#!/usr/bin/env python3
"""Sync inbound Addrs from settings:
- suiplusPreferEnable=false or empty webDomain → IP only
- prefer on + webDomain set → domain (same as panel) + IP
Also refresh out_json.server to match primary host.
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


def dbg(msg: str, data: dict | None = None) -> None:
    # #region agent log
    try:
        payload = {
            "sessionId": "0d09c0",
            "runId": os.environ.get("SUIPLUS_RUN_ID", "sync-addrs"),
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
    addrs: list[dict] = []
    if prefer and domain:
        addrs.append({"server": domain, "server_port": port, "remark": "-域名"})
    if ip:
        addrs.append({"server": ip, "server_port": port, "remark": "-IP"})
    return addrs


def main() -> int:
    if not Path(DB).is_file():
        print(f"no db {DB}")
        return 0
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    s = settings(cur)
    domain = (s.get("webDomain") or "").strip()
    prefer = s.get("suiplusPreferEnable", "false").lower() in ("true", "1", "yes")
    ip = public_ip()
    if not ip:
        print("cannot detect public IP")
        dbg("no_ip", {})
        return 1

    if prefer and not domain:
        print("prefer on but webDomain empty — keep IP-only")
        prefer = False

    primary = domain if (prefer and domain) else ip
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
        if isinstance(out, dict):
            out["server"] = primary
            if port:
                out["server_port"] = port
        cur.execute(
            "UPDATE inbounds SET addrs=?, out_json=? WHERE id=?",
            (jblob(new_addrs), jblob(out), rid),
        )
        updated += 1
        dbg("row", {"id": rid, "tag": tag, "n": len(new_addrs), "primary": primary})

    # ensure prefer key exists
    if "suiplusPreferEnable" not in s:
        cur.execute(
            "INSERT INTO settings(key,value) VALUES(?,?)",
            ("suiplusPreferEnable", "false"),
        )

    conn.commit()
    conn.close()
    print(f"sync_addrs OK: prefer={prefer} domain={domain or '-'} ip={ip} updated={updated}")
    dbg("done", {"prefer": prefer, "domain": domain, "ip": ip, "updated": updated})
    return 0


if __name__ == "__main__":
    sys.exit(main())
