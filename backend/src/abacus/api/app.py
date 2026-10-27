"""The HTTP application (ADR-012). PROTECTED. TASK-007 design §6, TASK-008 design §3-6.

Every route comes from a module router built with `AbacusRouter`, so each one authenticates and
declares exactly one action. The only unauthenticated routes are the ones on the public-route list
(`api/public_routes.py`, ADR-152): `/healthz` and `/readyz`. No docs UI and no served OpenAPI
document (the API client is generated from `app.openapi()` in code, ADR-013; `export_openapi`).
The HTTP edge is middleware: trusted hosts, body-size limits and proxy headers from the load
balancer only (`api/middleware.py`, P-45).
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from starlette.types import Receive, Scope, Send
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from abacus.api.middleware import BodyLimit, TrustedHosts
from abacus.api.public_routes import PUBLIC_ROUTES
from abacus.api.request_context import RequestContextCapture
from abacus.kernel.clock import check_startup as check_clock
from abacus.kernel.config import settings
from abacus.kernel.controls import ReadOnlyMode
from abacus.kernel.egress import configure_egress
from abacus.kernel.error_tracking import configure_error_tracking, flush_errors, report
from abacus.kernel.errors import (
    DomainConflict,
    DomainForbidden,
    DomainInvalid,
    DomainRateLimited,
    DomainTooLarge,
    DomainUnavailable,
    DomainUnsupported,
    NotFound,
    NotImplementedYet,
    ServiceUnavailable,
)
from abacus.kernel.logging import get_logger
from abacus.kernel.telemetry import configure_tracing, shutdown_tracing
from abacus.kernel.temporal import payload_codec
from abacus.modules import MODULES
from abacus.modules.audit_trail.api import events_for_work_item
from abacus.modules.evidence.api import (
    MAX_CONTENT_BYTES,
    UPLOAD_EDGE_BYTES,
    UPLOAD_ROUTE_PATHS,
    register_export_audit_trail,
)
from abacus.modules.identity import api as identity
from abacus.modules.integrations.api import (
    assert_egress_declared,
    egress_allowlist,
    egress_hosts_by_connector,
)

# A-01-T18 (SPEC-344, DEC-433): no module may import audit_trail, so the composition roots (this
# and the worker) give the engagement export its audit-trail reader.
register_export_audit_trail(events_for_work_item)

# Every module's routers, in MODULES order (P-39; F-03-T07): adding a router edits only that
# module's api.py.
ROUTERS = tuple(
    router
    for module in MODULES
    for router in importlib.import_module(f"abacus.modules.{module}.api").ROUTERS
)
# What a validation error may say about each problem: never the submitted value (client content
# is hostile, AGENTS.md #8), never pydantic's internal context.
_ERROR_FIELDS = ("loc", "msg", "type")
_log = get_logger(__name__)


async def _forbidden(request: Request, exc: Exception) -> JSONResponse:
    # Which layer denied is logged by authorise, never told to the caller. A walled person gets
    # the same answer as for a missing engagement, so a wall doesn't reveal it (SPEC-002 Q1); so
    # does a client user on another client's engagement (F-03 story 5.2, DEC-43).
    if isinstance(exc, identity.Forbidden) and exc.layer in ("wall", "client_scope"):
        return await _not_found(request, exc)
    return JSONResponse({"detail": "forbidden"}, status_code=403)


async def _not_found(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "not found"}, status_code=404)


def _coded(
    exc: DomainConflict
    | DomainInvalid
    | DomainForbidden
    | DomainRateLimited
    | DomainTooLarge
    | DomainUnsupported,
) -> dict[str, object]:
    # The class's fixed code and its identifier-only facts (ADR-139): nothing from the request or
    # the database is echoed as text.
    body: dict[str, object] = {"detail": exc.code}
    if exc.facts:
        body["facts"] = exc.facts
    return body


async def _domain_forbidden(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(_coded(cast(DomainForbidden, exc)), status_code=403)


async def _rate_limited(_request: Request, exc: Exception) -> JSONResponse:
    limited = cast(DomainRateLimited, exc)
    retry = limited.facts.get("retry_after")
    headers = {"Retry-After": str(retry)} if isinstance(retry, int) else None
    return JSONResponse(_coded(limited), status_code=429, headers=headers)


async def _conflict(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(_coded(cast(DomainConflict, exc)), status_code=409)


async def _domain_invalid(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(_coded(cast(DomainInvalid, exc)), status_code=422)


async def _too_large(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(_coded(cast(DomainTooLarge, exc)), status_code=413)


async def _unsupported(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(_coded(cast(DomainUnsupported, exc)), status_code=415)


async def _unavailable(_request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, DomainUnavailable):  # ED-170: a contract's fixed code
        return JSONResponse({"detail": exc.code}, status_code=503)
    return JSONResponse({"detail": "service unavailable"}, status_code=503)


async def _read_only(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "read_only"}, status_code=503)  # Q-01-T37


async def _not_implemented(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "not_implemented"}, status_code=501)


async def _invalid(_request: Request, exc: Exception) -> JSONResponse:
    errors = cast(RequestValidationError, exc).errors()
    detail = [
        {key: cast(dict[str, object], error)[key] for key in _ERROR_FIELDS if key in error}
        for error in errors
    ]
    return JSONResponse({"detail": detail}, status_code=422)


async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
    # A fixed body: never an exception message, a driver error or a stack trace.
    _log.error("api.unexpected_error", error=exc)
    route = request.scope.get("route")
    report(exc, route=getattr(route, "path", None))
    return JSONResponse({"detail": "internal error"}, status_code=500)


def _openapi(app: FastAPI) -> dict[str, object]:
    """The OpenAPI document, with the bearer scheme every route requires."""
    if app.openapi_schema is None:
        document = get_openapi(title=app.title, version=app.version, routes=app.routes)
        components = cast(dict[str, object], document.setdefault("components", {}))
        components["securitySchemes"] = {
            "bearer": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
        }
        document["security"] = [{"bearer": []}]
        app.openapi_schema = document
    return app.openapi_schema


def _operation_id(route: APIRoute) -> str:
    """Stable client function names: the endpoint's name without its `_route` suffix (unique)."""
    return route.name.removesuffix("_route")


