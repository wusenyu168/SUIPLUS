#!/usr/bin/env python3
# SUIPLUS first-install seed: region-named TUD inbounds + Addrs + admin/admin
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import random
import sqlite3
import string
import subprocess
import sys
import urllib.request
from pathlib import Path

DEFAULT_DB = "/usr/local/s-ui/db/s-ui.db"
# Never pre-bind a domain: each VPS sets its own later in panel settings.
DEFAULT_DOMAIN = ""
# Avoid 443/80/16122: many VPS uplinks drop them. Use high ports that already work on this fleet.
PORT_HY2 = 18443
PORT_TUIC = 18446
PORT_VLESS = 18445
PORT_ANYTLS = 45738
PORT_SS = 13495
CERT_DIR = Path("/usr/local/s-ui/cert")

REGION_CN = {
    "TW": "台湾", "HK": "香港", "JP": "日本", "KR": "韩国", "SG": "新加坡",
    "US": "美国", "GB": "英国", "DE": "德国", "FR": "法国", "AU": "澳洲",
    "CA": "加拿大", "NL": "荷兰", "RU": "俄罗斯", "IN": "印度", "VN": "越南",
    "TH": "泰国", "MY": "马来", "PH": "菲律宾", "ID": "印尼", "MO": "澳门",
    "CN": "中国", "IE": "爱尔兰", "SE": "瑞典", "FI": "芬兰", "TR": "土耳其",
}


def rand_str(n: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(n))


def rand_uuid() -> str:
    import uuid
    return str(uuid.uuid4())


def public_ip() -> str:
    for url in (
        "https://api64.ipify.org",
        "https://ipv4.icanhazip.com",
        "https://ifconfig.me/ip",
    ):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                ip = r.read().decode().strip()
                if ip and " " not in ip and len(ip) < 46:
                    return ip
        except Exception:
            continue
    return ""


def detect_region(ip: str) -> str:
    try:
        with urllib.request.urlopen("https://www.cloudflare.com/cdn-cgi/trace", timeout=4) as r:
            for line in r.read().decode().splitlines():
                if line.startswith("loc="):
                    code = line.split("=", 1)[1].strip().upper()
                    if len(code) == 2 and code.isalpha():
                        return code
    except Exception:
        pass
    for url in (
        f"https://ipapi.co/{ip}/country/" if ip else "",
        f"https://ipinfo.io/{ip}/country" if ip else "",
    ):
        if not url:
            continue
        try:
            with urllib.request.urlopen(url, timeout=4) as r:
                code = r.read().decode().strip().upper()
                if len(code) == 2 and code.isalpha():
                    return code
        except Exception:
            continue
    return "UN"


def region_label(code: str) -> str:
    return REGION_CN.get(code.upper(), code.upper())


def pem_lines(pem: str) -> list[str]:
    return [ln for ln in pem.strip().splitlines() if ln]


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def reality_keypair() -> tuple[str, str]:
    sing = Path("/usr/local/s-ui/bin/sing-box")
    if sing.is_file():
        try:
            out = subprocess.check_output(
                [str(sing), "generate", "reality-keypair"],
                text=True,
                timeout=15,
            )
            priv = pub = ""
            for line in out.splitlines():
                if "PrivateKey" in line:
                    priv = line.split(":", 1)[1].strip()
                if "PublicKey" in line:
                    pub = line.split(":", 1)[1].strip()
            if priv and pub:
                return priv, pub
        except Exception:
            pass
    try:
        from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

        priv_key = X25519PrivateKey.generate()
        priv = b64url(priv_key.private_bytes_raw())
        pub = b64url(priv_key.public_key().public_bytes_raw())
        return priv, pub
    except Exception:
        raw = os.urandom(32)
        return b64url(raw), b64url(hashlib.sha256(raw).digest()[:32])


def gen_self_signed(cn: str = "apple.com") -> tuple[str, str, str]:
    """Return (cert_pem, key_pem, cert_pubkey_sha256_b64)."""
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    key_path = CERT_DIR / f"{cn.replace('.', '_')}.key"
    crt_path = CERT_DIR / f"{cn.replace('.', '_')}.crt"
    subprocess.check_call(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path), "-out", str(crt_path),
            "-days", "3650", "-nodes", "-subj", f"/CN={cn}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    cert_pem = crt_path.read_text(encoding="utf-8")
    key_pem = key_path.read_text(encoding="utf-8")
    # SHA256 of SubjectPublicKeyInfo
    der = subprocess.check_output(
        ["openssl", "x509", "-in", str(crt_path), "-pubkey", "-noout"],
    )
    # convert PEM pubkey -> DER
    pub_der = subprocess.check_output(
        ["openssl", "pkey", "-pubin", "-outform", "DER"],
        input=der,
    )
    sha = base64.b64encode(hashlib.sha256(pub_der).digest()).decode()
    return cert_pem, key_pem, sha


