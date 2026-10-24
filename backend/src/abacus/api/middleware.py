"""HTTP edge middleware: size limits and trusted hosts (ADR-152, P-45; Q-01-T16). PROTECTED.

Plain ASGI, not `BaseHTTPMiddleware`, so a request is refused before its body is read or parsed.
Proxy headers are handled by uvicorn's `ProxyHeadersMiddleware` in `create_app()`, trusted only
from the peers in `proxy_trusted_hosts` (the load balancer). Nothing here reads `X-Forwarded-Host`:
the portal host is a branding hint only, and a tenant comes from membership or grant (INV-4).
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from typing import Final

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

JSON_BODY_LIMIT: Final = 1024 * 1024
_SAFE_METHODS: Final = frozenset({"GET", "HEAD", "OPTIONS"})

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


class BodyTooLarge(Exception):
    """A body grew past its limit while it was being read."""


def _header(scope: Scope, name: bytes) -> list[bytes]:
    return [v for k, v in scope["headers"] if k == name]


def _is_json(content_type: bytes | None) -> bool:
    if content_type is None:
        return True  # no declared type: the strict limit
    media = content_type.split(b";", 1)[0].strip().lower()
    return media == b"application/json" or media.endswith(b"+json")


class BodyLimit:
    """JSON bodies are refused past 1 MB and any other body (a raw upload) past `upload_bytes`
    (MAX_CONTENT_BYTES, 50 MB): on `Content-Length` before a byte is read, and by counting bytes
    for a body without one (chunked).

    The routes that take a file (`route_paths`) get `route_bytes` instead, a little over their own
    limit, so the route answers an oversize file with its catalogue code (422 `upload_too_large`,
    DEC-296) while it streams, and the edge still refuses anything far past it."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        upload_bytes: int,
        json_bytes: int = JSON_BODY_LIMIT,
        route_bytes: int | None = None,
        route_paths: re.Pattern[str] | None = None,
    ) -> None:
        self.app = app
        self._upload = upload_bytes
        self._json = json_bytes
        self._route_bytes = route_bytes
        self._route_paths = route_paths

    def _raw_limit(self, scope: Scope) -> int:
        paths, wider = self._route_paths, self._route_bytes
        if paths is not None and wider is not None and paths.fullmatch(str(scope.get("path"))):
            return max(wider, self._upload)
        return self._upload

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in _SAFE_METHODS:
            await self.app(scope, receive, send)
            return
        content_type = next(iter(_header(scope, b"content-type")), None)
        limit = self._json if _is_json(content_type) else self._raw_limit(scope)
        declared = _header(scope, b"content-length")
        if declared:
            try:
                length = int(declared[0])
            except ValueError:
                await _reject(send, 400, "bad request")
                return
            if length < 0:
                await _reject(send, 400, "bad request")
                return
            if length > limit:
                await _reject(send, 413, "payload too large")
                return

        seen = 0
        started = False

        async def counted() -> Message:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > limit:
                    raise BodyTooLarge
            return message

        async def tracked(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted, tracked)
        except BodyTooLarge:
            if started:
                raise
            await _reject(send, 413, "payload too large")


async def _reject(send: Send, status: int, detail: str) -> None:
    response = JSONResponse(
        {"detail": detail}, status_code=status, headers={"Connection": "close"}
    )
    await response({"type": "http"}, _no_receive, send)


async def _no_receive() -> Message:
    return {"type": "http.disconnect"}


class HostPolicy:
    """Which `Host` values are trusted: exact names, `*.suffix` names, `*` (everything), and IP
    addresses or CIDR networks (a load balancer probes a task by its IP)."""

    def __init__(self, patterns: Iterable[str]) -> None:
        self.any = False
        self.names: set[str] = set()
        self.suffixes: list[str] = []
        self.networks: list[IPNetwork] = []
        for raw in patterns:
            pattern = raw.strip().lower().rstrip(".")
            if pattern == "*":
                self.any = True
            elif pattern.startswith("*."):
                self.suffixes.append(pattern[1:])
            else:
                try:
                    self.networks.append(ipaddress.ip_network(pattern, strict=False))
                except ValueError:
                    self.names.add(pattern)

    def allows(self, host: str) -> bool:
        if self.any:
            return True
        name = _host_name(host)
        if not name:
            return False
        if name in self.names or any(name.endswith(suffix) for suffix in self.suffixes):
            return True
        try:
            address = ipaddress.ip_address(name)
        except ValueError:
            return False
        return any(
            address in network for network in self.networks if address.version == network.version
        )


def _host_name(value: str) -> str:
    """The host without its port, lower case and without a trailing dot."""
    host = value.strip().lower()
    if host.startswith("["):  # [::1]:8000
        end = host.find("]")
        return host[1:end] if end > 0 else ""
    if host.count(":") == 1:
        host = host.split(":", 1)[0]
    return host.rstrip(".")


class TrustedHosts:
    """A request whose `Host` is not trusted gets 400, before any route runs. A missing or
    repeated `Host` header is untrusted too."""

    def __init__(self, app: ASGIApp, *, allowed: Iterable[str]) -> None:
        self.app = app
        self._policy = HostPolicy(allowed)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        hosts = _header(scope, b"host")
        if len(hosts) == 1 and self._policy.allows(hosts[0].decode("latin-1")):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "http":
            await _reject(send, 400, "invalid host")
        else:
            await send({"type": "websocket.close", "code": 1008})


__all__ = ["JSON_BODY_LIMIT", "BodyLimit", "BodyTooLarge", "HostPolicy", "TrustedHosts"]
