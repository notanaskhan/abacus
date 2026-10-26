"""Bind each HTTP request's context for its audit events (G-02-T06; SPEC-349 AC-9).

Plain ASGI, inside the proxy-header middleware, so `scope["client"]` is already the client the
trusted load balancer named (never a header the caller wrote). Reads the peer address, the
User-Agent (reduced to a family and a device label from a closed list) and the staff session
cookie (kept only as its SHA-256), and binds them for the request (`kernel.request_context`).
"""

from __future__ import annotations

from http.cookies import CookieError, SimpleCookie

from starlette.types import ASGIApp, Receive, Scope, Send

from abacus.kernel.request_context import (
    RequestContext,
    bound,
    client_ip,
    cookie_sha256,
    device_of,
    session_cookie_name,
)


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return bytes(value).decode("latin-1")
    return None


def _session_cookie(scope: Scope) -> str | None:
    name = session_cookie_name()
    raw = _header(scope, b"cookie")
    if name is None or raw is None:
        return None
    try:
        jar = SimpleCookie(raw)
    except CookieError:
        return None
    morsel = jar.get(name)
    return cookie_sha256(morsel.value) if morsel is not None and morsel.value else None


class RequestContextCapture:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        client = scope.get("client")
        family, label = device_of(_header(scope, b"user-agent"))
        context = RequestContext(
            ip=client_ip(client[0] if client else None),
            user_agent_family=family,
            device_label=label,
            session_cookie_sha256=_session_cookie(scope),
        )
        with bound(context):
            await self.app(scope, receive, send)
