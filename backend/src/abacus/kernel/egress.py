"""The one outbound HTTP client for connectors, and the egress allowlist it enforces (A-02-T16
security review M3, L10 and round 2 L4; ADR-040; ADR-150; Q-01's DNS Firewall is the network's
copy; DEC-515, DEC-518).

The process configures the allowlist once at start-up from the write-capability registry
(`integrations.api.egress_allowlist()`, wired in `abacus.api.app` and the worker's
`__main__`); the kernel never imports a module. Until it is configured the allowlist is empty:
every request is refused (fail closed).

- `EgressClient.request` sends only reads (ADR-040, ED-156): GET or HEAD, or a POST to a
  provider path configured as a read (`read_posts`: a token exchange, a revoke). It parses the
  URL once (`httpx.URL`), checks that object and sends that
  object: HTTPS only, port 443 or none, no userinfo, an allowlisted host. It never follows a
  redirect (a 3xx could leave the allowlist), ignores proxy and certificate settings from the
  environment (`trust_env=False`), holds the whole request to one deadline and refuses a response
  larger than `MAX_RESPONSE_BYTES`. Connectors get network access through it alone (CONN-001
  forbids them HTTP libraries).
- `check_sign_in_url` holds a provider's sign-in URL to the same rule before it is handed to the
  browser: HTTPS to an allowlisted host, or the app's own origin (the demo ledger's local sign-in
  returns straight to the callback).

Per connector (DEC-518, follow-up DEC-582): the registry also gives each connector its own hosts
(`by_connector`). A client built for a connector (`EgressClient("quickbooks")`) and a sign-in URL
checked for one reach only that connector's hosts, so one provider's connector can't reach another
provider's host. A client or check that names no connector falls back to the union, which only
tests and the start-up export use: module code always names its connector (a source check in
`tests/unit/kernel/test_egress_per_connector.py`). Not here (DEC-518): a check of the resolved
address; the DNS Firewall holds that at the network.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

import httpx

from abacus.kernel.config import settings

_ALLOWED: set[str] = set()
# DEC-582: each connector's own hosts; a connector absent here reaches nothing.
_BY_CONNECTOR: dict[str, frozenset[str]] = {}
# ADR-040: connectors read. GET and HEAD to an allowlisted host; a POST only to a provider path
# declared as a read (a token exchange, a revoke), as (host, path). Anything else is refused
# before a byte leaves the process (ED-156).
_READ_METHODS: Final = frozenset({"GET", "HEAD"})
_READ_POSTS: set[tuple[str, str]] = set()
TIMEOUT_SECONDS: Final = 20.0
MAX_RESPONSE_BYTES: Final = 20 * 1024 * 1024


class EgressRefused(Exception):
    """A request to a host or scheme the allowlist does not admit (names the host only)."""


@dataclass(frozen=True)
class EgressResponse:
    status_code: int
    headers: Mapping[str, str]
    content: bytes


def configure_egress(
    hosts: frozenset[str],
    read_posts: frozenset[tuple[str, str]] = frozenset(),
    *,
    by_connector: Mapping[str, frozenset[str]] | None = None,
) -> None:
    """Replace the allowlist, each connector's own hosts and the provider read POSTs (start-up;
    tests). A connector's hosts outside `hosts` are dropped: the union stays the ceiling."""
    _ALLOWED.clear()
    _ALLOWED.update(h.lower() for h in hosts)
    _READ_POSTS.clear()
    _READ_POSTS.update((h.lower(), p) for h, p in read_posts)
    _BY_CONNECTOR.clear()
    for key, own in (by_connector or {}).items():
        _BY_CONNECTOR[key] = frozenset(h.lower() for h in own) & frozenset(_ALLOWED)


def allowed_hosts() -> frozenset[str]:
    return frozenset(_ALLOWED)


def _parsed(url: str | httpx.URL) -> httpx.URL:
    try:
        return url if isinstance(url, httpx.URL) else httpx.URL(url)
    except (httpx.InvalidURL, TypeError, ValueError):
        raise EgressRefused("not a URL") from None


def _hosts(connector: str | None) -> frozenset[str]:
    if connector is None:
        return frozenset(_ALLOWED)
    return _BY_CONNECTOR.get(connector, frozenset())


def _check(target: httpx.URL, connector: str | None = None) -> None:
    host = target.host.lower()
    if target.userinfo:
        raise EgressRefused("credentials in the URL")
    if target.scheme != "https" or target.port not in (None, 443) or host not in _hosts(connector):
        raise EgressRefused(host or "no host")


def check_egress(url: str | httpx.URL, connector: str | None = None) -> httpx.URL:
    """The parsed URL, if the connector (or, unnamed, any connector) may reach it;
    `EgressRefused` otherwise."""
    target = _parsed(url)
    _check(target, connector)
    return target


def check_sign_in_url(url: str, connector: str | None = None) -> str:
    """The URL, if the browser may be sent there for this connector; `EgressRefused` otherwise."""
    target = _parsed(url)
    app = httpx.URL(settings().app_base_url)
    own = (
        target.scheme == app.scheme
        and target.host.lower() == app.host.lower()
        and target.port == app.port
        and not target.userinfo
    )
    if own and target.scheme in ("https", "http"):
        return url
    _check(target, connector)
    return url


class EgressClient:
    """HTTPS to allowlisted hosts, no redirects, no environment proxies, a deadline, a size cap."""

    def __init__(self, connector: str | None = None) -> None:
        # Module code names its connector (DEC-582); unnamed is the union, for tests.
        self._connector = connector
        self._client = httpx.AsyncClient(
            follow_redirects=False, timeout=TIMEOUT_SECONDS, trust_env=False
        )

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        data: Mapping[str, str] | None = None,
    ) -> EgressResponse:
        target = check_egress(url, self._connector)  # checked once; this object is sent
        verb = method.upper()
        if verb not in _READ_METHODS and not (
            verb == "POST" and (target.host.lower(), target.path) in _READ_POSTS
        ):
            raise EgressRefused(f"{verb} is not a read")
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async with self._client.stream(
                method, target, headers=dict(headers or {}), data=dict(data) if data else None
            ) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise EgressRefused("response too large")
                return EgressResponse(response.status_code, dict(response.headers), bytes(body))

    async def close(self) -> None:
        await self._client.aclose()
