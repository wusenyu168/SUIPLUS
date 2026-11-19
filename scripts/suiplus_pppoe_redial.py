#!/usr/bin/env python3
"""Dynamic IP redial (provider API) then refresh CF DDNS.

Manual: anytime, but 5 minutes cooldown after a successful IP change.
Auto (--auto): N-day cycle + fixed HH:MM in panel timeLocation; skip if last
success within N days. When pppoePending, always try showip first.
Provider domain is VPS vendor domain (not panel webDomain). Does NOT touch Argo.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[misc, assignment]

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
LOG = Path("/var/log/suiplus-pppoe.log")
IP_WAIT_SEC = int(os.environ.get("PPPOE_IP_WAIT_SEC", "150"))
IP_POLL_SEC = int(os.environ.get("PPPOE_IP_POLL_SEC", "5"))
COOLDOWN_SEC = 300
SESSION_SEC = 72 * 3600
TIMEOUT = 30
POLL_TIMEOUT = 8
DEFAULT_TZ = "Asia/Shanghai"


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


def panel_tz_name(s: dict[str, str]) -> str:
    name = (s.get("timeLocation") or "").strip() or DEFAULT_TZ
    return name


def panel_tz(s: dict[str, str]):
    name = panel_tz_name(s)
    if ZoneInfo is None:
        return None
    try:
        return ZoneInfo(name)
    except Exception:
        try:
            return ZoneInfo(DEFAULT_TZ)
        except Exception:
            return None


def now_panel(s: dict[str, str]) -> datetime:
    tz = panel_tz(s)
    if tz is not None:
        return datetime.now(tz)
    return datetime.now()


def format_panel_now(s: dict[str, str]) -> str:
    return now_panel(s).strftime("%Y-%m-%d %H:%M:%S")


def _endpoint() -> str:
    parts = (
        b"aHR0cHM6Ly9s",
        b"aXNhaG9zdC5j",
        b"b20vaGluZXQu",
        b"cGhw",
    )
    return base64.b64decode(b"".join(parts)).decode("ascii")


def _sanitize_msg(msg: str) -> str:
    dirty = ("lisahost", "LisaHost", "hinet", "Hinet", "HiNet")
    out = msg
    for w in dirty:
        out = out.replace(w, "***")
    return out


def _call(action: str, account_id: str, password: str, timeout: float = TIMEOUT) -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {"a": action, "id": account_id, "pass": password}
    )
    url = _endpoint() + "?" + params
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "suiplus-pppoe/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"status": "error", "msg": "返回格式异常", "transient": False}
        if data.get("status") == "error" and "msg" in data:
            data = {
                **data,
                "msg": _sanitize_msg(str(data.get("msg") or "")),
                "transient": False,
            }
        return data
    except urllib.error.HTTPError as e:
        return {"status": "error", "msg": f"HTTP {e.code}", "transient": True}
    except urllib.error.URLError:
        return {"status": "error", "msg": "网络错误，请检查连接后重试", "transient": True}
    except TimeoutError:
        return {"status": "error", "msg": "请求超时，请稍后重试", "transient": True}
    except json.JSONDecodeError:
        return {"status": "error", "msg": "服务器返回非 JSON 内容", "transient": False}


def show_ip(account_id: str, password: str, *, timeout: float = TIMEOUT) -> dict[str, Any]:
    return _call("showip", account_id, password, timeout=timeout)


def change_ip(account_id: str, password: str) -> dict[str, Any]:
    return _call("changeip", account_id, password, timeout=TIMEOUT)


def run_ddns() -> None:
    script = Path(__file__).with_name("suiplus_cf_ddns.py")
    if not script.is_file():
        script = Path("/usr/local/s-ui/scripts/suiplus_cf_ddns.py")
    if script.is_file():
        subprocess.call([sys.executable, str(script)], timeout=120)
    addrs = Path(__file__).with_name("suiplus_sync_addrs.py")
    if not addrs.is_file():
        addrs = Path("/usr/local/s-ui/scripts/suiplus_sync_addrs.py")
    if addrs.is_file():
        subprocess.call([sys.executable, str(addrs)], timeout=180)


def last_success_ts(s: dict[str, str]) -> int:
    raw = (s.get("pppoeLastSuccessTs") or "").strip()
    if raw:
        try:
            return int(float(raw))
        except ValueError:
            pass
    # fallback: parse pppoeLastAt as panel timezone wall clock
    at = (s.get("pppoeLastAt") or "").strip()
    if at:
        tz = panel_tz(s)
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(at, fmt)
                if tz is not None:
                    dt = dt.replace(tzinfo=tz)
                return int(dt.timestamp())
            except ValueError:
                continue
    return 0


def parse_hhmm(raw: str) -> tuple[int, int] | None:
    text = (raw or "03:00").strip()
    parts = text.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h, m


def schedule_days(s: dict[str, str]) -> int:
    try:
        n = int(float(str(s.get("pppoeScheduleDays") or "1").strip()))
    except ValueError:
        n = 1
    return max(1, min(n, 365))


def fail(msg: str, *, code: int = 1, **extra: Any) -> int:
    log(f"skip/fail: {msg}")
    payload = {"ok": False, "msg": msg, **extra}
    print(json.dumps(payload, ensure_ascii=False))
    return code


def maybe_skip_auto(s: dict[str, str]) -> str | None:
    """Return skip reason or None to proceed. Times use panel timeLocation."""
    now = now_panel(s)
    tz_name = panel_tz_name(s)
    # #region agent log
    try:
        _dbg = {
            "sessionId": "28da0c",
            "runId": "tz-cooldown",
            "hypothesisId": "H1",
            "location": "suiplus_pppoe_redial.py:maybe_skip_auto",
            "message": "auto gate tz snapshot",
            "data": {
                "tzname_os": list(time.tzname),
                "timeLocation": tz_name,
                "panel_now": now.isoformat(sep=" ", timespec="seconds"),
                "local_now": datetime.now().isoformat(sep=" ", timespec="seconds"),
                "utc_now": datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
                "scheduleTime": (s.get("pppoeScheduleTime") or ""),
                "scheduleEnable": (s.get("pppoeScheduleEnable") or ""),
                "pppoeEnable": (s.get("pppoeEnable") or ""),
                "lastAutoFire": (s.get("pppoeLastAutoFireDate") or ""),
                "lastSuccessTs": (s.get("pppoeLastSuccessTs") or ""),
                "lastAt": (s.get("pppoeLastAt") or ""),
                "pending": (s.get("pppoePending") or ""),
                "scheduleDays": (s.get("pppoeScheduleDays") or ""),
            },
            "timestamp": int(time.time() * 1000),
        }
        log("DEBUG_JSON " + json.dumps(_dbg, ensure_ascii=False))
    except Exception:
        pass
    # #endregion
    if s.get("pppoeEnable", "false").lower() not in ("true", "1", "yes"):
        return "动态拨号未启用"
    if s.get("pppoeScheduleEnable", "false").lower() not in ("true", "1", "yes"):
        return "定时自动重拨未启用"
    hhmm = parse_hhmm(s.get("pppoeScheduleTime") or "03:00")
    if not hhmm:
        return "定时时刻格式无效（需要 HH:MM）"
    if (now.hour, now.minute) < hhmm:
        return (
            f"未到今日时刻 {hhmm[0]:02d}:{hhmm[1]:02d}"
            f"（面板时区 {tz_name} 现在 {now.strftime('%H:%M')}）"
        )
    today = now.strftime("%Y-%m-%d")
    if (s.get("pppoeLastAutoFireDate") or "").strip() == today:
        return "今日定时已执行过"
    last = last_success_ts(s)
    need = schedule_days(s) * 86400
    if last and (time.time() - last) < need:
        days = schedule_days(s)
        left = int(need - (time.time() - last))
        return f"周期内已换过 IP（设定 {days} 天，约剩余 {max(0, left)//3600} 小时）"
    return None


def cooldown_block(s: dict[str, str]) -> str | None:
    last = last_success_ts(s)
    if last and (time.time() - last) < COOLDOWN_SEC:
        left = int(COOLDOWN_SEC - (time.time() - last))
        return f"成功换 IP 后 5 分钟内不可重拨（剩余约 {left} 秒）"
    return None


def do_showip(s: dict[str, str]) -> int:
    """Fetch current provider IP; update last/prev when changed."""
    aid = (s.get("pppoeAccountId") or "").strip()
    pw = (s.get("pppoePassword") or "").strip()
    if not aid or not pw:
        return fail("请先填写账号 ID 和密码并保存")
    if s.get("pppoeEnable", "false").lower() not in ("true", "1", "yes"):
        return fail("动态拨号未启用")

    prev = (s.get("pppoePrevIp") or "").strip()
    last = (s.get("pppoeLastIp") or "").strip()
    pending = (s.get("pppoePending") or "").lower() in ("true", "1", "yes")
    check = show_ip(aid, pw, timeout=TIMEOUT)
    if check.get("status") != "success":
        msg = _sanitize_msg(str(check.get("msg") or "获取 IP 失败"))
        return fail(msg, pppoePrevIp=prev, pppoeLastIp=last, transient=bool(check.get("transient")), pppoePending=str(pending).lower())

    cur = str(check.get("ip") or "").strip()
    if not cur:
        return fail("获取 IP 为空", pppoePrevIp=prev, pppoeLastIp=last, pppoePending=str(pending).lower())

    now_ts = int(time.time())
    now = format_panel_now(s)
    kv: dict[str, str] = {"pppoeLastAt": now, "pppoePending": "false"}
    changed = bool(last and cur != last)
    if changed:
        kv["pppoePrevIp"] = last
        kv["pppoeLastIp"] = cur
        # Keep existing session ts if already running; else start now
        if not last_success_ts(s):
            kv["pppoeLastSuccessTs"] = str(now_ts)
        prev, last = last, cur
        log(f"showip changed {prev} -> {last}; refreshing DDNS")
        upsert_settings(DB, kv)
        try:
            run_ddns()
        except Exception as e:
            log(f"ddns after showip: {e}")
        msg = f"IP 已更新 {prev} → {last}"
    else:
        if not last:
            kv["pppoeLastIp"] = cur
            last = cur
            if not last_success_ts(s):
                kv["pppoeLastSuccessTs"] = str(now_ts)
        upsert_settings(DB, kv)
        msg = f"当前 IP {cur}" + ("（未变化）" if last == cur and (prev or not pending) else "")
        if pending:
            msg = f"已确认 IP {cur}"

    out = {
        "ok": True,
        "msg": msg,
        "changed": changed,
        "pppoePrevIp": prev or (s.get("pppoePrevIp") or ""),
        "pppoeLastIp": last or cur,
        "pppoeLastAt": now,
        "pppoeLastSuccessTs": kv.get("pppoeLastSuccessTs") or (s.get("pppoeLastSuccessTs") or ""),
        "pppoePending": "false",
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


def do_redial(s: dict[str, str], *, auto: bool) -> int:
    aid = (s.get("pppoeAccountId") or "").strip()
    pw = (s.get("pppoePassword") or "").strip()
    vendor = (s.get("pppoeProviderDomain") or "").strip()
    if not aid or not pw:
        return fail("请先填写账号 ID 和密码并保存")

    cool = cooldown_block(s)
    if cool:
        return fail(cool)

    log(f"redial start auto={auto} vendor={vendor or '-'} id={aid[:3]}*** tz={panel_tz_name(s)}")
    pre = show_ip(aid, pw, timeout=POLL_TIMEOUT)
    old_ip = ""
    if pre.get("status") == "success":
        old_ip = str(pre.get("ip") or "").strip()
    else:
        old_ip = (s.get("pppoeLastIp") or "").strip()

    # Lock previous IP before changeip (survive panel disconnect); start session even without prev IP
    now_ts = int(time.time())
    now = format_panel_now(s)
    pre_kv: dict[str, str] = {
        "pppoePending": "true",
        "pppoeLastAt": now,
        "pppoeLastSuccessTs": str(now_ts),
    }
    if old_ip:
        pre_kv["pppoePrevIp"] = old_ip
    if auto:
        pre_kv["pppoeLastAutoFireDate"] = now_panel(s).strftime("%Y-%m-%d")
    upsert_settings(DB, pre_kv)

    result = change_ip(aid, pw)
    if result.get("status") != "success":
        msg = _sanitize_msg(str(result.get("msg") or "重拨失败"))
        return fail(msg, pppoePrevIp=old_ip, pppoeLastIp=(s.get("pppoeLastIp") or old_ip), pppoePending="true")

    new_ip = ""
    deadline = time.time() + IP_WAIT_SEC
    while time.time() < deadline:
        time.sleep(IP_POLL_SEC)
        check = show_ip(aid, pw, timeout=POLL_TIMEOUT)
        if check.get("status") != "success":
            continue
        cand = str(check.get("ip") or "").strip()
        if not cand:
            continue
        if old_ip and cand == old_ip:
            continue
        new_ip = cand
        break

    if not new_ip:
        new_ip = str(result.get("ip") or "").strip()
    if not new_ip:
        upsert_settings(
            DB,
            {
                "pppoePrevIp": old_ip,
                "pppoePending": "true",
                "pppoeLastAt": format_panel_now(s),
                "pppoeLastSuccessTs": str(now_ts),
            },
        )
        return fail(
            "重拨已提交但未检测到新 IP（换线断网正常）。网络恢复后将自动获取，或点「获取 IP」",
            pppoePrevIp=old_ip,
            pppoeLastIp=(s.get("pppoeLastIp") or old_ip),
            pppoePending="true",
            pppoeLastSuccessTs=str(now_ts),
            pppoeLastAt=format_panel_now(s),
        )

    now2 = format_panel_now(s)
    kv = {
        "pppoePrevIp": old_ip,
        "pppoeLastIp": new_ip,
        "pppoeLastAt": now2,
        "pppoeLastSuccessTs": str(now_ts),
        "pppoePending": "false",
    }
    if auto:
        kv["pppoeLastAutoFireDate"] = now_panel(s).strftime("%Y-%m-%d")
    upsert_settings(DB, kv)
    log(f"ip changed {old_ip or '-'} -> {new_ip}; refreshing DDNS")
    try:
        run_ddns()
    except Exception as e:
        log(f"ddns after redial: {e}")

    out = {
        "ok": True,
        "msg": f"重拨成功 {old_ip or '-'} → {new_ip}",
        "prev_ip": old_ip,
        "last_ip": new_ip,
        "last_at": now2,
        "pppoePrevIp": old_ip,
        "pppoeLastIp": new_ip,
        "pppoeLastAt": now2,
        "pppoeLastSuccessTs": str(now_ts),
        "pppoePending": "false",
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="SUIPLUS PPPoE redial")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Scheduled run: honor N-day cycle + HH:MM; skip quietly when not due",
    )
    parser.add_argument(
        "--showip",
        action="store_true",
        help="Only fetch current IP (for panel after network recovers)",
    )
    args = parser.parse_args()

    if not Path(DB).is_file():
        return fail("no db")

    s = settings(DB)
    if args.showip:
        return do_showip(s)
    if args.auto:
        # Pending after redial disconnect: always try fetch IP (ignore schedule gate)
        if (s.get("pppoePending") or "").lower() in ("true", "1", "yes"):
            log(f"auto pending showip tz={panel_tz_name(s)}")
            do_showip(s)
            s = settings(DB)
        reason = maybe_skip_auto(s)
        if reason:
            # exit 0 so timer does not look failed
            log(f"auto skip: {reason}")
            print(json.dumps({"ok": True, "skipped": True, "msg": reason}, ensure_ascii=False))
            return 0
        return do_redial(s, auto=True)

    if s.get("pppoeEnable", "false").lower() not in ("true", "1", "yes"):
        return fail("动态拨号未启用")
    return do_redial(s, auto=False)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"error: {e}")
        print(json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))
        sys.exit(1)