def make_addrs(domain: str, ip: str, prefer: bool = False) -> list[dict]:
    """Install: IP only until domain bound. remark empty → subscribe name = inbound tag."""
    addrs: list[dict] = []
    if domain:
        addrs.append({"server": domain, "server_port": 0, "remark": ""})
    elif ip:
        addrs.append({"server": ip, "server_port": 0, "remark": ""})
    return addrs


def upsert_setting(cur: sqlite3.Cursor, key: str, value: str) -> None:
    cur.execute("SELECT 1 FROM settings WHERE key=?", (key,))
    if cur.fetchone():
        cur.execute("UPDATE settings SET value=? WHERE key=?", (value, key))
    else:
        cur.execute("INSERT INTO settings(key, value) VALUES(?, ?)", (key, value))


def jblob(obj):
    """Store JSON as SQLite BLOB so Go json.RawMessage can Scan it."""
    if isinstance(obj, memoryview):
        raw = obj.tobytes()
    elif isinstance(obj, (bytes, bytearray)):
        raw = bytes(obj)
    elif isinstance(obj, str):
        raw = obj.encode("utf-8")
    else:
        raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return sqlite3.Binary(raw)


def ensure_admin(cur: sqlite3.Cursor) -> None:
    # Only ensure username=admin here. Password must be set by `sui admin`
    # because packaged binaries may store bcrypt hashes while Login compares accordingly.
    cur.execute("SELECT id FROM users ORDER BY id LIMIT 1")
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE users SET username=? WHERE id=?", ("admin", row[0]))
    else:
        cur.execute("INSERT INTO users(username, password) VALUES(?, ?)", ("admin", "admin"))


