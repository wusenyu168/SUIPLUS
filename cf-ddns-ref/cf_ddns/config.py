from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


@dataclass
class Config:
    api_token: str
    zone: str
    record: str
    proxied: bool = False
    ttl: int = 1
    interval_seconds: int = 120
    state_file: str = "/var/lib/cf-ddns/last_ip"
    log_file: str = "/var/log/cf-ddns.log"
    ip_urls: list[str] = field(default_factory=list)

    @property
    def fqdn(self) -> str:
        name = self.record.strip()
        zone = self.zone.strip().rstrip(".")
        if name in ("@", "", zone):
            return zone
        if name.endswith("." + zone) or name == zone:
            return name.rstrip(".")
        return f"{name}.{zone}"


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("config root must be a mapping")
        return data
    # minimal fallback parser for simple key: value files
    data: dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        key = k.strip()
        val = v.strip().strip("'\"")
        if val.lower() in ("true", "false"):
            data[key] = val.lower() == "true"
        elif val.isdigit():
            data[key] = int(val)
        else:
            data[key] = val
    return data


def load_config(path: str | Path) -> Config:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"config not found: {p}")
    raw = _load_yaml(p)

    api_token = str(raw.get("api_token") or os.environ.get("CF_API_TOKEN") or "").strip()
    zone = str(raw.get("zone") or "").strip()
    record = str(raw.get("record") or "@").strip()
    if not api_token:
        raise ValueError("api_token is required (or set CF_API_TOKEN)")
    if not zone:
        raise ValueError("zone is required (e.g. douyin.uk)")

    ip_urls = raw.get("ip_urls") or []
    if isinstance(ip_urls, str):
        ip_urls = [ip_urls]

    return Config(
        api_token=api_token,
        zone=zone,
        record=record,
        proxied=bool(raw.get("proxied", False)),
        ttl=int(raw.get("ttl") or 1),
        interval_seconds=int(raw.get("interval_seconds") or 120),
        state_file=str(raw.get("state_file") or "/var/lib/cf-ddns/last_ip"),
        log_file=str(raw.get("log_file") or "/var/log/cf-ddns.log"),
        ip_urls=[str(u) for u in ip_urls],
    )
