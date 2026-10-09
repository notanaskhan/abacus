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
    ("POST", "/v1/walls"): "wall.create",
    ("POST", "/v1/walls/{wall_id}/remove"): "wall.remove",
    ("GET", "/v1/walls"): "wall.list",
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


# TASK-019: taking, releasing and assigning a review return the assignment, so 200.
REVIEW_QUEUE = "/v1/engagements/{engagement_id}/review-queue/{version_id}"
NOT_CREATING = {
    "/v1/walls/{wall_id}/remove",  # TASK-016: returns the removed wall, so 200
    REVIEW_QUEUE + "/take",
    REVIEW_QUEUE + "/release",
    REVIEW_QUEUE + "/assign",
    "/v1/knowledge/documents/{document_id}/withdraw",  # SPEC-009: returns the document, so 200
    "/v1/knowledge/search",  # SPEC-009: a query, nothing created
    "/v1/engagements/{engagement_id}/self-join",  # SPEC-013: returns the engagement, so 200
    "/v1/notifications/{notification_id}/read",  # SPEC-013: own read state
    "/v1/notifications/read-all",
    # SPEC-015: acceptance returns the engagement; revoke and resend return the invitation.
    "/v1/invitations/accept",
    "/v1/engagements/{engagement_id}/request-items/import/preview",  # SPEC-018: nothing stored
    "/v1/engagements/{engagement_id}/client-invitations/{invitation_id}/revoke",
    "/v1/engagements/{engagement_id}/client-invitations/{invitation_id}/resend",
    # SPEC-012: lifecycle changes return the session, so 200.
    "/v1/support/sessions/{session_id}/approve",
    "/v1/support/sessions/{session_id}/end",
    "/v1/support-sessions/{session_id}/approve",
    "/v1/support-sessions/{session_id}/revoke",
    "/v1/support-sessions/{session_id}/acknowledge",
}


def test_ac20_creating_routes_answer_201() -> None:
    posts = [r for r in _routes() if "POST" in _methods(r)]
    created = {r.path for r in posts if r.path != RETRIEVALS and r.path not in NOT_CREATING}
    decisions = "/v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/"
    assert created == {
        "/v1/engagements",
        "/v1/engagements/{engagement_id}/request-items",
        "/v1/walls",
        "/v1/methodology/templates/{name}/versions",  # SPEC-008: a template version
        "/v1/engagements/{engagement_id}/methodology",  # SPEC-008: items seeded
        "/v1/knowledge/documents",  # SPEC-009: a knowledge document
        "/v1/support/sessions",  # SPEC-012: a support session is requested
        "/v1/engagements/{engagement_id}/client-invitations",  # SPEC-015: an invitation
        "/v1/engagements/{engagement_id}/team",  # SPEC-017: a team member
        "/v1/engagements/{engagement_id}/request-items/import",  # SPEC-018: items created
        "/v1/engagements/{engagement_id}/request-items/{item_id}/uploads",  # SPEC-020: evidence
        decisions + "accept",  # TASK-019: a review decision is created
        decisions + "reject",
        decisions + "send-back",
    }
    assert all(r.status_code == 201 for r in posts if r.path in created)
    assert {r.path for r in posts if r.path in NOT_CREATING} == NOT_CREATING
    assert all(r.status_code in (None, 200) for r in posts if r.path in NOT_CREATING)


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


def test_ac11_production_starts_now_that_walls_are_enforced(production: None) -> None:
    # TASK-016: WALL_SAFE is True, so the gate lets `create_app` start in production.
    assert identity_api.WALL_SAFE is True
    try:
        assert create_app() is not None
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
