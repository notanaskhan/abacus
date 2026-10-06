"""AC-20: every route declares one action and checks it (TASK-007 contract, "Routing").

Action routes are exercised on `create_app()` with a probe router appended to
`abacus.api.app.ROUTERS`; the request context is replaced through `dependency_overrides`, so no
database is needed. Authentication failures (401) happen before any database access.
"""

from __future__ import annotations

import contextlib
import json
import uuid
from collections.abc import AsyncIterator, Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Protocol, cast

import httpx
import pytest
import yaml
from fastapi import Depends, FastAPI, HTTPException
from fastapi.routing import APIRoute
from pydantic import BaseModel
from sqlalchemy import Uuid, column

import abacus.api.app as app_module
from abacus.api import create_app
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import (
    ACTION_KEY,
    SELF,
    AbacusRoute,
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    configure_verifier,
    current_context,
    current_signed_in,
    declared_action,
    visible,
)
from abacus_tools.codegen import permission_matrix as pm
from abacus_tools.fakes.identity import FakeIdentityProvider

MATRIX = cast(
    dict[str, dict[str, str]],
    cast(dict[str, object], yaml.safe_load(pm.SOURCE.read_text()))["actions"],
)
VERBS = ["get", "post", "put", "patch", "delete"]
FORBIDDEN_WORDS = ("tenancy", "relationship", "attribute", "layer", "role")


class Ok(BaseModel):
    ok: bool


async def _handler() -> Ok:
    return Ok(ok=True)


# --- registration ------------------------------------------------------------------------------


@pytest.mark.parametrize("verb", VERBS)
def test_ac20_an_action_not_in_the_matrix_is_rejected_at_registration(verb: str) -> None:
    router = AbacusRouter(prefix="/v1/x")
    with pytest.raises(ValueError):
        getattr(router, verb)("/a", action="no.such_action", response_model=Ok)(_handler)


@pytest.mark.parametrize("verb", VERBS)
def test_ac20_a_missing_response_model_is_rejected_at_registration(verb: str) -> None:
    router = AbacusRouter(prefix="/v1/x")
    with pytest.raises(ValueError):
        getattr(router, verb)("/a", action="engagement.create", response_model=None)(_handler)


@pytest.mark.parametrize("verb", VERBS)
def test_ac20_a_route_without_an_action_is_rejected(verb: str) -> None:
    router = AbacusRouter(prefix="/v1/x")
    with pytest.raises(TypeError):
        getattr(router, verb)("/a", response_model=Ok)(_handler)


@pytest.mark.parametrize("verb", VERBS)
def test_ac20_a_route_without_a_response_model_argument_is_rejected(verb: str) -> None:
    router = AbacusRouter(prefix="/v1/x")
    with pytest.raises(TypeError):
        getattr(router, verb)("/a", action="engagement.create")(_handler)


def test_ac20_self_is_accepted_at_registration() -> None:
    router = AbacusRouter(prefix="/v1/x")
    router.get("/a", action=SELF, response_model=Ok)(_handler)
    [route] = router.routes
    assert isinstance(route, APIRoute)
    assert declared_action(route) == SELF


@pytest.mark.parametrize("action", sorted(MATRIX))
def test_ac20_every_matrix_action_can_be_declared(action: str) -> None:
    router = AbacusRouter(prefix="/v1/x")
    router.post("/a", action=action, response_model=Ok)(_handler)
    [route] = router.routes
    assert isinstance(route, APIRoute)
    assert declared_action(route) == action


@pytest.mark.parametrize("verb", VERBS)
def test_ac20_each_verb_registers_one_route_with_its_method_and_action(verb: str) -> None:
    router = AbacusRouter(prefix="/v1/x", tags=["probe"])
    getattr(router, verb)("/a", action="engagement.create", response_model=Ok)(_handler)
    [route] = router.routes
    assert isinstance(route, AbacusRoute)
    assert route.methods == {verb.upper()}
    assert route.path == "/v1/x/a"
    assert declared_action(route) == "engagement.create"
    assert route.openapi_extra is not None
    assert route.openapi_extra[ACTION_KEY] == "engagement.create"
    assert route.response_model is Ok


def test_ac20_status_code_is_passed_through() -> None:
    router = AbacusRouter(prefix="/v1/x")
    router.post("/a", action="engagement.create", response_model=Ok, status_code=201)(_handler)
    [route] = router.routes
    assert isinstance(route, APIRoute)
    assert route.status_code == 201


def test_ac20_the_decorator_returns_the_handler_unchanged() -> None:
    router = AbacusRouter(prefix="/v1/x")
    assert router.get("/a", action="engagement.create", response_model=Ok)(_handler) is _handler


