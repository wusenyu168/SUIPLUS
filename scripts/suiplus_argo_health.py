#!/usr/bin/env python3
"""Argo health: optional auto rebuild (default off) + manual --force.

Manual: --force → FORCE_ARGO_RESTART=1 sync_prefer (new SNI; clients must re-sub).
Auto: only when argoAutoRebuild=true AND tunnel unhealthy AND cooldown elapsed.
Never called from PPPoE redial.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
LOG = Path("/var/log/suiplus-argo-health.log")
ARGO_DIR = Path("/usr/local/s-ui/argo")
DOMAIN_FILE = ARGO_DIR / "argo_domain.txt"
DEFAULT_COOLDOWN = 1800  # 30 minutes


def log(msg: str) -> None:
    print(msg, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def settings(db: str) -> dict[str, str]:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM settings")
    out = {k: (v or "") for k, v in cur.fetchall()}
    conn.close()
    return out


def upsert_settings(db: str, kv: dict[str, str]) -> None:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    for k, v in kv.items():
        cur.execute("SELECT 1 FROM settings WHERE key=?", (k,))
        if cur.fetchone():
            cur.execute("UPDATE settings SET value=? WHERE key=?", (v, k))
        else:
            cur.execute("INSERT INTO settings(key, value) VALUES(?,?)", (k, v))
    conn.commit()
    conn.close()


def cloudflared_alive() -> bool:
    try:
        r = subprocess.run(
            ["pgrep", "-f", "cloudflared tunnel --url"],
            capture_output=True,
            timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def argo_domain() -> str:
    if not DOMAIN_FILE.is_file():
        return ""
    try:
        return DOMAIN_FILE.read_text(encoding="utf-8").strip().replace("\r", "").replace("\n", "")
    except OSError:
        return ""


def unhealthy() -> tuple[bool, str]:
    if not cloudflared_alive():
        return True, "cloudflared 未运行"
    dom = argo_domain()
    if not dom or "." not in dom:
        return True, "argo_domain.txt 无效"
    return False, f"ok {dom}"


def cooldown_sec(s: dict[str, str]) -> int:
    try:
        n = int(float(str(s.get("argoRebuildCooldownSec") or DEFAULT_COOLDOWN).strip()))
    except ValueError:
        n = DEFAULT_COOLDOWN
    return max(300, min(n, 86400))


def last_rebuild_ts(s: dict[str, str]) -> int:
    raw = (s.get("argoLastRebuildTs") or "").strip()
    if not raw:
        return 0
    try:
        return int(float(raw))
    except ValueError:
        return 0


def sync_script() -> Path:
    p = Path(__file__).with_name("suiplus_sync_prefer.py")
    if p.is_file():
        return p
    return Path("/usr/local/s-ui/scripts/suiplus_sync_prefer.py")


def run_force_rebuild() -> tuple[bool, str]:
    script = sync_script()
    if not script.is_file():
        return False, "缺少 suiplus_sync_prefer.py"
    env = os.environ.copy()
    env["FORCE_ARGO_RESTART"] = "1"
    try:
        r = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
    except Exception as e:
        return False, f"重建失败: {e}"
    out = ((r.stdout or "") + "\n" + (r.stderr or "")).strip()
    dom = argo_domain()
    ok = r.returncode == 0 and bool(dom) and cloudflared_alive()
    return ok, out[-800:] if out else ("prefer OK" if ok else "重建失败")


def emit(ok: bool, msg: str, **extra: object) -> int:
    payload = {"ok": ok, "msg": msg, **extra}
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="SUIPLUS Argo health / rebuild")
    parser.add_argument("--force", action="store_true", help="Manual rebuild (ignore auto switch)")
    parser.add_argument("--auto", action="store_true", help="Timer: rebuild only if enabled + unhealthy + cooldown")
    args = parser.parse_args()

    if not Path(DB).is_file():
        return emit(False, "no db")

    s = settings(DB)
    prefer_on = s.get("suiplusPreferEnable", "false").lower() in ("true", "1", "yes")
    auto_on = s.get("argoAutoRebuild", "false").lower() in ("true", "1", "yes")
    bad, reason = unhealthy()
    dom = argo_domain()

    if args.force:
        if not prefer_on:
            return emit(False, "请先开启「Argo默认+优选」并保存", argoDomain=dom)
        log(f"force rebuild (was unhealthy={bad} reason={reason})")
        ok, detail = run_force_rebuild()
        now = str(int(time.time()))
        if ok:
            upsert_settings(
                DB,
                {
                    "argoLastRebuildTs": now,
                    "argoLastRebuildAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "argoDomain": argo_domain(),
                },
            )
            return emit(
                True,
                f"Argo 已重建：{argo_domain()}（请重新订阅优选节点）",
                argoDomain=argo_domain(),
                argoLastRebuildTs=now,
                detail=detail[-200:],
            )
        return emit(False, f"Argo 重建失败：{detail[-200:]}", argoDomain=dom)

    if args.auto:
        if not prefer_on:
            log("auto skip: prefer off")
            return emit(True, "优选未启用", skipped=True)
        if not auto_on:
            log("auto skip: argoAutoRebuild=false")
            return emit(True, "自动重建未启用", skipped=True)
        if not bad:
            log(f"auto skip: healthy ({reason})")
            return emit(True, reason, skipped=True, argoDomain=dom)
        cool = cooldown_sec(s)
        last = last_rebuild_ts(s)
        if last and (time.time() - last) < cool:
            left = int(cool - (time.time() - last))
            log(f"auto skip: cooldown {left}s")
            return emit(True, f"冷却中（约 {left // 60} 分钟）", skipped=True)
        log(f"auto rebuild: {reason}")
        ok, detail = run_force_rebuild()
        now = str(int(time.time()))
        if ok:
            upsert_settings(
                DB,
                {
                    "argoLastRebuildTs": now,
                    "argoLastRebuildAt": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "argoDomain": argo_domain(),
                },
            )
            return emit(True, f"自动重建成功：{argo_domain()}", argoDomain=argo_domain(), rebuilt=True)
        return emit(False, f"自动重建失败：{detail[-200:]}")

    # status only
    return emit(not bad, reason, argoDomain=dom, unhealthy=bad)


if __name__ == "__main__":
    sys.exit(main())