def seed(db_path: str, domain: str, force: bool = False) -> int:
    path = Path(db_path)
    if not path.is_file():
        print(f"DB not found: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) AS c FROM inbounds")
    inbound_count = int(cur.fetchone()["c"])
    if inbound_count > 0 and not force:
        print("inbounds already present, skip seed (use --force to reset)")
        ensure_admin(cur)
        # Do NOT overwrite webDomain — operator binds domain manually per VPS
        conn.commit()
        return 0

    if force and inbound_count > 0:
        cur.execute("DELETE FROM clients")
        cur.execute("DELETE FROM inbounds")
        cur.execute("DELETE FROM tls")

    ip = public_ip()
    code = detect_region(ip)
    label = region_label(code)

    # TLS materials. Keep a Reality profile for the TLS page; VLESS still uses plain TLS
    # because Clash Meta Reality auth has been unreliable on this fleet.
    tls_cert, tls_key, tls_sha = gen_self_signed("www.microsoft.com")
    any_cert, any_key, any_sha = gen_self_signed("apple.com")

    tls_server = {
        "enabled": True,
        "server_name": "www.microsoft.com",
        "alpn": ["h3", "h2", "http/1.1"],
        "certificate": pem_lines(tls_cert),
        "key": pem_lines(tls_key),
    }
    tls_client = {
        "certificate_public_key_sha256": [tls_sha],
        "insecure": True,
        "server_name": "www.microsoft.com",
    }
    any_server = {
        "enabled": True,
        "server_name": "apple.com",
        "alpn": ["h2"],
        "certificate": pem_lines(any_cert),
        "key": pem_lines(any_key),
    }
    any_client = {
        "alpn": ["h2"],
        "certificate_public_key_sha256": [any_sha],
        "insecure": True,
        "server_name": "apple.com",
    }

    cur.execute(
        "INSERT INTO tls(name, server, client) VALUES(?,?,?)",
        ("TLS", jblob(tls_server), jblob(tls_client)),
    )
    tls_id = cur.lastrowid
    cur.execute(
        "INSERT INTO tls(name, server, client) VALUES(?,?,?)",
        ("AnyTLS-tls", jblob(any_server), jblob(any_client)),
    )
    any_id = cur.lastrowid

    # Reality profile (panel TLS page). Non-empty short_ids only — empty sid breaks Clash Meta.
    reality_priv, reality_pub = reality_keypair()
    short_id = "".join(random.choice("0123456789abcdef") for _ in range(8))
    reality_server = {
        "enabled": True,
        "server_name": "www.microsoft.com",
        "reality": {
            "enabled": True,
            "handshake": {"server": "www.microsoft.com", "server_port": 443},
            "private_key": reality_priv,
            "short_id": [short_id],
        },
    }
    reality_client = {
        "server_name": "www.microsoft.com",
        "reality": {"public_key": reality_pub, "short_id": short_id},
        "utls": {"enabled": True, "fingerprint": "chrome"},
    }
    cur.execute(
        "INSERT INTO tls(name, server, client) VALUES(?,?,?)",
        ("Reality", jblob(reality_server), jblob(reality_client)),
    )

    # credentials
    hy2_pwd = rand_str(12)
    hy2_obfs = rand_str(10)
    tuic_pwd = rand_str(12)
    tuic_uuid = rand_uuid()
    any_pwd = rand_str(10)
    ss_pwd = rand_str(10)
    vless_uuid = rand_uuid()

    # Seed never enables prefer; links use public IP until operator binds domain + turns prefer on
    link_host = ip or "127.0.0.1"
    addrs = make_addrs("", ip, prefer=False)

    specs = [
        {
            "type": "hysteria2",
            "tag": f"{label}-TUD-HY2",
            "tls_id": tls_id,
            "port": PORT_HY2,
            "options": {
                "listen": "::",
                "listen_port": PORT_HY2,
                "ignore_client_bandwidth": True,
                "obfs": {"type": "salamander", "password": hy2_obfs},
            },
            "out_json": {
                "type": "hysteria2",
                "tag": f"{label}-TUD-HY2",
                "server": link_host,
                "server_port": PORT_HY2,
                "obfs": {"type": "salamander", "password": hy2_obfs},
                "tls": {
                    "enabled": True,
                    "server_name": "www.microsoft.com",
                    "insecure": True,
                    "alpn": ["h3", "h2", "http/1.1"],
                    "certificate_public_key_sha256": [tls_sha],
                },
            },
        },
        {
            "type": "tuic",
            "tag": f"{label}-TUD-TUIC",
            "tls_id": tls_id,
            "port": PORT_TUIC,
            "options": {
                "listen": "::",
                "listen_port": PORT_TUIC,
                "congestion_control": "bbr",
            },
            "out_json": {
                "type": "tuic",
                "tag": f"{label}-TUD-TUIC",
                "server": link_host,
                "server_port": PORT_TUIC,
                "congestion_control": "bbr",
                "tls": {
                    "enabled": True,
                    "server_name": "www.microsoft.com",
                    "insecure": True,
                    "alpn": ["h3"],
                    "certificate_public_key_sha256": [tls_sha],
                },
            },
        },
        {
            "type": "anytls",
            "tag": f"{label}-TUD-AnyTls",
            "tls_id": any_id,
            "port": PORT_ANYTLS,
            "options": {
                "listen": "::",
                "listen_port": PORT_ANYTLS,
                "padding_scheme": [
                    "stop=8",
                    "0=30-30",
                    "1=100-400",
                    "2=400-500,c,500-1000,c,500-1000,c,500-1000,c,500-1000",
                    "3=9-9,500-1000",
                    "4=500-1000",
                    "5=500-1000,c,1000-4000",
                    "6=500-1000,500-2000,c,1000-2000,c,1000-2000",
                    "7=100-400",
                ],
            },
            "out_json": {
                "type": "anytls",
                "tag": f"{label}-TUD-AnyTls",
                "server": link_host,
                "server_port": PORT_ANYTLS,
                "tls": {
                    "enabled": True,
                    "server_name": "apple.com",
                    "insecure": True,
                    "alpn": ["h2"],
                    "certificate_public_key_sha256": [any_sha],
                },
            },
        },
        {
            "type": "shadowsocks",
            "tag": f"{label}-TUD-SS",
            "tls_id": 0,
            "port": PORT_SS,
            "options": {
                "listen": "::",
                "listen_port": PORT_SS,
                "method": "aes-256-gcm",
                "password": ss_pwd,
                "multiplex": {"enabled": True},
            },
            "out_json": {
                "type": "shadowsocks",
                "tag": f"{label}-TUD-SS",
                "server": link_host,
                "server_port": PORT_SS,
                "method": "aes-256-gcm",
            },
        },
        {
            "type": "vless",
            "tag": f"{label}-TUD-VLESS",
            # Use normal TLS (same as HY2). Reality + Clash Meta on this fleet keeps failing auth.
            "tls_id": tls_id,
            "port": PORT_VLESS,
            "options": {
                "listen": "::",
                "listen_port": PORT_VLESS,
            },
            "out_json": {
                "type": "vless",
                "tag": f"{label}-TUD-VLESS",
                "server": link_host,
                "server_port": PORT_VLESS,
                "tls": {
                    "enabled": True,
                    "server_name": "www.microsoft.com",
                    "insecure": True,
                    "alpn": ["h2", "http/1.1"],
                    "utls": {"enabled": True, "fingerprint": "chrome"},
                },
            },
        },
    ]

    inbound_ids: list[int] = []
    for sp in specs:
        # fix addrs server_port per inbound
        per_addrs = []
        for a in addrs:
            item = dict(a)
            item["server_port"] = sp["port"]
            per_addrs.append(item)
        cur.execute(
            "INSERT INTO inbounds(type, tag, tls_id, addrs, out_json, options) VALUES(?,?,?,?,?,?)",
            (
                sp["type"],
                sp["tag"],
                sp["tls_id"],
                jblob(per_addrs),
                jblob(sp["out_json"]),
                jblob(sp["options"]),
            ),
        )
        inbound_ids.append(int(cur.lastrowid))

    client_name = "default"
    client_cfg = {
        "hysteria2": {"name": client_name, "password": hy2_pwd},
        "tuic": {"name": client_name, "password": tuic_pwd, "uuid": tuic_uuid},
        "anytls": {"name": client_name, "password": any_pwd},
        "shadowsocks": {"name": client_name, "password": ss_pwd},
        "vless": {"name": client_name, "uuid": vless_uuid},
        "vmess": {"name": client_name, "uuid": rand_uuid(), "alterId": 0},
        "trojan": {"name": client_name, "password": rand_str(12)},
        "socks": {"username": client_name, "password": rand_str(10)},
        "http": {"username": client_name, "password": rand_str(10)},
        "mixed": {"username": client_name, "password": rand_str(10)},
        "naive": {"username": client_name, "password": rand_str(10)},
        "hysteria": {"name": client_name, "auth_str": rand_str(10)},
        "shadowsocks16": {"name": client_name, "password": base64.b64encode(os.urandom(16)).decode()},
        "shadowtls": {"name": client_name, "password": base64.b64encode(os.urandom(32)).decode()},
        "snell": {"name": client_name, "userkey": rand_str(32)},
    }
    cur.execute(
        """INSERT INTO clients(
            enable, name, config, inbounds, links, volume, expiry, down, up, "desc", "group",
            delay_start, auto_reset, reset_days, next_reset, total_up, total_down
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            1,
            client_name,
            jblob(client_cfg),
            jblob(inbound_ids),
            jblob([]),
            0,
            0,
            0,
            0,
            "",
            "",
            0,
            0,
            0,
            0,
            0,
            0,
        ),
    )

    ensure_admin(cur)
    # Leave domain empty for multi-VPS; operator binds manually in Settings
    upsert_setting(cur, "webDomain", "")
    upsert_setting(cur, "subDomain", "")
    for k, v in {
        "cfDdnsEnable": "false",
        "cfDdnsToken": "",
        "cfDdnsZone": "",
        "cfDdnsRecord": "",
        "cfDdnsInterval": "300",
        "cfDdnsProxied": "false",
        # 优选：默认关，绑域名后再开（不随 DDNS timer 重建 Argo）
        "suiplusPreferEnable": "false",
        "pppoeEnable": "false",
        "pppoeProviderDomain": "",
        "pppoeAccountId": "",
        "pppoePassword": "",
        "pppoeScheduleEnable": "false",
        "pppoeScheduleDays": "1",
        "pppoeScheduleTime": "03:00",
        "pppoeLastIp": "",
        "pppoePrevIp": "",
        "pppoeLastAt": "",
        "pppoeLastSuccessTs": "",
        "pppoeLastAutoFireDate": "",
        "pppoePending": "false",
        "argoAutoRebuild": "false",
        "argoRebuildCooldownSec": "1800",
        "argoLastRebuildTs": "",
        "argoLastRebuildAt": "",
        "argoDomain": "",
    }.items():
        upsert_setting(cur, k, v)

    conn.commit()
    conn.close()

    print(f"SUIPLUS seed OK: region={label}({code}) ip={ip} domain=(empty, bind later)")
    print(f"  inbounds={len(inbound_ids)} tags={[s['tag'] for s in specs]}")
    print("  addrs=IP-only; prefer=off; admin via: sui admin -username admin -password admin")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="SUIPLUS DB seed")
    p.add_argument("--db", default=os.environ.get("SUI_DB", DEFAULT_DB))
    p.add_argument(
        "--domain",
        default=os.environ.get("SUIPLUS_DOMAIN", DEFAULT_DOMAIN),
        help="Ignored for binding; kept for compat. Domain must be set in panel.",
    )
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    return seed(args.db, args.domain or "", force=args.force)


if __name__ == "__main__":
    sys.exit(main())