@pytest.mark.parametrize(
    ("action", "auth"), [(SELF, current_signed_in), ("engagement.create", current_context)]
)
def test_ac20_every_route_gets_an_authentication_dependency(
    action: str, auth: Callable[..., object]
) -> None:
    router = AbacusRouter(prefix="/v1/x")
    router.get("/a", action=action, response_model=Ok)(_handler)
    [route] = router.routes
    assert isinstance(route, APIRoute)
    assert auth in [d.dependency for d in route.dependencies]


def test_ac20_websocket_routes_are_refused() -> None:
    router = AbacusRouter(prefix="/v1/x")
    with pytest.raises(TypeError):
        router.websocket("/ws")


def test_ac20_add_api_websocket_route_is_refused() -> None:
    router = AbacusRouter(prefix="/v1/x")
    with pytest.raises(TypeError):
        router.add_api_websocket_route("/ws", _handler)


def test_ac20_add_route_is_refused() -> None:
    router = AbacusRouter(prefix="/v1/x")
    with pytest.raises(TypeError):
        router.add_route("/plain", _handler)


# --- introspection of the real application -----------------------------------------------------


class _RouteContext(Protocol):
    """What FastAPI 0.142 exposes for a route reached through `include_router`."""

    @property
    def original_route(self) -> object: ...


class _Included(Protocol):
    def effective_route_contexts(self) -> Iterable[_RouteContext]: ...


def _routes() -> list[APIRoute]:
    """Every route of `create_app()`; newer FastAPI wraps included routers in `app.routes`."""
    found: list[APIRoute] = []
    for item in create_app().routes:
        if isinstance(item, APIRoute):
            found.append(item)
        elif hasattr(item, "effective_route_contexts"):
            for context in cast(_Included, item).effective_route_contexts():
                assert isinstance(context.original_route, APIRoute), context.original_route
                found.append(context.original_route)
        else:
            raise AssertionError(f"unexpected route type {type(item)}")
    return found


def test_ac20_the_app_has_routes() -> None:
    assert _routes()


def test_ac20_every_route_is_an_abacus_route() -> None:
    for route in _routes():
        assert isinstance(route, AbacusRoute), route.path


def test_ac20_every_route_declares_an_action_in_the_matrix_or_self() -> None:
    for route in _routes():
        action = declared_action(route)
        assert action is not None, route.path
        assert action == SELF or action in MATRIX, (route.path, action)


def test_ac20_self_is_used_only_on_v1_me() -> None:
    assert [r.path for r in _routes() if declared_action(r) == SELF] == ["/v1/me"]


def test_ac20_v1_me_exists_as_a_get() -> None:
    [me] = [r for r in _routes() if r.path == "/v1/me"]
    assert me.methods == {"GET"}


def test_ac20_every_route_has_a_response_model() -> None:
    for route in _routes():
        assert route.response_model is not None, route.path


def test_ac20_every_route_has_the_authentication_dependency() -> None:
    for route in _routes():
        dependencies = [d.dependency for d in route.dependencies]
        assert current_signed_in in dependencies or current_context in dependencies, route.path


def test_ac20_every_route_declares_exactly_one_action() -> None:
    for route in _routes():
        assert route.openapi_extra is not None
        assert isinstance(route.openapi_extra[ACTION_KEY], str), route.path


def test_ac20_there_are_no_docs_or_openapi_routes() -> None:
    paths = {r.path for r in _routes()}
    assert not {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"} & paths
    assert not [p for p in paths if "docs" in p or "openapi" in p or "redoc" in p]


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"])
async def test_ac20_docs_and_openapi_paths_are_not_served(path: str) -> None:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get(path)).status_code == 404


# --- authentication happens before anything else ------------------------------------------------


