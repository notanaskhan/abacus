"""The HTTP application (ADR-012). PROTECTED. TASK-007 design §6, TASK-008 design §3-6.

Every route comes from a module router built with `AbacusRouter`, so each one authenticates and
declares exactly one action. There are no unauthenticated routes: no docs UI and no served OpenAPI
document (the API client is generated from `app.openapi()` in code, ADR-013; `export_openapi`).
"""

from __future__ import annotations

from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from abacus.kernel.config import settings
from abacus.kernel.errors import NotFound
from abacus.kernel.logging import get_logger
from abacus.modules.engagements import api as engagements
from abacus.modules.identity import api as identity
from abacus.modules.requests import api as requests

ROUTERS = (identity.router, engagements.router, requests.router)
# What a validation error may say about each problem: never the submitted value (client content
# is hostile, AGENTS.md #8), never pydantic's internal context.
_ERROR_FIELDS = ("loc", "msg", "type")
_log = get_logger(__name__)


async def _forbidden(_request: Request, _exc: Exception) -> JSONResponse:
    # Which layer denied is logged by authorise, never told to the caller.
    return JSONResponse({"detail": "forbidden"}, status_code=403)


async def _not_found(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse({"detail": "not found"}, status_code=404)


async def _invalid(_request: Request, exc: Exception) -> JSONResponse:
    errors = cast(RequestValidationError, exc).errors()
    detail = [
        {key: cast(dict[str, object], error)[key] for key in _ERROR_FIELDS if key in error}
        for error in errors
    ]
    return JSONResponse({"detail": detail}, status_code=422)


async def _unexpected(_request: Request, exc: Exception) -> JSONResponse:
    # A fixed body: never an exception message, a driver error or a stack trace.
    _log.error("api.unexpected_error", error=type(exc).__name__)
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


def create_app() -> FastAPI:
    if settings().environment == "production" and not identity.WALL_SAFE:
        # Founder decision 2026-10-06: ethical walls (ADR-026) gate the first real firm.
        raise RuntimeError("ethical walls are not implemented: refusing to serve production")
    identity.token_verifier()  # a misconfigured identity provider fails here, not per request
    app = FastAPI(
        title="Abacus",
        version="1",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        generate_unique_id_function=_operation_id,
    )
    for router in ROUTERS:
        app.include_router(router)
    app.add_exception_handler(identity.Forbidden, _forbidden)
    app.add_exception_handler(NotFound, _not_found)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(Exception, _unexpected)
    app.openapi = lambda: _openapi(app)  # type-safe override of FastAPI's generator
    return app
