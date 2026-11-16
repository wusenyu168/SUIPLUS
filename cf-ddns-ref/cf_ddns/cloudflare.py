from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


API_BASE = "https://api.cloudflare.com/client/v4"


@dataclass
class DnsRecord:
    id: str
    name: str
    content: str
    type: str
    proxied: bool
    ttl: int


class CloudflareError(RuntimeError):
    pass


class CloudflareClient:
    def __init__(self, api_token: str, timeout: float = 15.0):
        self.api_token = api_token.strip()
        self.timeout = timeout
        if not self.api_token:
            raise ValueError("Cloudflare api_token is empty")

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = API_BASE + path
        data = None
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "cf-ddns/1.0",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            raise CloudflareError(f"HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise CloudflareError(str(e)) from e

        if not payload.get("success"):
            raise CloudflareError(json.dumps(payload.get("errors") or payload, ensure_ascii=False))
        return payload

    def get_zone_id(self, zone_name: str) -> str:
        q = urllib.parse.urlencode({"name": zone_name, "status": "active"})
        payload = self._request("GET", f"/zones?{q}")
        result = payload.get("result") or []
        if not result:
            raise CloudflareError(f"zone not found: {zone_name}")
        return result[0]["id"]

    def find_a_record(self, zone_id: str, name: str) -> DnsRecord | None:
        q = urllib.parse.urlencode({"type": "A", "name": name})
        payload = self._request("GET", f"/zones/{zone_id}/dns_records?{q}")
        result = payload.get("result") or []
        if not result:
            return None
        r = result[0]
        return DnsRecord(
            id=r["id"],
            name=r["name"],
            content=r["content"],
            type=r["type"],
            proxied=bool(r.get("proxied")),
            ttl=int(r.get("ttl") or 1),
        )

    def create_a_record(
        self,
        zone_id: str,
        name: str,
        ip: str,
        *,
        proxied: bool = False,
        ttl: int = 1,
    ) -> DnsRecord:
        payload = self._request(
            "POST",
            f"/zones/{zone_id}/dns_records",
            {
                "type": "A",
                "name": name,
                "content": ip,
                "ttl": ttl,
                "proxied": proxied,
            },
        )
        r = payload["result"]
        return DnsRecord(
            id=r["id"],
            name=r["name"],
            content=r["content"],
            type=r["type"],
            proxied=bool(r.get("proxied")),
            ttl=int(r.get("ttl") or 1),
        )

    def update_a_record(
        self,
        zone_id: str,
        record_id: str,
        name: str,
        ip: str,
        *,
        proxied: bool = False,
        ttl: int = 1,
    ) -> DnsRecord:
        payload = self._request(
            "PUT",
            f"/zones/{zone_id}/dns_records/{record_id}",
            {
                "type": "A",
                "name": name,
                "content": ip,
                "ttl": ttl,
                "proxied": proxied,
            },
        )
        r = payload["result"]
        return DnsRecord(
            id=r["id"],
            name=r["name"],
            content=r["content"],
            type=r["type"],
            proxied=bool(r.get("proxied")),
            ttl=int(r.get("ttl") or 1),
        )
