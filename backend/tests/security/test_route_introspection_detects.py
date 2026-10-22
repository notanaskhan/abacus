"""Q-02-T15: the generated route-introspection test catches what it is for. On small apps built
here, a route without an action, with an action outside the matrix, without its authentication,
or answering without a token off the public-route list is reported, as the generated cases for
`create_app()` would report it; a well-formed route is not."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel

from abacus.modules.identity.api import (
    ACTION_KEY,
    AbacusRoute,
    AbacusRouter,
    current_context,
)
from abacus_tools.codegen.security_tests import served

from .route_checks import openapi_problems, public_problems, route_problems


@pytest.fixture(autouse=True)
def engines() -> None:
    """These apps touch no database: this file needs no container."""


class _Out(BaseModel):
    ok: bool


async def _handler() -> _Out:
    return _Out(ok=True)


async def _plain() -> dict[str, str]:
    return {"status": "ok"}


def _app() -> FastAPI:
    """An app without FastAPI's own docs routes, as `create_app()` builds it. With them, `/docs`
    and `/openapi.json` would be reported: they answer without a token."""
    return FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def _bare_abacus_router() -> APIRouter:
    """A router of `AbacusRoute`s that skips `AbacusRouter`'s own refusals, as a hand-rolled
    router would."""
    return APIRouter(route_class=AbacusRoute)


def test_a_well_formed_route_has_no_problems() -> None:
    router = AbacusRouter()
    router.add_api_route(
        "/v1/x", _handler, action="engagement.create", response_model=_Out, methods=["POST"]
    )
    app = _app()
    app.include_router(router)
    guarded, unguarded = served(app)
    assert guarded == [("POST", "/v1/x", "engagement.create")]
    assert unguarded == []
    assert route_problems(app, "POST", "/v1/x", "engagement.create") == []
    assert openapi_problems(app, guarded) == []


def test_a_route_without_an_action_fails() -> None:
    router = _bare_abacus_router()
    router.add_api_route("/v1/x", _handler, methods=["GET"])
    app = _app()
    app.include_router(router)
    guarded, _ = served(app)
    assert guarded == [("GET", "/v1/x", "")]
    found = route_problems(app, "GET", "/v1/x", "")
    assert "GET /v1/x declares no action" in found
    assert any("is authenticated by []" in p for p in found)


def test_an_action_outside_the_matrix_fails() -> None:
    router = _bare_abacus_router()
    router.add_api_route(
        "/v1/x",
        _handler,
        methods=["GET"],
        response_model=_Out,
        dependencies=[Depends(current_context)],
        openapi_extra={ACTION_KEY: "made.up"},
    )
    app = _app()
    app.include_router(router)
    found = route_problems(app, "GET", "/v1/x", "made.up")
    assert found == ["GET /v1/x: 'made.up' is not a matrix action or route marker"]


def test_a_route_without_a_response_model_fails() -> None:
    router = _bare_abacus_router()
    router.add_api_route(
        "/v1/x",
        _plain,
        methods=["GET"],
        response_model=None,
        dependencies=[Depends(current_context)],
        openapi_extra={ACTION_KEY: "engagement.create"},
    )
    app = _app()
    app.include_router(router)
    assert route_problems(app, "GET", "/v1/x", "engagement.create") == [
        "GET /v1/x has no response model"
    ]


def test_a_route_outside_the_router_off_the_public_list_fails() -> None:
    app = _app()
    for method in ("GET", "POST"):
        app.add_api_route("/debug", _plain, methods=[method], operation_id=f"debug_{method}")
    guarded, unguarded = served(app)
    assert guarded == []
    assert unguarded == [("GET", "/debug"), ("POST", "/debug")]
    found = public_problems(app, unguarded)
    assert "GET /debug answers without a token and is not on the P-45 list" in found
    assert "POST /debug answers without a token and is not on the P-45 list" in found
    assert "/healthz is on the public-route list but not served" in found
    assert openapi_problems(app, guarded) == [
        "GET /debug is documented but not a generated route",
        "POST /debug is documented but not a generated route",
    ]


def test_a_public_path_answering_more_than_get_or_in_the_document_fails() -> None:
    app = _app()
    for method in ("GET", "POST"):
        app.add_api_route("/healthz", _plain, methods=[method], operation_id=f"healthz_{method}")
    app.add_api_route("/readyz", _plain, methods=["GET"], include_in_schema=False)
    _, unguarded = served(app)
    assert public_problems(app, unguarded) == [
        "GET /healthz: a public route stays out of the OpenAPI document",
        "POST /healthz: a public route answers GET only",
        "POST /healthz: a public route stays out of the OpenAPI document",
    ]