_TRACE_HEADERS = (b"traceparent", b"tracestate")


class _Abacus(FastAPI):
    """The app, with inbound W3C trace headers removed before anything else runs (before the
    tracing instrumentation, which sits outside every middleware): each API request starts its
    own trace, so callers can't choose the trace IDs audit rows record (TASK-013). The scope is
    edited in place, so what the router sets on it (the route) stays visible to handlers."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope["headers"] = [(k, v) for k, v in scope["headers"] if k not in _TRACE_HEADERS]
        await super().__call__(scope, receive, send)


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    # A-02-T15 (ADR-040, ADR-150): no adapter may reach a host write-capabilities.yaml does not
    # declare for it; the API does not start while one would.
    assert_egress_declared()
    configure_egress(egress_allowlist(), by_connector=egress_hosts_by_connector())
    yield
    # Spans and error reports still buffered at shutdown are sent, not lost.
    shutdown_tracing()
    flush_errors()


def _add_edge_middleware(app: FastAPI) -> None:
    """Innermost first (the last one added is outermost): proxy headers are corrected for the
    trusted load balancer, then the Host is checked, then the body is bounded, then the request's
    audit context is bound (G-02-T06), from the corrected client address."""
    s = settings()
    app.add_middleware(RequestContextCapture)
    app.add_middleware(
        BodyLimit,
        upload_bytes=MAX_CONTENT_BYTES,
        route_bytes=UPLOAD_EDGE_BYTES,
        route_paths=UPLOAD_ROUTE_PATHS,
    )
    hosts = list(s.trusted_hosts or ())
    if s.portal_base_domain:
        hosts.append(f"*.{s.portal_base_domain}")  # portal hosts: a branding hint only (INV-4)
    app.add_middleware(TrustedHosts, allowed=hosts)
    if s.proxy_trusted_hosts:
        app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=list(s.proxy_trusted_hosts))


def create_app() -> FastAPI:
    if settings().environment == "production" and not identity.WALL_SAFE:
        # Founder decision 2026-10-06: ethical walls (ADR-026) gate the first real firm.
        raise RuntimeError("ethical walls are not implemented: refusing to serve production")
    check_clock()  # F-04-T02: no demo clock in production
    identity.token_verifier()  # a misconfigured identity provider fails here, not per request
    payload_codec()  # and so does a bad workflow payload key, before any run is recorded
    app = _Abacus(
        title="Abacus",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        generate_unique_id_function=_operation_id,
        lifespan=_lifespan,
    )
    for router in ROUTERS:
        app.include_router(router)
    # The public-route list, and nothing else, answers without a token (ADR-152). GET only, and
    # out of the OpenAPI document: these are not part of the API contract.
    for path, handler in PUBLIC_ROUTES.items():
        app.add_api_route(path, handler, methods=["GET"], include_in_schema=False)
    app.add_exception_handler(identity.Forbidden, _forbidden)
    app.add_exception_handler(NotFound, _not_found)
    app.add_exception_handler(DomainConflict, _conflict)
    app.add_exception_handler(DomainForbidden, _domain_forbidden)
    app.add_exception_handler(DomainRateLimited, _rate_limited)
    app.add_exception_handler(DomainInvalid, _domain_invalid)
    app.add_exception_handler(DomainTooLarge, _too_large)  # R-01-T09
    app.add_exception_handler(DomainUnsupported, _unsupported)  # R-01-T09
    app.add_exception_handler(ServiceUnavailable, _unavailable)
    app.add_exception_handler(ReadOnlyMode, _read_only)
    app.add_exception_handler(NotImplementedYet, _not_implemented)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(Exception, _unexpected)
    app.openapi = lambda: _openapi(app)  # type-safe override of FastAPI's generator
    _add_edge_middleware(app)
    # One server span per request, named by route template (TASK-013). The scrubbing exporter
    # keeps only route, method and status: never URL, query, client address or user agent.
    configure_tracing("abacus-api")
    configure_error_tracking("abacus-api")
    FastAPIInstrumentor.instrument_app(app, exclude_spans=["receive", "send"])
    return app
