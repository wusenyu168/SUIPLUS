#!/usr/bin/env python3
"""Dynamic IP redial (provider API) then refresh CF DDNS.

Provider-domain / account / password come from s-ui settings.
NOT the panel webDomain — pppoeProviderDomain is VPS vendor domain only.
Does NOT restart Argo / prefer tunnel.
"""
from __future__ import annotations

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

DB = os.environ.get("SUI_DB", "/usr/local/s-ui/db/s-ui.db")
LOG = Path("/var/log/suiplus-pppoe.log")
IP_WAIT_SEC = int(os.environ.get("PPPOE_IP_WAIT_SEC", "150"))
IP_POLL_SEC = int(os.environ.get("PPPOE_IP_POLL_SEC", "5"))
TIMEOUT = 30
POLL_TIMEOUT = 8


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


def main() -> int:
    if not Path(DB).is_file():
        log("error: no db")
        print(json.dumps({"ok": False, "msg": "no db"}, ensure_ascii=False))
        return 1
    s = settings(DB)
    if s.get("pppoeEnable", "false").lower() not in ("true", "1", "yes"):
        msg = "动态拨号未启用"
        log(f"skip: {msg}")
        print(json.dumps({"ok": False, "msg": msg}, ensure_ascii=False))
        return 1
    aid = (s.get("pppoeAccountId") or "").strip()
    pw = (s.get("pppoePassword") or "").strip()
    vendor = (s.get("pppoeProviderDomain") or "").strip()
    if not aid or not pw:
        msg = "请先填写账号 ID 和密码并保存"
        log(f"error: {msg}")
        print(json.dumps({"ok": False, "msg": msg}, ensure_ascii=False))
        return 1

    log(f"redial start vendor={vendor or '-'} id={aid[:3]}***")
    pre = show_ip(aid, pw, timeout=POLL_TIMEOUT)
    old_ip = ""
    if pre.get("status") == "success":
        old_ip = str(pre.get("ip") or "").strip()
    else:
        old_ip = (s.get("pppoeLastIp") or "").strip()

    result = change_ip(aid, pw)
    if result.get("status") != "success":
        msg = _sanitize_msg(str(result.get("msg") or "重拨失败"))
        log(f"changeip fail: {msg}")
        print(json.dumps({"ok": False, "msg": msg, "prev_ip": old_ip}, ensure_ascii=False))
        return 1

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
        # accept changeip-reported ip if any
        new_ip = str(result.get("ip") or "").strip()
    if not new_ip:
        msg = "重拨已提交但未检测到新 IP，请稍后点「立即重拨」或手动刷新 DDNS"
        log(f"warn: {msg} old={old_ip}")
        print(
            json.dumps(
                {"ok": False, "msg": msg, "prev_ip": old_ip, "last_ip": old_ip},
                ensure_ascii=False,
            )
        )
        return 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    upsert_settings(
        DB,
        {
            "pppoePrevIp": old_ip,
            "pppoeLastIp": new_ip,
            "pppoeLastAt": now,
        },
    )
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
        "last_at": now,
        "pppoePrevIp": old_ip,
        "pppoeLastIp": new_ip,
        "pppoeLastAt": now,
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"error: {e}")
        print(json.dumps({"ok": False, "msg": str(e)}, ensure_ascii=False))
        sys.exit(1)
