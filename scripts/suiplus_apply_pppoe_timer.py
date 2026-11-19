#!/usr/bin/env python3
"""Install/enable suiplus-pppoe.timer so --auto checks run (HH:MM + N days).

Timer always ticks; redial script no-ops when schedule/enable is off.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path("/usr/local/s-ui/scripts")
SVC_DST = Path("/etc/systemd/system/suiplus-pppoe.service")
TIMER_DST = Path("/etc/systemd/system/suiplus-pppoe.timer")


def main() -> int:
    src_dir = Path(__file__).resolve().parent
    if not (src_dir / "suiplus-pppoe.service").is_file():
        src_dir = SCRIPTS
    svc = src_dir / "suiplus-pppoe.service"
    timer = src_dir / "suiplus-pppoe.timer"
    if not svc.is_file() or not timer.is_file():
        print("apply_pppoe_timer: unit files missing")
        return 0
    try:
        SVC_DST.parent.mkdir(parents=True, exist_ok=True)
        SVC_DST.write_text(svc.read_text(encoding="utf-8"), encoding="utf-8")
        TIMER_DST.write_text(timer.read_text(encoding="utf-8"), encoding="utf-8")
    except OSError as e:
        print(f"apply_pppoe_timer write fail: {e}")
        return 1
    try:
        subprocess.call(["systemctl", "daemon-reload"], timeout=60)
        subprocess.call(["systemctl", "enable", "suiplus-pppoe.timer"], timeout=60)
        subprocess.call(["systemctl", "restart", "suiplus-pppoe.timer"], timeout=60)
    except Exception as e:
        print(f"apply_pppoe_timer systemctl: {e}")
    print("apply_pppoe_timer OK: OnUnitActiveSec=15min (script gates HH:MM + N days)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
