"""The HTTP application (ADR-012). PROTECTED. TASK-007 design §6.

Every route comes from a module router built with `AbacusRouter`, so each one authenticates and
declares exactly one action. There are no unauthenticated routes: no docs UI and no served OpenAPI
document (the API client is generated from `app.openapi()` in code, ADR-013).
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from abacus.modules.identity import api as identity

ROUTERS = (identity.router,)


async def _forbidden(_request: Request, _exc: Exception) -> JSONResponse:
    # Which layer denied is logged by authorise, never told to the caller.
    return JSONResponse({"detail": "forbidden"}, status_code=403)


def create_app() -> FastAPI:
    app = FastAPI(title="Abacus", docs_url=None, redoc_url=None, openapi_url=None)
    for router in ROUTERS:
        app.include_router(router)
    app.add_exception_handler(identity.Forbidden, _forbidden)
    return app
