#!/usr/bin/env python3
"""梭哈式固定隧道优选（对齐 suoha-source 路径/SNI，入站 UI 拆 6 卡）：

仅本脚本管理的入站才走优选：Argo / cf.090227.xyz / cloudflare.182682.xyz
TUD 等非优选入站禁止写入上述主机（由 suiplus_sync_addrs.py 绑面板域名，不改 IP）。

内核真实监听仍 2 个（Argo 分流目标）：
  VLESS-WS → 127.0.0.1:10080   Trojan-WS → 127.0.0.1:10081
入站管理拆成 6 张卡（优选* 用闲置本机端口占位；流量仍经 10080/10081）：
  {地区}-优选-VLESS-默认|优选1|优选2
  {地区}-优选-Trojan-默认|优选1|优选2
SNI 与 WS Host 一律使用 Argo 临时域（不是面板域名）。无 alpn（避免 CF 协商 h2 打断 WS）。

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
from pathlib import Path
from typing import Any

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
ARGO_DIR = Path("/usr/local/s-ui/argo")
ARGO_DOMAIN_FILE = ARGO_DIR / "argo_domain.txt"

# Real Argo targets (must match suiplus_argo.sh)
VLESS_PORT = 10080
TROJAN_PORT = 10081
ENTRY_PORT = 10079
VLESS_PATH = "/suoha-vless"
TROJAN_PATH = "/suoha-trojan"
# Extra listen ports so UI can show N cards without colliding on 10080/10081
# Keep 默认 + 优选1/2 only (6 cards total).
VLESS_UI_PORTS = {
    "默认": 10080,
    "优选1": 10082,
    "优选2": 10084,
}
TROJAN_UI_PORTS = {
    "默认": 10081,
    "优选1": 10083,
    "优选2": 10085,
}
PREFER_LABELS = ("默认", "优选1", "优选2")

REGION_CN = {
    "TW": "台湾", "HK": "香港", "JP": "日本", "KR": "韩国", "SG": "新加坡",
    "US": "美国", "GB": "英国", "DE": "德国", "CN": "中国",
}

# legacy / current prefer card names (默认 + 优选1..4; [3-4] kept for prune of old 10-card layout)
LEGACY_RE = re.compile(r"^.+-(VLESS|Trojan)-(默认|优选[1-4])$")
# 2-card legacy: 美国-VLESS / 美国-优选-VLESS / 美国-梭哈-VLESS (never TUD)
PREFER_TAGS_RE = re.compile(r"^.+-(?:优选-|梭哈-)?(VLESS|Trojan)$")


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


def client_tls(argo: str) -> dict:
    """Client TLS/SNI = Argo domain (suoha-source), NOT panel domain.

    Do NOT set alpn. newsuoha Clash leaves alpn absent; offering h2 first makes
    Cloudflare negotiate h2, which breaks WebSocket Upgrade (no HTTP/1.1 101).
    """
    return {
        "enabled": True,
        "server_name": argo,
        "insecure": False,
        "utls": {"enabled": True, "fingerprint": "chrome"},
    }


def prefer_hosts(argo: str) -> dict[str, str]:
    """label -> subscription server host (SNI/Host still argo).

    默认 = Quick Tunnel hostname; 优选1/2 = CF CDN edge domains (IP-block escape).
    """
    return {
        "默认": argo,
        "优选1": "cf.090227.xyz",
        "优选2": "cloudflare.182682.xyz",
    }


def upsert_inbound(
    cur,
    *,
    tag: str,
    typ: str,
    listen_port: int,
    transport: dict,
    argo: str,
    server: str,
) -> int:
    """One inbound card = one subscription node (empty remark → name == tag)."""
    tls = client_tls(argo)
    addrs = [{"server": server, "server_port": 443, "remark": "", "tls": dict(tls)}]
    options = {
        "listen": "127.0.0.1",
        "listen_port": listen_port,
        "transport": transport,
    }
    out_json = {
        "tag": tag,
        "type": typ,
        "server": server,
        "server_port": 443,
        "transport": transport,
        "tls": dict(tls),
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


def as_int_ids(seq: Any) -> list[int]:
    """Normalize inbound id lists (JSON may mix int/str)."""
    out: list[int] = []
    if not isinstance(seq, list):
        return out
    for x in seq:
        try:
            out.append(int(x))
        except Exception:
            continue
    return out


def existing_inbound_ids(cur) -> set[int]:
    cur.execute("SELECT id FROM inbounds")
    return {int(r[0]) for r in cur.fetchall()}


def prune_orphan_client_inbounds(cur) -> dict[str, Any]:
    """Remove client.inbounds entries that no longer exist in inbounds table."""
    valid = existing_inbound_ids(cur)
    touched = 0
    removed_total = 0
    cur.execute("SELECT id, inbounds FROM clients")
    for cid, ib_raw in cur.fetchall():
        ibs = decode_blob(ib_raw) or []
        cur_ids = as_int_ids(ibs)
        kept = [i for i in cur_ids if i in valid]
        removed = len(cur_ids) - len(kept)
        # Always rewrite if types were mixed (str/int) even when set equal
        if removed or kept != ibs:
            cur.execute("UPDATE clients SET inbounds=? WHERE id=?", (jblob(kept), cid))
            touched += 1
            removed_total += removed
    return {"clients_touched": touched, "ids_removed": removed_total}


def delete_prefer_inbounds(cur, *, keep_tags: set[str] | None = None) -> list[tuple[int, str]]:
    """Delete prefer/梭哈 inbounds. If keep_tags set, only delete tags not in that set.

    Keeping wanted tags preserves inbound row ids so client checkbox bindings do not drop.
    """
    cur.execute("SELECT id, tag FROM inbounds")
    rows = []
    for i, t in cur.fetchall():
        tag = t or ""
        if not is_prefer_tag(tag):
            continue
        if keep_tags is not None and tag in keep_tags:
            continue
        rows.append((int(i), tag))
    ids = [i for i, _ in rows]
    id_set = set(ids)
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
            # int-normalize so str "124" is removed when 124 was deleted
            new_ibs = [i for i in as_int_ids(ibs) if i not in id_set]
            new_links = [
                lk
                for lk in links
                if not (
                    isinstance(lk, dict)
                    and lk.get("type") == "local"
                    and str(lk.get("remark") or "") in tags
                )
            ]
            if new_ibs != as_int_ids(ibs) or new_links != links or new_ibs != ibs:
                cur.execute(
                    "UPDATE clients SET inbounds=?, links=? WHERE id=?",
                    (jblob(new_ibs), jblob(new_links), cid),
                )
    # Also drop any other dangling inbound ids left behind
    prune_orphan_client_inbounds(cur)
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


def maybe_start_argo(*, force: bool = False) -> str:
    script = Path("/usr/local/s-ui/scripts/suiplus_argo.sh")
    if script.is_file():
        try:
            env = os.environ.copy()
            if force or os.environ.get("FORCE_ARGO_RESTART") == "1":
                env["FORCE_ARGO_RESTART"] = "1"
            # New session so Argo is less likely to die with a parent oneshot unit.
            subprocess.call(
                ["bash", str(script)],
                timeout=180,
                env=env,
                start_new_session=True,
            )
        except Exception:
            pass
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

    if not prefer:
        removed = delete_prefer_inbounds(cur)
        conn.commit()
        print(f"prefer off: removed {len(removed)}")
        conn.close()
        return 0

    if not domain:
        print("prefer on but no webDomain")
        conn.close()
        return 0

    _code, label = detect_region()
    # FORCE_ARGO_RESTART=1 refreshes Quick Tunnel domain/colo before rewrite
    force_argo = os.environ.get("FORCE_ARGO_RESTART", "") == "1"
    argo = maybe_start_argo(force=force_argo)
    if not argo:
        argo = argo_domain()

    if not argo:
        print("prefer on but no Argo domain (cloudflared not ready)")
        conn.close()
        return 1

    hosts = prefer_hosts(argo)
    vless_transport = {"type": "ws", "path": VLESS_PATH, "headers": {"Host": argo}}
    trojan_transport = {"type": "ws", "path": TROJAN_PATH, "headers": {"Host": argo}}

    # Wanted tags for this region; upsert keeps row ids so client checkboxes stick.
    keep_tags: set[str] = set()
    for lab in PREFER_LABELS:
        for proto in ("VLESS", "Trojan"):
            keep_tags.add(f"{label}-优选-{proto}-{lab}")
    # Drop legacy/梭哈/extra prefer cards only; never wipe wanted ids.
    delete_prefer_inbounds(cur, keep_tags=keep_tags)

    prefer_ids: list[int] = []
    for lab in PREFER_LABELS:
        for typ, ports, transport in (
            ("vless", VLESS_UI_PORTS, vless_transport),
            ("trojan", TROJAN_UI_PORTS, trojan_transport),
        ):
            proto = "VLESS" if typ == "vless" else "Trojan"
            tag = f"{label}-优选-{proto}-{lab}"
            server = hosts[lab]
            listen_port = ports[lab]
            iid = upsert_inbound(
                cur,
                tag=tag,
                typ=typ,
                listen_port=listen_port,
                transport=transport,
                argo=argo,
                server=server,
            )
            prefer_ids.append(iid)

    # Do NOT force-bind prefer onto clients — subscription must follow checkbox only.
    prune_orphan_client_inbounds(cur)
    ensure_client_flow_empty_for_ws(cur)
    regen_local_links(cur, argo)
    conn.commit()
    conn.close()
    print(
        f"prefer OK(cards={len(prefer_ids)}): argo={argo} "
        f"real_listen=127.0.0.1:{VLESS_PORT}/{TROJAN_PORT} prefer_ids={prefer_ids}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
