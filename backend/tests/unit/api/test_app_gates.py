"""AC-20: route introspection of the TASK-008 routes, the production walls gate and the new
exports (TASK-008 contract and revision 1)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, cast

import pytest
from fastapi.routing import APIRoute

import abacus.modules.engagements.api as engagements_api
import abacus.modules.identity.api as identity_api
import abacus.modules.requests.api as requests_api
from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.modules.identity.api import declared_action

EXPECTED = {
    ("POST", "/v1/engagements"): "engagement.create",
    ("GET", "/v1/engagements"): "engagement.read_metadata",
    ("GET", "/v1/engagements/{engagement_id}"): "engagement.read_metadata",
    ("POST", "/v1/engagements/{engagement_id}/request-items"): "request_item.create",
    ("GET", "/v1/engagements/{engagement_id}/request-items"): "request_item.read",
}


class _RouteContext(Protocol):
    @property
    def original_route(self) -> object: ...


class _Included(Protocol):
    def effective_route_contexts(self) -> Iterable[_RouteContext]: ...


RETRIEVALS = "/v1/engagements/{engagement_id}/retrievals"


def _routes() -> list[APIRoute]:
    found: list[APIRoute] = []
    for item in create_app().routes:
        if isinstance(item, APIRoute):
            found.append(item)
        elif hasattr(item, "effective_route_contexts"):
            for context in cast(_Included, item).effective_route_contexts():
                assert isinstance(context.original_route, APIRoute)
                found.append(context.original_route)
    return found


def _methods(route: APIRoute) -> set[str]:
    return set(route.methods or ())


def test_ac20_the_five_engagement_routes_exist_with_their_actions() -> None:
    actual = {
        (method, route.path): declared_action(route)
        for route in _routes()
        for method in _methods(route)
    }
    for key, action in EXPECTED.items():
        assert actual.get(key) == action, key


def test_ac20_each_new_route_declares_exactly_one_action_and_a_response_model() -> None:
    for route in _routes():
        if route.path.startswith("/v1/engagements"):
            assert declared_action(route) is not None
            assert route.response_model is not None


def test_ac20_creating_routes_answer_201() -> None:
    posts = [r for r in _routes() if "POST" in _methods(r)]
    created = {r.path for r in posts if r.path != RETRIEVALS}
    assert created == {"/v1/engagements", "/v1/engagements/{engagement_id}/request-items"}
    assert all(r.status_code == 201 for r in posts if r.path != RETRIEVALS)


def test_ac20_the_retrieval_routes_exist_with_their_actions_and_the_post_answers_202() -> None:
    actual = {
        (method, route.path): declared_action(route)
        for route in _routes()
        for method in _methods(route)
    }
    assert actual[("POST", RETRIEVALS)] == "evidence.upload"
    assert actual[("GET", RETRIEVALS + "/{sync_run_id}")] == "request_item.read"
    [post] = [r for r in _routes() if r.path == RETRIEVALS and "POST" in _methods(r)]
    assert post.status_code == 202
    assert post.response_model is not None


def test_ac20_self_is_still_used_only_on_v1_me() -> None:
    assert [r.path for r in _routes() if declared_action(r) == identity_api.SELF] == ["/v1/me"]


def test_ac20_the_new_module_exports_exist() -> None:
    for name in ("EngagementCreated", "EngagementRef", "get_ref", "lock_ref", "router"):
        assert hasattr(engagements_api, name), name
        assert name in engagements_api.__all__
    for name in ("RequestItemCreated", "router"):
        assert hasattr(requests_api, name), name
        assert name in requests_api.__all__


def test_ac20_identity_exports_add_creator_as_partner_and_not_add_engagement_member() -> None:
    assert callable(identity_api.add_creator_as_partner)
    assert "add_creator_as_partner" in identity_api.__all__
    assert not hasattr(identity_api, "add_engagement_member")
    assert "add_engagement_member" not in identity_api.__all__
    assert "WALL_SAFE" in identity_api.__all__


PRODUCTION_SETTINGS = {
    "DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "RELAY_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "IDENTITY_DATABASE_URL": "postgresql+asyncpg://u:p@h/d",
    "IDENTITY_ISSUER": "https://idp.example.test",
    "IDENTITY_AUDIENCE": "abacus-api",
    "IDENTITY_JWKS": '{"keys": []}',
    "S3_ENDPOINT_URL": "http://s3.example.test",
    "S3_ACCESS_KEY": "k",
    "S3_SECRET_KEY": "s",
    "TEMPORAL_TARGET": "t:7233",
    "TEMPORAL_PAYLOAD_KEY": "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs",
    "TEMPORAL_TLS": "true",
    "TEMPORAL_API_KEY": "test-temporal-api-key",
    "EVIDENCE_BUCKET": "test-evidence-bucket",
}


@pytest.fixture
def production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "production")
    for name, value in PRODUCTION_SETTINGS.items():
        monkeypatch.setenv(f"ABACUS_{name}", value)
    settings.cache_clear()


def test_ac20_production_refuses_to_start_while_walls_are_not_implemented(
    production: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(identity_api, "WALL_SAFE", False)
    try:
        with pytest.raises(RuntimeError):
            create_app()
    finally:
        settings.cache_clear()


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_non_production_environments_start_without_walls(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    settings.cache_clear()
    try:
        assert create_app() is not None
    finally:
        settings.cache_clear()
