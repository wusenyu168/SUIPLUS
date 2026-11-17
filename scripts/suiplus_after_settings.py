#!/usr/bin/env python3
"""Panel settings-save hook (NOT used by DDNS timer).

Order:
  1) apply DDNS timer interval from cfDdnsInterval
  2) sync TUD addrs (domain/IP) — never starts/kills Argo
  3) sync prefer/Argo only when suiplusPreferEnable is on
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path("/usr/local/s-ui/scripts")


def run(name: str) -> int:
    p = SCRIPTS / name
    if not p.is_file():
        # allow running from repo checkout
        alt = Path(__file__).resolve().parent / name
        p = alt if alt.is_file() else p
    if not p.is_file():
        print(f"skip missing {name}")
        return 0
    return int(subprocess.call([sys.executable, str(p)]))


def main() -> int:
    rc = 0
    for script in (
        "suiplus_apply_ddns_timer.py",
        "suiplus_sync_addrs.py",
        "suiplus_sync_prefer.py",
    ):
        r = run(script)
        if r != 0:
            rc = r
    return rc


if __name__ == "__main__":
    sys.exit(main())
