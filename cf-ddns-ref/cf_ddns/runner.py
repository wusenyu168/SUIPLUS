from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .cloudflare import CloudflareClient
from .config import load_config
from .ip import get_public_ipv4


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _log(path: str, message: str) -> None:
    line = f"[{_now()}] {message}"
    print(line, flush=True)
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _read_state(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8").strip()


def _write_state(path: str, ip: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(ip + "\n", encoding="utf-8")


def sync_once(config_path: str, force: bool = False) -> int:
    cfg = load_config(config_path)
    _log(cfg.log_file, f"start sync fqdn={cfg.fqdn} force={force}")

    ip = get_public_ipv4(cfg.ip_urls or None)
    last = _read_state(cfg.state_file)
    _log(cfg.log_file, f"public_ip={ip} last_ip={last or '-'}")

    client = CloudflareClient(cfg.api_token)
    zone_id = client.get_zone_id(cfg.zone)
    record = client.find_a_record(zone_id, cfg.fqdn)

    if record is None:
        created = client.create_a_record(
            zone_id, cfg.fqdn, ip, proxied=cfg.proxied, ttl=cfg.ttl
        )
        _write_state(cfg.state_file, ip)
        _log(cfg.log_file, f"created A {created.name} -> {created.content} proxied={created.proxied}")
        return 0

    if not force and record.content == ip and last == ip:
        _log(cfg.log_file, f"unchanged {cfg.fqdn} -> {ip}")
        return 0

    if record.content == ip and not force:
        _write_state(cfg.state_file, ip)
        _log(cfg.log_file, f"dns already {ip}, state refreshed")
        return 0

    updated = client.update_a_record(
        zone_id,
        record.id,
        cfg.fqdn,
        ip,
        proxied=cfg.proxied,
        ttl=cfg.ttl,
    )
    _write_state(cfg.state_file, ip)
    _log(
        cfg.log_file,
        f"updated A {updated.name}: {record.content} -> {updated.content} proxied={updated.proxied}",
    )
    return 0


def run_loop(config_path: str) -> int:
    cfg = load_config(config_path)
    interval = max(30, int(cfg.interval_seconds))
    _log(cfg.log_file, f"loop started interval={interval}s")
    while True:
        try:
            sync_once(config_path)
        except Exception as e:  # noqa: BLE001 - keep loop alive
            _log(cfg.log_file, f"ERROR {e}")
        time.sleep(interval)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cf-ddns", description="Cloudflare DDNS for dynamic VPS IP")
    p.add_argument(
        "-c",
        "--config",
        default=os_default_config(),
        help="path to config.yaml",
    )
    sub = p.add_subparsers(dest="cmd")

    once = sub.add_parser("once", help="run one sync")
    once.add_argument("--force", action="store_true", help="force update even if unchanged")

    sub.add_parser("loop", help="run forever using interval_seconds")
    sub.add_parser("version", help="print version")
    return p


def os_default_config() -> str:
    for candidate in (
        "/etc/cf-ddns/config.yaml",
        str(Path.cwd() / "config.yaml"),
        str(Path(__file__).resolve().parent.parent / "config.yaml"),
    ):
        if Path(candidate).is_file():
            return candidate
    return "/etc/cf-ddns/config.yaml"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    cmd = args.cmd or "once"
    try:
        if cmd == "version":
            from . import __version__

            print(__version__)
            return 0
        if cmd == "loop":
            return run_loop(args.config)
        return sync_once(args.config, force=bool(getattr(args, "force", False)))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
