#!/usr/bin/env python3
"""SUIPLUS Cloudflare DDNS — reads enable/token/zone from s-ui settings SQLite."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
STATE = Path("/var/lib/cf-ddns/last_ip")
LOG = Path("/var/log/cf-ddns.log")
API = "https://api.cloudflare.com/client/v4"


def log(msg: str) -> None:
    line = msg
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def settings(db: str) -> dict[str, str]:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM settings")
    out = {k: (v or "") for k, v in cur.fetchall()}
    conn.close()
    return out


def public_ip() -> str:
    for url in ("https://api64.ipify.org", "https://ipv4.icanhazip.com"):
        try:
            with urllib.request.urlopen(url, timeout=8) as r:
                return r.read().decode().strip()
        except Exception:
            continue
    raise RuntimeError("cannot detect public IP")


def cf(token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "suiplus-cf-ddns/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode("utf-8", "replace")) from e
    if not payload.get("success"):
        raise RuntimeError(json.dumps(payload.get("errors") or payload, ensure_ascii=False))
    return payload


def main() -> int:
    if not Path(DB).is_file():
        log(f"skip: no db {DB}")
        return 0
    s = settings(DB)
    if s.get("cfDdnsEnable", "false").lower() not in ("true", "1", "yes"):
        log("skip: cfDdnsEnable=false")
        return 0
    token = (s.get("cfDdnsToken") or os.environ.get("CF_API_TOKEN") or "").strip()
    # CF zone/record names are case-insensitive; normalize to lowercase FQDN
    zone = (s.get("cfDdnsZone") or "").strip().lower().rstrip(".")
    record = (s.get("cfDdnsRecord") or "@").strip().lower().rstrip(".")
    proxied = s.get("cfDdnsProxied", "false").lower() in ("true", "1", "yes")
    if not token or not zone:
        log("skip: missing cfDdnsToken or cfDdnsZone")
        return 0

    fqdn = zone if record in ("@", "") else f"{record}.{zone}"
    ip = public_ip()
    last = STATE.read_text(encoding="utf-8").strip() if STATE.is_file() else ""
    log(f"sync fqdn={fqdn} ip={ip} last={last or '-'} proxied={proxied}")

    z = cf(token, "GET", f"/zones?{urllib.parse.urlencode({'name': zone, 'status': 'active'})}")
    zones = z.get("result") or []
    if not zones:
        log(f"error: zone not found {zone}")
        return 1
    zone_id = zones[0]["id"]
    q = urllib.parse.urlencode({"type": "A", "name": fqdn})
    found = (cf(token, "GET", f"/zones/{zone_id}/dns_records?{q}").get("result") or [])
    if not found:
        # also try original-case lookup miss → create lowercase name
        cf(
            token,
            "POST",
            f"/zones/{zone_id}/dns_records",
            {"type": "A", "name": fqdn, "content": ip, "ttl": 1, "proxied": proxied},
        )
        log(f"created A {fqdn} -> {ip}")
    else:
        rec = found[0]
        if rec.get("content") == ip and bool(rec.get("proxied")) == proxied and last == ip:
            log(f"unchanged {fqdn} -> {ip}")
            return 0
        cf(
            token,
            "PUT",
            f"/zones/{zone_id}/dns_records/{rec['id']}",
            {"type": "A", "name": fqdn, "content": ip, "ttl": 1, "proxied": proxied},
        )
        log(f"updated A {fqdn} -> {ip}")

    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(ip + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"error: {e}")
        sys.exit(1)
