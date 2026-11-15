#!/usr/bin/env python3
"""Sync inbound Addrs from settings (v2):

SUI nodes (unchanged tag names):
  - no webDomain → single addr = public IP, remark ""
  - has webDomain (证书绑定域名) → single addr = domain only, remark ""
    (域名模式，不用 IP，不改名成 CDN优选/IP)

Prefer (梭哈式固定隧道优选1/2) when suiplusPreferEnable=true and webDomain set:
  - extra addrs: cf.090227.xyz / cloudflare.182682.xyz
  - remark "-优选1" / "-优选2"
  - tls.server_name = panel domain（与固定隧道同域）
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
DEBUG_LOG = Path("/usr/local/s-ui/suiplus-seed-debug.ndjson")

# 梭哈式固定隧道优选域名（与 suoha-source 一致）
SUOHA_PREFER = (
    ("cf.090227.xyz", "-优选1"),
    ("cloudflare.182682.xyz", "-优选2"),
)


def dbg(msg: str, data: dict | None = None) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "0d09c0",
            "runId": os.environ.get("SUIPLUS_RUN_ID", "sync-addrs-v2"),
            "hypothesisId": "C",
            "location": "suiplus_sync_addrs.py",
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


def jblob(obj):
    raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return sqlite3.Binary(raw)


def public_ip() -> str:
    for url in ("https://api64.ipify.org", "https://ipv4.icanhazip.com"):
        try:
            with urllib.request.urlopen(url, timeout=6) as r:
                ip = r.read().decode().strip()
                if ip:
                    return ip
        except Exception:
            continue
    return ""


def settings(cur: sqlite3.Cursor) -> dict[str, str]:
    cur.execute("SELECT key, value FROM settings")
    return {k: (v or "") for k, v in cur.fetchall()}


def decode_blob(v) -> object:
    if v is None:
        return None
    if isinstance(v, memoryview):
        v = v.tobytes()
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8", "replace")
    if isinstance(v, str):
        return json.loads(v) if v.strip() else None
    return v


def build_addrs(domain: str, ip: str, prefer: bool, port: int) -> list[dict]:
    """SUI 主入口 + 可选梭哈式优选1/2。主入口 remark 为空 → 订阅名=入站 tag。"""
    addrs: list[dict] = []

    # SUI 主节点：有域名则域名模式；否则临时用 IP
    if domain:
        addrs.append({"server": domain, "server_port": port, "remark": ""})
    elif ip:
        addrs.append({"server": ip, "server_port": port, "remark": ""})

    # 梭哈式固定隧道优选（不改动 SUI 主节点名）
    if prefer and domain:
        for host, remark in SUOHA_PREFER:
            addrs.append(
                {
                    "server": host,
                    "server_port": port,
                    "remark": remark,
                    # 固定隧道：SNI/证书域名仍用面板同域
                    "tls": {"server_name": domain, "enabled": True},
                }
            )
    return addrs


def main() -> int:
    if not Path(DB).is_file():
        print(f"no db {DB}")
        return 0
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    s = settings(cur)
    domain = (s.get("webDomain") or "").strip()
    cert = (s.get("webCertFile") or "").strip()
    prefer = s.get("suiplusPreferEnable", "false").lower() in ("true", "1", "yes")
    ip = public_ip()
    if not ip and not domain:
        print("cannot detect public IP and no domain")
        dbg("no_ip_no_domain", {})
        return 1

    if prefer and not domain:
        print("prefer on but webDomain empty — skip 优选1/2, SUI stays IP/domain rule")
        prefer = False

    # 域名模式优先（有绑定域名即用域名；证书路径有则更好）
    primary = domain if domain else ip
    mode = "domain" if domain else "ip"
    dbg(
        "plan",
        {
            "mode": mode,
            "domain": domain,
            "has_cert": bool(cert),
            "prefer": prefer,
            "ip": ip,
        },
    )

    cur.execute("SELECT id, tag, addrs, out_json, options FROM inbounds")
    rows = cur.fetchall()
    updated = 0
    for rid, tag, addrs_raw, out_raw, opt_raw in rows:
        opts = decode_blob(opt_raw) or {}
        port = int(opts.get("listen_port") or 0)
        if not port:
            out0 = decode_blob(out_raw) or {}
            port = int(out0.get("server_port") or 0)
        new_addrs = build_addrs(domain, ip, prefer, port)
        out = decode_blob(out_raw) or {}
        if isinstance(out, dict) and primary:
            out["server"] = primary
            if port:
                out["server_port"] = port
        cur.execute(
            "UPDATE inbounds SET addrs=?, out_json=? WHERE id=?",
            (jblob(new_addrs), jblob(out), rid),
        )
        updated += 1
        servers = [a.get("server") for a in new_addrs]
        remarks = [a.get("remark") for a in new_addrs]
        dbg("row", {"id": rid, "tag": tag, "servers": servers, "remarks": remarks})

    if "suiplusPreferEnable" not in s:
        cur.execute(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            ("suiplusPreferEnable", "false"),
        )

    conn.commit()
    conn.close()
    print(
        f"sync_addrs OK: mode={mode} prefer={prefer} domain={domain or '-'} "
        f"ip={ip or '-'} updated={updated}"
    )
    dbg("done", {"mode": mode, "prefer": prefer, "domain": domain, "updated": updated})
    return 0


if __name__ == "__main__":
    sys.exit(main())
