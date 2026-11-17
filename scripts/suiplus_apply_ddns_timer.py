#!/usr/bin/env python3
"""Rewrite systemd DDNS timer from settings.cfDdnsInterval (seconds).

Prefer/Argo is NOT touched here — DDNS interval only controls DNS refresh.
Default: 300 (5 minutes). Clamp: 60..86400.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
TIMER_DST = Path("/etc/systemd/system/suiplus-cf-ddns.timer")
DEFAULT_SEC = 300
MIN_SEC = 60
MAX_SEC = 86400


def interval_sec() -> int:
    sec = DEFAULT_SEC
    if Path(DB).is_file():
        try:
            conn = sqlite3.connect(DB)
            cur = conn.cursor()
            cur.execute("SELECT value FROM settings WHERE key=?", ("cfDdnsInterval",))
            row = cur.fetchone()
            conn.close()
            if row and str(row[0] or "").strip():
                sec = int(float(str(row[0]).strip()))
        except Exception:
            sec = DEFAULT_SEC
    if sec < MIN_SEC:
        sec = MIN_SEC
    if sec > MAX_SEC:
        sec = MAX_SEC
    return sec


def main() -> int:
    sec = interval_sec()
    # systemd accepts "300s" / "5min"
    body = f"""[Unit]
Description=SUIPLUS Cloudflare DDNS timer (interval from cfDdnsInterval)

[Timer]
OnBootSec=1min
OnUnitActiveSec={sec}s
AccuracySec=30s
Persistent=true
Unit=suiplus-cf-ddns.service

[Install]
WantedBy=timers.target
"""
    try:
        TIMER_DST.parent.mkdir(parents=True, exist_ok=True)
        TIMER_DST.write_text(body, encoding="utf-8")
    except OSError as e:
        print(f"apply_ddns_timer write fail: {e}")
        return 1
    try:
        subprocess.call(["systemctl", "daemon-reload"], timeout=60)
        # enable timer if unit exists; restart so new interval applies
        subprocess.call(["systemctl", "enable", "suiplus-cf-ddns.timer"], timeout=60)
        subprocess.call(["systemctl", "restart", "suiplus-cf-ddns.timer"], timeout=60)
    except Exception as e:
        print(f"apply_ddns_timer systemctl: {e}")
    print(f"apply_ddns_timer OK: OnUnitActiveSec={sec}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
