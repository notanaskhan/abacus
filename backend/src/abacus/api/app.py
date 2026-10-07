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
from starlette.types import ASGIApp, Receive, Scope, Send

from abacus.kernel.config import settings
from abacus.kernel.error_tracking import configure_error_tracking, flush_errors, report
from abacus.kernel.errors import DomainConflict, NotFound, ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.telemetry import configure_tracing, shutdown_tracing
from abacus.kernel.temporal import payload_codec
from abacus.modules.agents import api as agents
from abacus.modules.connections import api as connections
from abacus.modules.engagements import api as engagements
from abacus.modules.evidence import api as evidence
from abacus.modules.identity import api as identity
from abacus.modules.requests import api as requests

ROUTERS = (
    identity.router,
    engagements.router,
    requests.router,
    connections.router,
    evidence.router,
    agents.router,
)
# What a validation error may say about each problem: never the submitted value (client content
# is hostile, AGENTS.md #8), never pydantic's internal context.
_ERROR_FIELDS = ("loc", "msg", "type")
_log = get_logger(__name__)


async def _forbidden(_request: Request, _exc: Exception) -> JSONResponse:
    # Which layer denied is logged by authorise, never told to the caller.
    return JSONResponse({"detail": "forbidden"}, status_code=403)


async def _not_found(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "not found"}, status_code=404)


async def _conflict(_request: Request, exc: Exception) -> JSONResponse:
    # The class's fixed code: nothing from the request or the database is echoed.
    return JSONResponse({"detail": cast(DomainConflict, exc).code}, status_code=409)


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


class _IgnoreInboundTrace:
    """Drop inbound W3C trace headers: every API request starts its own trace (TASK-013)."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = [
                (k, v) for k, v in scope["headers"] if k not in (b"traceparent", b"tracestate")
            ]
            scope = {**scope, "headers": headers}
        await self._app(scope, receive, send)


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
    app = FastAPI(
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
    app.add_exception_handler(ServiceUnavailable, _unavailable)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(Exception, _unexpected)
    app.openapi = lambda: _openapi(app)  # type-safe override of FastAPI's generator
    # One server span per request, named by route template (TASK-013). The scrubbing exporter
    # keeps only route, method and status: never URL, query, client address or user agent.
    configure_tracing("abacus-api")
    configure_error_tracking("abacus-api")
    FastAPIInstrumentor.instrument_app(app, exclude_spans=["receive", "send"])
    # Added last, so it runs first: callers can't choose our trace IDs (audit rows record them).
    app.add_middleware(_IgnoreInboundTrace)
    return app
