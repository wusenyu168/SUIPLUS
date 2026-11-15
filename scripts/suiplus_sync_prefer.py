#!/usr/bin/env python3
"""梭哈式固定隧道优选（对齐 suoha-source）：

本机：VLESS-WS + Trojan-WS 仅监听 127.0.0.1，无入站 TLS（TLS 由 Cloudflare 终止）
订阅：每协议 3 条地址（默认 Argo 域名 / cf.090227.xyz / cloudflare.182682.xyz）
  入站卡 2 张 → 订阅名 6 个：{地区}-VLESS-默认|优选1|优选2 + Trojan 同理

不自动绑定到所有客户端。
依赖：suiplus_argo.sh 拉起 cloudflared + 路径分流。
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
DEBUG_LOG = Path("/usr/local/s-ui/suiplus-seed-debug.ndjson")
ARGO_DIR = Path("/usr/local/s-ui/argo")
ARGO_DOMAIN_FILE = ARGO_DIR / "argo_domain.txt"

VLESS_PORT = 10080
TROJAN_PORT = 10081
ENTRY_PORT = 10079
VLESS_PATH = "/suoha-vless"
TROJAN_PATH = "/suoha-trojan"

REGION_CN = {
    "TW": "台湾", "HK": "香港", "JP": "日本", "KR": "韩国", "SG": "新加坡",
    "US": "美国", "GB": "英国", "DE": "德国", "CN": "中国",
}

# legacy 6-card or 梭哈 names
LEGACY_RE = re.compile(r"^.+-(VLESS|Trojan)-(默认|优选1|优选2)$")
PREFER_TAGS_RE = re.compile(r"^.+-(VLESS|Trojan)$")  # 2-card style without TUD/梭哈


def dbg(msg: str, data: dict | None = None, hid: str = "C") -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "0d09c0",
            "runId": os.environ.get("SUIPLUS_RUN_ID", "sync-prefer"),
            "hypothesisId": hid,
            "location": "suiplus_sync_prefer.py",
            "message": msg,
            "data": data or {},
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
        }
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


def jblob(obj: Any):
    return sqlite3.Binary(json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))


def decode_blob(v):
    if v is None:
        return None
    if isinstance(v, memoryview):
        v = v.tobytes()
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8", "replace")
    if isinstance(v, str):
        return json.loads(v) if v.strip() else None
    return v


def settings(cur) -> dict[str, str]:
    cur.execute("SELECT key, value FROM settings")
    return {k: (v or "") for k, v in cur.fetchall()}


def detect_region() -> tuple[str, str]:
    code = "UN"
    try:
        with urllib.request.urlopen("https://www.cloudflare.com/cdn-cgi/trace", timeout=4) as r:
            for line in r.read().decode().splitlines():
                if line.startswith("loc="):
                    c = line.split("=", 1)[1].strip().upper()
                    if len(c) == 2 and c.isalpha():
                        code = c
                        break
    except Exception:
        pass
    return code, REGION_CN.get(code, code)


def is_prefer_tag(tag: str) -> bool:
    if not tag or "-TUD-" in tag:
        return False
    if "-梭哈-" in tag:
        return True
    if LEGACY_RE.match(tag):
        return True
    if PREFER_TAGS_RE.match(tag) and "梭哈" not in tag:
        # 台湾-VLESS / 台湾-Trojan (2-card)
        return True
    return False


def argo_domain() -> str:
    try:
        if ARGO_DOMAIN_FILE.is_file():
            d = ARGO_DOMAIN_FILE.read_text(encoding="utf-8").strip()
            if d and "." in d:
                return d
    except Exception:
        pass
    return ""


def build_addrs(panel_domain: str, argo: str) -> list[dict]:
    """Client-side TLS only (CF terminates). Match suoha link params."""
    # 默认必须用 Argo 临时域；没有 Argo 时先用面板域名占位（仍不可达直至隧道起来）
    default_host = argo if argo else panel_domain
    hosts = (
        (default_host, "-默认"),
        ("cf.090227.xyz", "-优选1"),
        ("cloudflare.182682.xyz", "-优选2"),
    )
    tls = {
        "enabled": True,
        "server_name": panel_domain,
        "insecure": False,
        "utls": {"enabled": True, "fingerprint": "chrome"},
        "alpn": ["h2", "http/1.1"],
    }
    return [
        {"server": h, "server_port": 443, "remark": remark, "tls": dict(tls)}
        for h, remark in hosts
    ]


def upsert_inbound(cur, *, tag: str, typ: str, listen_port: int, transport: dict, panel_domain: str, argo: str) -> int:
    addrs = build_addrs(panel_domain, argo)
    options = {
        "listen": "127.0.0.1",
        "listen_port": listen_port,
        "transport": transport,
    }
    out_json = {
        "tag": tag,
        "type": typ,
        "server": argo or panel_domain,
        "server_port": 443,
        "transport": transport,
        "tls": {"enabled": True, "server_name": panel_domain},
    }
    cur.execute("SELECT id FROM inbounds WHERE tag=?", (tag,))
    row = cur.fetchone()
    if row:
        cur.execute(
            "UPDATE inbounds SET type=?, tls_id=?, addrs=?, out_json=?, options=? WHERE id=?",
            (typ, 0, jblob(addrs), jblob(out_json), jblob(options), row[0]),
        )
        return int(row[0])
    cur.execute(
        "INSERT INTO inbounds(type, tag, tls_id, addrs, out_json, options) VALUES(?,?,?,?,?,?)",
        (typ, tag, 0, jblob(addrs), jblob(out_json), jblob(options)),
    )
    return int(cur.lastrowid)


def delete_prefer_inbounds(cur) -> list[tuple[int, str]]:
    cur.execute("SELECT id, tag FROM inbounds")
    rows = [(int(i), t or "") for i, t in cur.fetchall() if is_prefer_tag(t or "")]
    ids = [i for i, _ in rows]
    tags = {t for _, t in rows}
    for i in ids:
        cur.execute("DELETE FROM inbounds WHERE id=?", (i,))
    if ids:
        cur.execute("SELECT id, inbounds, links FROM clients")
        for cid, ib_raw, lk_raw in cur.fetchall():
            ibs = decode_blob(ib_raw) or []
            links = decode_blob(lk_raw) or []
            if not isinstance(ibs, list):
                ibs = []
            if not isinstance(links, list):
                links = []
            new_ibs = [x for x in ibs if x not in ids]
            new_links = [
                lk
                for lk in links
                if not (
                    isinstance(lk, dict)
                    and lk.get("type") == "local"
                    and str(lk.get("remark") or "") in tags
                )
            ]
            if new_ibs != ibs or new_links != links:
                cur.execute(
                    "UPDATE clients SET inbounds=?, links=? WHERE id=?",
                    (jblob(new_ibs), jblob(new_links), cid),
                )
    return rows


def ensure_client_flow_empty_for_ws(cur) -> None:
    """WS 优选不能带 xtls-rprx-vision。"""
    cur.execute("SELECT id, config FROM clients")
    for cid, cfg_raw in cur.fetchall():
        cfg = decode_blob(cfg_raw) or {}
        if not isinstance(cfg, dict):
            continue
        vless = cfg.get("vless")
        if isinstance(vless, dict) and vless.get("flow"):
            # keep vision for Reality TUD users — only clear if they ONLY have prefer?
            # Safer: leave config; LinkGenerator adds flow when tls enabled.
            # Prefer inbounds have tls_id=0 so vision stripped in core users;
            # but addr-level tls still adds flow in links. Clear flow globally breaks Reality.
            pass


def fix_reality_sni(cur) -> bool:
    """H-Reality: client TLS missing server_name → link 无 sni → ping 失败。"""
    cur.execute("SELECT id, name, server, client FROM tls")
    changed = False
    for rid, name, server_raw, client_raw in cur.fetchall():
        server = decode_blob(server_raw) or {}
        client = decode_blob(client_raw) or {}
        if not isinstance(server, dict) or not isinstance(client, dict):
            continue
        reality = server.get("reality")
        if not isinstance(reality, dict) or not reality.get("enabled"):
            continue
        hs = reality.get("handshake") or {}
        sni = hs.get("server") or "apple.com"
        # ensure client has server_name for link sni=
        c_real = client.get("reality") if isinstance(client.get("reality"), dict) else {}
        new_client = dict(client)
        new_client["server_name"] = sni
        new_client["reality"] = dict(c_real)
        new_client["reality"]["enabled"] = True
        if "utls" not in new_client:
            new_client["utls"] = {"enabled": True, "fingerprint": "chrome"}
        cur.execute("UPDATE tls SET client=? WHERE id=?", (jblob(new_client), rid))
        changed = True
        dbg("reality_sni_fixed", {"tls_id": rid, "name": name, "sni": sni}, "R")
    return changed


def regen_local_links(cur, hostname: str) -> int:
    """Regenerate local links for clients from current inbounds (subset of LinkGenerator)."""
    import urllib.parse

    def tls_params(tls: dict) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = []
        reality = tls.get("reality") if isinstance(tls.get("reality"), dict) else {}
        if reality.get("enabled"):
            params.append(("security", "reality"))
            if reality.get("public_key"):
                params.append(("pbk", str(reality["public_key"])))
            if reality.get("short_id"):
                params.append(("sid", str(reality["short_id"])))
        elif tls.get("enabled"):
            params.append(("security", "tls"))
            if tls.get("insecure"):
                params.append(("allowInsecure", "1"))
        if tls.get("server_name"):
            params.append(("sni", str(tls["server_name"])))
        utls = tls.get("utls") or {}
        if isinstance(utls, dict) and utls.get("fingerprint"):
            params.append(("fp", str(utls["fingerprint"])))
        alpn = tls.get("alpn")
        if isinstance(alpn, list) and alpn:
            params.append(("alpn", ",".join(str(x) for x in alpn)))
        return params

    def transport_params(t: Any) -> list[tuple[str, str]]:
        if not isinstance(t, dict) or not t:
            return [("type", "tcp")]
        typ = t.get("type") or "tcp"
        params = [("type", typ)]
        if typ == "ws":
            if t.get("path"):
                params.append(("path", str(t["path"])))
            headers = t.get("headers") or {}
            if isinstance(headers, dict) and headers.get("Host"):
                params.append(("host", str(headers["Host"])))
        return params

    def add_params(uri: str, params: list[tuple[str, str]], remark: str) -> str:
        q = urllib.parse.urlencode(params)
        frag = urllib.parse.quote(remark, safe="")
        return f"{uri}?{q}#{frag}" if q else f"{uri}#{frag}"

    def prepare_tls(tls_id: int) -> dict:
        if not tls_id:
            return {}
        cur.execute("SELECT server, client FROM tls WHERE id=?", (tls_id,))
        row = cur.fetchone()
        if not row:
            return {}
        server = decode_blob(row[0]) or {}
        client = decode_blob(row[1]) or {}
        if not isinstance(client, dict):
            client = {}
        if isinstance(server, dict):
            for k in ("enabled", "server_name", "alpn"):
                if k in server:
                    client[k] = server[k]
            if isinstance(server.get("reality"), dict):
                cr = client.get("reality") if isinstance(client.get("reality"), dict) else {}
                sr = server["reality"]
                cr = dict(cr)
                cr["enabled"] = sr.get("enabled", True)
                sids = sr.get("short_id") or []
                if isinstance(sids, list) and sids:
                    # prefer non-empty
                    sid = next((x for x in sids if x), sids[0])
                    cr["short_id"] = sid
                client["reality"] = cr
                if not client.get("server_name"):
                    hs = sr.get("handshake") or {}
                    if isinstance(hs, dict) and hs.get("server"):
                        client["server_name"] = hs["server"]
        return client

    n = 0
    cur.execute("SELECT id, config, inbounds, links FROM clients")
    for cid, cfg_raw, ib_raw, lk_raw in cur.fetchall():
        cfg = decode_blob(cfg_raw) or {}
        ibs = decode_blob(ib_raw) or []
        old_links = decode_blob(lk_raw) or []
        if not isinstance(cfg, dict) or not isinstance(ibs, list):
            continue
        if not isinstance(old_links, list):
            old_links = []

        # rebuild only vless/trojan local links; keep other locals + externals
        ib_tags = set()
        vt_tags = set()
        for iid in ibs:
            cur.execute("SELECT type, tag FROM inbounds WHERE id=?", (iid,))
            row = cur.fetchone()
            if row:
                ib_tags.add(row[1])
                if row[0] in ("vless", "trojan"):
                    vt_tags.add(row[1])

        kept = []
        for lk in old_links:
            if not isinstance(lk, dict):
                continue
            if lk.get("type") != "local":
                kept.append(lk)
                continue
            remark = str(lk.get("remark") or "")
            if remark in vt_tags or is_prefer_tag(remark):
                continue  # will regenerate
            # drop locals for inbounds no longer assigned to this client
            if remark and remark not in ib_tags:
                continue
            kept.append(lk)

        new_local: list[dict] = []
        for iid in ibs:
            cur.execute(
                "SELECT id, type, tag, tls_id, addrs, options FROM inbounds WHERE id=?",
                (iid,),
            )
            row = cur.fetchone()
            if not row:
                continue
            _, typ, tag, tls_id, addrs_raw, opt_raw = row
            if typ not in ("vless", "trojan"):
                continue
            addrs = decode_blob(addrs_raw) or []
            opts = decode_blob(opt_raw) or {}
            if not isinstance(addrs, list) or not addrs:
                continue
            if not isinstance(opts, dict):
                opts = {}
            base_tls = prepare_tls(int(tls_id or 0))
            transport = opts.get("transport") or {}
            for addr in addrs:
                if not isinstance(addr, dict):
                    continue
                remark = f"{tag}{addr.get('remark') or ''}"
                server = str(addr.get("server") or hostname)
                port = int(addr.get("server_port") or 0)
                tls = dict(base_tls)
                if isinstance(addr.get("tls"), dict):
                    tls.update(addr["tls"])
                params = list(transport_params(transport))
                if typ == "vless":
                    user = cfg.get("vless") if isinstance(cfg.get("vless"), dict) else {}
                    uuid = str(user.get("uuid") or "")
                    tparams = list(params)
                    if tls.get("enabled") or (
                        isinstance(tls.get("reality"), dict) and tls["reality"].get("enabled")
                    ):
                        tparams.extend(tls_params(tls))
                        is_ws = isinstance(transport, dict) and transport.get("type") == "ws"
                        is_reality = isinstance(tls.get("reality"), dict) and tls["reality"].get(
                            "enabled"
                        )
                        if (not is_ws) and is_reality and user.get("flow"):
                            tparams.append(("flow", str(user["flow"])))
                    uri = f"vless://{uuid}@{server}:{port}"
                    new_local.append(
                        {"remark": tag, "type": "local", "uri": add_params(uri, tparams, remark)}
                    )
                else:
                    user = cfg.get("trojan") if isinstance(cfg.get("trojan"), dict) else {}
                    pwd = str(user.get("password") or "")
                    tparams = list(params)
                    if tls.get("enabled"):
                        tparams.extend(tls_params(tls))
                    uri = f"trojan://{pwd}@{server}:{port}"
                    new_local.append(
                        {"remark": tag, "type": "local", "uri": add_params(uri, tparams, remark)}
                    )
        new_links = new_local + kept
        cur.execute("UPDATE clients SET links=? WHERE id=?", (jblob(new_links), cid))
        n += 1
    return n


def maybe_start_argo() -> str:
    script = Path("/usr/local/s-ui/scripts/suiplus_argo.sh")
    if script.is_file():
        try:
            subprocess.call(["bash", str(script)], timeout=120)
        except Exception as e:
            dbg("argo_start_err", {"err": str(e)}, "E")
    return argo_domain()


def main() -> int:
    if not Path(DB).is_file():
        print("no db")
        return 0
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    s = settings(cur)
    domain = (s.get("webDomain") or "").strip()
    prefer = s.get("suiplusPreferEnable", "false").lower() in ("true", "1", "yes")

    # Always fix Reality SNI (SUI TUD VLESS)
    fix_reality_sni(cur)

    dbg("prefer_entry", {"prefer": prefer, "domain": domain}, "A")

    if not prefer:
        removed = delete_prefer_inbounds(cur)
        conn.commit()
        print(f"prefer off: removed {len(removed)}")
        dbg("prefer_off", {"removed": removed}, "A")
        conn.close()
        return 0

    if not domain:
        print("prefer on but no webDomain")
        dbg("prefer_no_domain", {}, "A")
        conn.close()
        return 0

    code, label = detect_region()
    # start/ensure argo before writing default host
    argo = maybe_start_argo()
    if not argo:
        argo = argo_domain()
    dbg("argo_domain", {"argo": argo, "panel": domain}, "E")

    # only remove legacy 梭哈 / 6-card names; keep current 台湾-VLESS|Trojan ids so client binds survive
    removed = []
    cur.execute("SELECT id, tag FROM inbounds")
    for rid, tag in cur.fetchall():
        t = tag or ""
        if "-TUD-" in t:
            continue
        legacy = ("-梭哈-" in t) or bool(LEGACY_RE.match(t))
        if legacy:
            removed.append((int(rid), t))
    if removed:
        ids = [i for i, _ in removed]
        tags = {t for _, t in removed}
        for i in ids:
            cur.execute("DELETE FROM inbounds WHERE id=?", (i,))
        # unlink legacy ids only
        cur.execute("SELECT id, inbounds, links FROM clients")
        for cid, ib_raw, lk_raw in cur.fetchall():
            ibs = decode_blob(ib_raw) or []
            links = decode_blob(lk_raw) or []
            if not isinstance(ibs, list):
                ibs = []
            if not isinstance(links, list):
                links = []
            new_ibs = [x for x in ibs if x not in ids]
            new_links = [
                lk
                for lk in links
                if not (
                    isinstance(lk, dict)
                    and lk.get("type") == "local"
                    and str(lk.get("remark") or "") in tags
                )
            ]
            if new_ibs != ibs or new_links != links:
                cur.execute(
                    "UPDATE clients SET inbounds=?, links=? WHERE id=?",
                    (jblob(new_ibs), jblob(new_links), cid),
                )
    dbg("removed_legacy_prefer", {"rows": removed}, "H1")

    vless_tag = f"{label}-VLESS"
    trojan_tag = f"{label}-Trojan"
    vless_transport = {"type": "ws", "path": VLESS_PATH, "headers": {"Host": domain}}
    trojan_transport = {"type": "ws", "path": TROJAN_PATH, "headers": {"Host": domain}}

    vid = upsert_inbound(
        cur,
        tag=vless_tag,
        typ="vless",
        listen_port=VLESS_PORT,
        transport=vless_transport,
        panel_domain=domain,
        argo=argo,
    )
    tid = upsert_inbound(
        cur,
        tag=trojan_tag,
        typ="trojan",
        listen_port=TROJAN_PORT,
        transport=trojan_transport,
        panel_domain=domain,
        argo=argo,
    )

    # DO NOT auto-bind prefer to clients
    ensure_client_flow_empty_for_ws(cur)
    regen_local_links(cur, domain)
    conn.commit()

    cur.execute("SELECT tag, addrs FROM inbounds WHERE id IN (?,?)", (vid, tid))
    verify = []
    for tag, addrs_raw in cur.fetchall():
        addrs = decode_blob(addrs_raw) or []
        verify.append(
            {
                "tag": tag,
                "hosts": [(a.get("remark"), a.get("server")) for a in addrs if isinstance(a, dict)],
            }
        )
    conn.close()
    print(f"prefer OK(suoha-model): {vless_tag}+{trojan_tag} argo={argo or '(pending)'} listen=127.0.0.1:{VLESS_PORT}/{TROJAN_PORT}")
    dbg("prefer_ok_suoha", {"vless_id": vid, "trojan_id": tid, "argo": argo, "verify": verify}, "C")
    return 0


if __name__ == "__main__":
    sys.exit(main())
