#!/usr/bin/env python3
"""Sync SUI inbound Addrs only (domain mode).

Scheme B: TUD (非优选) only get panel domain / public IP — never Argo/CF prefer hosts.
Prefer (梭哈式固定隧道) is handled exclusively by suiplus_sync_prefer.py.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
# Uplink often drops 80/443/16122. Keep TUD nodes on high ports that already pass.
REACHABLE_PORTS = {
    "hysteria2": 18443,
    "tuic": 18446,
    "vless": 18445,
    "anytls": 45738,
    "shadowsocks": 13495,
}
FILTERED_LISTEN_PORTS = {80, 443, 16122}


def jblob(obj):
    return sqlite3.Binary(json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))


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


def is_sui_tud(tag: str) -> bool:
    return "-TUD-" in (tag or "")


def effective_port(itype: str, port: int) -> int:
    want = REACHABLE_PORTS.get(itype or "")
    if want and (not port or port in FILTERED_LISTEN_PORTS):
        return want
    return port


def rewrite_uri_port(uri: str, new_port: int) -> str:
    return re.sub(r"(@[^:/?#]+):\d+", rf"\1:{new_port}", uri or "", count=1)


def main() -> int:
    if not Path(DB).is_file():
        print(f"no db {DB}")
        return 0
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    s = settings(cur)
    domain = (s.get("webDomain") or "").strip()
    ip = public_ip()
    primary = domain if domain else ip
    if not primary:
        print("no domain and no ip")
        return 1

    cur.execute("SELECT id, type, tag, out_json, options FROM inbounds")
    rows = cur.fetchall()
    updated = 0
    tag_ports: dict[str, int] = {}
    for rid, itype, tag, out_raw, opt_raw in rows:
        if not is_sui_tud(tag):
            continue  # leave 梭哈 prefer inbounds alone
        opts = decode_blob(opt_raw) or {}
        port = int(opts.get("listen_port") or 0)
        out = decode_blob(out_raw) or {}
        if not port and isinstance(out, dict):
            port = int(out.get("server_port") or 0)
        port = effective_port(itype, port)
        if isinstance(opts, dict) and port:
            opts["listen_port"] = port
        # SUI: single addr, empty remark → subscribe name = tag (台湾-TUD-HY2)
        new_addrs = [{"server": primary, "server_port": port, "remark": ""}]
        if isinstance(out, dict):
            out["server"] = primary
            if port:
                out["server_port"] = port
            if itype and not out.get("type"):
                out["type"] = itype
            # Keep protocol ALPNs coherent when multiple inbounds share one TLS profile.
            # TUIC/QUIC needs h3 only; VLESS TCP needs h2/http1.1 — never collapse TLS to h3-only.
            tls = out.get("tls") if isinstance(out.get("tls"), dict) else None
            if tls is not None:
                if itype == "tuic":
                    tls["alpn"] = ["h3"]
                elif itype == "vless":
                    tls["alpn"] = ["h2", "http/1.1"]
                elif itype == "hysteria2":
                    tls["alpn"] = ["h3", "h2", "http/1.1"]
                out["tls"] = tls
        cur.execute(
            "UPDATE inbounds SET addrs=?, out_json=?, options=? WHERE id=?",
            (jblob(new_addrs), jblob(out), jblob(opts), rid),
        )
        updated += 1
        tag_ports[tag] = port

    # Strip mistaken TUD+优选 entries from stored client links (subscription source)
    stripped = 0
    prefer_hosts = ("cf.090227.xyz", "cloudflare.182682.xyz")
    cur.execute("SELECT id, links FROM clients")
    for cid, links_raw in cur.fetchall():
        links = decode_blob(links_raw) or []
        if not isinstance(links, list):
            continue
        new_links = []
        for lk in links:
            if not isinstance(lk, dict):
                continue
            if lk.get("type") == "local" and "-TUD-" in str(lk.get("remark") or ""):
                uri = str(lk.get("uri") or "")
                host = ""
                try:
                    if "@" in uri:
                        host = uri.split("@", 1)[1].split("?", 1)[0].split("#", 1)[0].split(":")[0].lower()
                except Exception:
                    host = ""
                frag = uri.split("#", 1)[1] if "#" in uri else ""
                if host in prefer_hosts or "优选" in frag:
                    stripped += 1
                    continue
                remark = str(lk.get("remark") or "")
                if remark in tag_ports:
                    lk = dict(lk)
                    lk["uri"] = rewrite_uri_port(uri, tag_ports[remark])
            new_links.append(lk)
        if new_links != links:
            cur.execute("UPDATE clients SET links=? WHERE id=?", (jblob(new_links), cid))

    conn.commit()
    conn.close()
    print(f"sync_addrs OK: sui_domain_mode server={primary} updated={updated} stripped_tud_prefer_links={stripped}")
    # Prefer/Argo is intentionally NOT invoked here.
    # DDNS timer → sync_addrs only; prefer runs via suiplus_after_settings / suiplus-prefer.service.
    return 0


if __name__ == "__main__":
    sys.exit(main())