@pytest.fixture
async def anonymous() -> AsyncIterator[httpx.AsyncClient]:
    configure_verifier(FakeIdentityProvider().verifier())
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.parametrize("path", ["/v1/me"])
@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Bearer",
        "Bearer ",
        "Bearer garbage",
        "Basic dXNlcjpwYXNz",
        "garbage",
        "bearer a.b.c",
    ],
)
async def test_ac20_missing_or_invalid_bearer_token_is_401_with_www_authenticate(
    anonymous: httpx.AsyncClient, path: str, authorization: str | None
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = await anonymous.get(path, headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_ac20_token_from_another_provider_is_401(anonymous: httpx.AsyncClient) -> None:
    token = FakeIdentityProvider().token("someone")  # a different key
    response = await anonymous.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


# --- the guard on the declared action ----------------------------------------------------------

probe = AbacusRouter(prefix="/probe", tags=["probe"])


@probe.get("/checked", action="engagement.create", response_model=Ok)
async def _checked(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    await authorise(ctx, "engagement.create", Resource(ctx.tenant_id, None, False))
    return Ok(ok=True)


@probe.get("/unchecked", action="engagement.create", response_model=Ok)
async def _unchecked(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    return Ok(ok=True)


@probe.post("/unchecked-created", action="engagement.create", response_model=Ok, status_code=201)
async def _unchecked_created(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    return Ok(ok=True)


@probe.get("/wrong-action", action="firm.manage_settings", response_model=Ok)
async def _wrong_action(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    await authorise(ctx, "engagement.create", Resource(ctx.tenant_id, None, False))
    return Ok(ok=True)


@probe.get("/swallowed", action="engagement.update", response_model=Ok)
async def _swallowed(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    with contextlib.suppress(Forbidden):
        await authorise(ctx, "engagement.update", Resource(ctx.tenant_id, None, False))
    return Ok(ok=True)


@probe.get("/visible", action="engagement.read_metadata", response_model=Ok)
async def _visible(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    visible(ctx, "engagement.read_metadata", column("engagement_id", Uuid()))
    return Ok(ok=True)


@probe.get("/denied-role", action="engagement.update", response_model=Ok)
async def _denied_role(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    await authorise(ctx, "engagement.update", Resource(ctx.tenant_id, None, False))
    return Ok(ok=True)


@probe.get("/denied-tenancy", action="engagement.create", response_model=Ok)
async def _denied_tenancy(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    await authorise(ctx, "engagement.create", Resource(uuid.uuid4(), None, False))
    return Ok(ok=True)


@probe.get("/not-found", action="engagement.create", response_model=Ok)
async def _not_found(ctx: Annotated[AuthContext, Depends(current_context)]) -> Ok:
    raise HTTPException(404, "no such thing")


@probe.get("/self", action=SELF, response_model=Ok)
async def _self() -> Ok:
    return Ok(ok=True)


def _ctx(tenant_id: uuid.UUID | None = None) -> AuthContext:
    user_id = uuid.uuid4()
    return AuthContext(
        tenant=TenantContext(tenant_id or uuid.uuid4(), "human", str(user_id)),
        user_id=user_id,
        membership_id=uuid.uuid4(),
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC),
    )


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(app_module, "ROUTERS", (*app_module.ROUTERS, probe))
    app: FastAPI = create_app()
    ctx = _ctx()
    app.dependency_overrides[current_context] = lambda: ctx
    app.dependency_overrides[current_signed_in] = lambda: None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_ac20_a_checked_route_returns_its_response(client: httpx.AsyncClient) -> None:
    response = await client.get("/probe/checked")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_ac20_a_route_that_never_checks_its_action_is_a_500(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    capsys.readouterr()
    response = await client.get("/probe/unchecked")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}
    events = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    assert "authz.unchecked_route" in [e["event"] for e in events]


async def test_ac20_the_unchecked_routes_own_response_never_reaches_the_caller(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/probe/unchecked")
    assert "ok" not in response.text


async def test_ac20_an_unchecked_route_with_a_201_is_still_a_500(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/probe/unchecked-created")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}


async def test_ac20_checking_a_different_action_than_the_declared_one_is_a_500(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/probe/wrong-action")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}


async def test_ac20_a_route_that_swallows_forbidden_and_carries_on_is_a_500(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/probe/swallowed")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}


async def test_ac20_calling_visible_for_the_declared_action_counts_as_a_check(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/probe/visible")
    assert response.status_code == 200


async def test_ac20_an_error_response_from_an_unchecked_route_is_not_turned_into_a_500(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/probe/not-found")
    assert response.status_code == 404


async def test_ac20_a_self_route_needs_no_authorise_call(client: httpx.AsyncClient) -> None:
    response = await client.get("/probe/self")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.parametrize("path", ["/probe/denied-role", "/probe/denied-tenancy"])
async def test_ac20_forbidden_is_a_403_with_a_fixed_body(
    client: httpx.AsyncClient, path: str
) -> None:
    response = await client.get(path)
    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


@pytest.mark.parametrize("path", ["/probe/denied-role", "/probe/denied-tenancy"])
async def test_ac20_a_403_never_names_the_denying_layer(
    client: httpx.AsyncClient, path: str
) -> None:
    response = await client.get(path)
    text = (response.text + json.dumps(dict(response.headers))).lower()
    for word in FORBIDDEN_WORDS:
        assert word not in text, word


def test_ac20_probe_router_declares_the_expected_actions() -> None:
    declared = {declared_action(r) for r in probe.routes if isinstance(r, APIRoute)}
    assert declared == {
        "engagement.create",
        "firm.manage_settings",
        "engagement.read_metadata",
        "engagement.update",
        SELF,
    }


def test_ac20_pm_source_path_exists() -> None:
    assert Path(pm.SOURCE).is_file()
