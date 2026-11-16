from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Iterable

IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")

DEFAULT_IP_URLS = (
    "https://api64.ipify.org",
    "https://ipv4.icanhazip.com",
    "https://ifconfig.me/ip",
    "https://ip.sb",
    "https://checkip.amazonaws.com",
)


def _fetch(url: str, timeout: float = 5.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "cf-ddns/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace").strip()


def get_public_ipv4(urls: Iterable[str] | None = None, timeout: float = 5.0) -> str:
    """Return current public IPv4, trying multiple providers."""
    errors: list[str] = []
    for url in urls or DEFAULT_IP_URLS:
        try:
            text = _fetch(url, timeout=timeout)
            # some providers may return extra whitespace/newlines
            ip = text.split()[0] if text else ""
            if IPV4_RE.match(ip):
                return ip
            errors.append(f"{url}: invalid ip {text!r}")
        except (urllib.error.URLError, TimeoutError, ValueError, IndexError) as e:
            errors.append(f"{url}: {e}")
    raise RuntimeError("unable to detect public IPv4: " + "; ".join(errors))
