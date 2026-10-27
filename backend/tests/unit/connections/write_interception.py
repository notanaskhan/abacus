"""The write-interception harness (ADR-040, ADR-150; A-02 AC-12.2; A-02-T19 extension).

Every outbound HTTP request any httpx client makes while the harness is active (the kernel's
`EgressClient`, the connectors' only client, or a client someone builds by hand) is caught at the
transport, recorded and answered locally: nothing reaches the network. `assert_read_only()` then
fails on any request that is not a read to a declared host:

- not HTTPS;
- to a host the write-capability registry does not declare;
- any method other than GET or HEAD, unless the exact (host, path) is an explicitly allowlisted
  provider read POST (an OAuth token exchange, a report query; ADR-040's enforcement line).

It lives under `tests/unit/connections/` beside the conformance suite (`make check` collects
`tests/unit`). A connector's test runs its reads inside `intercept()` and ends with
`assert_read_only()`; A-02-T26 runs the live ledger connector's recorded responses through it.
"""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field

import httpx
import pytest

READ_METHODS = frozenset({"GET", "HEAD"})
Responder = Callable[[httpx.Request], httpx.Response]


class WriteIntercepted(AssertionError):
    """An outbound request that is not a declared read (names method, host and path only)."""


@dataclass(frozen=True)
class Outbound:
    method: str
    scheme: str
    host: str
    path: str


def _ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={})


@dataclass
class Interceptor:
    declared_hosts: frozenset[str]
    read_posts: frozenset[tuple[str, str]] = frozenset()
    responder: Responder = _ok
    calls: list[Outbound] = field(default_factory=list[Outbound])

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(
            Outbound(
                request.method.upper(),
                request.url.scheme.lower(),
                (request.url.host or "").lower(),
                request.url.path,
            )
        )
        response = self.responder(request)
        response.request = request
        return response

    def violations(self) -> list[str]:
        found: list[str] = []
        for call in self.calls:
            where = f"{call.method} {call.scheme}://{call.host}{call.path}"
            if call.scheme != "https":
                found.append(f"not HTTPS: {where}")
            if call.host not in self.declared_hosts:
                found.append(f"undeclared host: {where}")
            if call.method not in READ_METHODS and (call.host, call.path) not in self.read_posts:
                found.append(f"write-shaped request: {where}")
        return found

    def assert_read_only(self) -> None:
        found = self.violations()
        if found:
            raise WriteIntercepted("; ".join(found))


@contextmanager
def intercept(
    monkeypatch: pytest.MonkeyPatch,
    declared_hosts: frozenset[str],
    *,
    read_posts: frozenset[tuple[str, str]] = frozenset(),
    responder: Responder = _ok,
) -> Generator[Interceptor]:
    """Catch every request at httpx's network transports for the block's duration."""
    harness = Interceptor(declared_hosts, read_posts, responder)

    async def handle_async(
        _self: httpx.AsyncHTTPTransport, request: httpx.Request
    ) -> httpx.Response:
        return harness.answer(request)

    def handle(_self: httpx.HTTPTransport, request: httpx.Request) -> httpx.Response:
        return harness.answer(request)

    with monkeypatch.context() as patch:
        patch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", handle_async)
        patch.setattr(httpx.HTTPTransport, "handle_request", handle)
        yield harness
