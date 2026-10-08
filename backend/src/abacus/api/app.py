"""The HTTP application (ADR-012). PROTECTED. TASK-007 design §6, TASK-008 design §3-6.

Every route comes from a module router built with `AbacusRouter`, so each one authenticates and
declares exactly one action. There are no unauthenticated routes: no docs UI and no served OpenAPI
document (the API client is generated from `app.openapi()` in code, ADR-013; `export_openapi`).
"""

from __future__ import annotations

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

from abacus.kernel.config import settings
from abacus.kernel.error_tracking import configure_error_tracking, flush_errors, report
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound, ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.telemetry import configure_tracing, shutdown_tracing
from abacus.kernel.temporal import payload_codec
from abacus.modules.agents import api as agents
from abacus.modules.connections import api as connections
from abacus.modules.engagements import api as engagements
from abacus.modules.evidence import api as evidence
from abacus.modules.identity import api as identity
from abacus.modules.notifications import api as notifications
from abacus.modules.platform import api as platform
from abacus.modules.requests import api as requests

ROUTERS = (
    identity.router,
    identity.staff_router,
    identity.firm_support_router,
    identity.invitation_router,
    engagements.router,
    engagements.methodology_router,
    engagements.firm_router,
    requests.router,
    requests.methodology_router,
    connections.router,
    evidence.router,
    agents.router,
    agents.graph_router,
    agents.knowledge_router,
    platform.router,
    notifications.router,
)
# What a validation error may say about each problem: never the submitted value (client content
# is hostile, AGENTS.md #8), never pydantic's internal context.
_ERROR_FIELDS = ("loc", "msg", "type")
_log = get_logger(__name__)


async def _forbidden(request: Request, exc: Exception) -> JSONResponse:
    # Which layer denied is logged by authorise, never told to the caller. A walled person gets
    # the same answer as for a missing engagement, so a wall doesn't reveal it (SPEC-002 Q1).
    if isinstance(exc, identity.Forbidden) and exc.layer == "wall":
        return await _not_found(request, exc)
    return JSONResponse({"detail": "forbidden"}, status_code=403)


async def _not_found(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "not found"}, status_code=404)


async def _conflict(_request: Request, exc: Exception) -> JSONResponse:
    # The class's fixed code: nothing from the request or the database is echoed.
    return JSONResponse({"detail": cast(DomainConflict, exc).code}, status_code=409)


async def _domain_invalid(_request: Request, exc: Exception) -> JSONResponse:
    # The class's fixed code, like a conflict: nothing from the request or the database is echoed.
    return JSONResponse({"detail": cast(DomainInvalid, exc).code}, status_code=422)


async def _unavailable(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "service unavailable"}, status_code=503)


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
    yield
    # Spans and error reports still buffered at shutdown are sent, not lost.
    shutdown_tracing()
    flush_errors()


def create_app() -> FastAPI:
    if settings().environment == "production" and not identity.WALL_SAFE:
        # Founder decision 2026-10-06: ethical walls (ADR-026) gate the first real firm.
        raise RuntimeError("ethical walls are not implemented: refusing to serve production")
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
    app.add_exception_handler(identity.Forbidden, _forbidden)
    app.add_exception_handler(NotFound, _not_found)
    app.add_exception_handler(DomainConflict, _conflict)
    app.add_exception_handler(DomainInvalid, _domain_invalid)
    app.add_exception_handler(ServiceUnavailable, _unavailable)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(Exception, _unexpected)
    app.openapi = lambda: _openapi(app)  # type-safe override of FastAPI's generator
    # One server span per request, named by route template (TASK-013). The scrubbing exporter
    # keeps only route, method and status: never URL, query, client address or user agent.
    configure_tracing("abacus-api")
    configure_error_tracking("abacus-api")
    FastAPIInstrumentor.instrument_app(app, exclude_spans=["receive", "send"])
    return app
