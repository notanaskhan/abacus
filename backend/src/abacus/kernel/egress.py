"""The one outbound HTTP client for connectors, and the egress allowlist it enforces (A-02-T16
security review M3, L10; ADR-040; ADR-150; Q-01's DNS Firewall is the network's copy).

The process configures the allowlist once at start-up from the write-capability registry
(`integrations.api.egress_allowlist()`, wired in `abacus.api.app` and the worker's
`__main__`); the kernel never imports a module. Until it is configured the allowlist is empty:
every request is refused (fail closed).

- `EgressClient.request` sends over HTTPS only, to an allowlisted host only, and never follows a
  redirect (a 3xx could leave the allowlist). Connectors get network access through it alone
  (CONN-001 forbids them HTTP libraries).
- `check_sign_in_url` holds a provider's sign-in URL to the same rule before it is handed to the
  browser: HTTPS to an allowlisted host, or the app's own origin (the demo ledger's local sign-in
  returns straight to the callback).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final
from urllib.parse import urlsplit

import httpx

from abacus.kernel.config import settings

_ALLOWED: set[str] = set()
TIMEOUT_SECONDS: Final = 20.0


class EgressRefused(Exception):
    """A request to a host or scheme the allowlist does not admit (names the host only)."""


def configure_egress(hosts: frozenset[str]) -> None:
    """Replace the allowlist (start-up; tests)."""
    _ALLOWED.clear()
    _ALLOWED.update(h.lower() for h in hosts)


def allowed_hosts() -> frozenset[str]:
    return frozenset(_ALLOWED)


def _host(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    if parts.username is not None or parts.password is not None:
        raise EgressRefused("credentials in the URL")
    return parts.scheme.lower(), (parts.hostname or "").lower()


def check_egress(url: str) -> None:
    scheme, host = _host(url)
    if scheme != "https" or host not in _ALLOWED:
        raise EgressRefused(host or "no host")


def check_sign_in_url(url: str) -> str:
    """The URL, if the browser may be sent there; `EgressRefused` otherwise."""
    scheme, host = _host(url)
    app = urlsplit(settings().app_base_url)
    own = host == (app.hostname or "").lower() and scheme == app.scheme.lower()
    if own and scheme in ("https", "http"):
        return url
    if scheme == "https" and host in _ALLOWED:
        return url
    raise EgressRefused(host or "no host")


class EgressClient:
    """HTTPS to allowlisted hosts, no redirects, a bounded timeout."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(follow_redirects=False, timeout=TIMEOUT_SECONDS)

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        check_egress(url)
        return await self._client.request(method, url, headers=headers, data=data)

    async def close(self) -> None:
        await self._client.aclose()
