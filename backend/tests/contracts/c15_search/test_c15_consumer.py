"""P-02-T02 (TASK-7506; C15 v1, `docs/contracts/c15-search.md`; ADR-241): the consumer suite for
the search API, written from the contract. It runs in the provider's CI.

It asserts the shapes on the wire (three routes, one action each, 501 until P-02-T08), that
client roles, the agent, the system, the QI and break-glass support are refused, that every field
is classified, that search text travels only in a POST body, and that nothing anywhere in the
schema names, counts or hints at a row hidden by a wall (DEC-43)."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel._flags import SEARCH_PALETTE
from abacus.kernel.classification import level_of, unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag
from abacus.modules.identity.api import RULES, AuthContext
from abacus.modules.platform import api as platform_api
from abacus.modules.platform.search import contract, routes

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])

ROUTES: list[tuple[str, str, str]] = [
    ("post", "/v1/search", "search.read"),
    ("get", "/v1/search/recents", "search.read"),
    ("post", "/v1/search/recents", "search_recent.record"),
]
# Built by P-02-T08 (DEC-4614): no route is a stub any more.
UNBUILT: set[str] = set()  # P-02-T08 (DEC-4614): every route is served
MODELS: list[type[BaseModel]] = [
    v
    for v in vars(contract).values()
    if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == contract.__name__
]
FIRM_ROLES = (
    "firm_admin",
    "practice_leader",
    "quality_partner",
    "firm_partner",
    "firm_manager",
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "eqr_reviewer",
    "specialist",
    "client_service",
)
REFUSED = ("client_admin", "client_contributor", "agent", "system", "security_admin")


@pytest.mark.parametrize(("method", "path", "action"), ROUTES)
def test_every_route_declares_its_action_and_is_a_stub_until_built(
    method: str, path: str, action: str
) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == action
    assert ("501" in cast(Json, op["responses"])) is (path in UNBUILT)


def test_the_search_paths_are_exactly_the_contract() -> None:
    found = {(m, p) for p, ops in PATHS.items() if p.startswith("/v1/search") for m in ops}
    assert found == {(m, p) for m, p, _ in ROUTES}


def test_search_text_never_travels_in_a_url() -> None:
    for path, ops in PATHS.items():
        if not path.startswith("/v1/search"):
            continue
        for method, op in ops.items():
            params = cast(list[Json], op.get("parameters", []))
            names = {str(p["name"]) for p in params if p.get("in") in ("query", "path")}
            assert "q" not in names, (method, path)
    body = cast(Json, PATHS["/v1/search"]["post"]["requestBody"])
    assert "SearchQueryIn" in json.dumps(body)


def test_no_schema_names_or_counts_a_walled_row() -> None:
    for name, schema in SCHEMAS.items():
        if not name.startswith("Search"):
            continue
        properties = cast(Json, schema.get("properties", {}))
        for field in properties:
            assert "hidden" not in field and "wall" not in field, (name, field)
    assert "hidden_by_wall" not in json.dumps(DOC)


def test_total_visible_is_capped_at_99() -> None:
    total = cast(Json, cast(Json, SCHEMAS["SearchResultsOut"]["properties"])["total_visible"])
    assert total.get("maximum") == 99 and total.get("minimum") == 0


def test_every_field_is_classified_and_titles_are_confidential() -> None:
    assert MODELS
    for model in MODELS:
        assert unclassified_fields(model) == [], model.__name__
    for model, field in (
        (contract.SearchItemOut, "title"),
        (contract.SearchItemOut, "context"),
        (contract.SearchSuggestionOut, "title"),
        (contract.SearchQueryIn, "q"),
    ):
        assert level_of(model.model_fields[field]) == "confidential", (model.__name__, field)
    for model, field in (
        (contract.SearchItemOut, "object_id"),
        (contract.SearchItemOut, "match_ranges"),
        (contract.SearchResultsOut, "total_visible"),
    ):
        assert level_of(model.model_fields[field]) == "internal", (model.__name__, field)


@pytest.mark.parametrize("action", ["search.read", "search_recent.record"])
def test_firm_roles_are_allowed_and_everyone_else_refused(action: str) -> None:
    decisions = RULES[action].decisions
    for role in FIRM_ROLES:
        assert decisions.get(role) == "allow", (action, role)
    for role in REFUSED:
        assert decisions.get(role) != "allow", (action, role)
    for support in ("platform_support", "platform_support_content"):
        assert decisions.get(support) != "allow", (action, support)


def _ctx(*, client: bool = False, role: str = "manager") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        cast(Any, role),  # a firm role name stand-in
        None,
        client=client,
    )


def test_the_matrix_refuses_before_the_flag_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[str] = []

    class Refused(Exception):
        pass

    async def refuse(*_: object, **__: object) -> None:
        order.append("authorise")
        raise Refused

    async def enabled(_tenant: object, _flag: Flag) -> bool:
        order.append("flag")
        return True

    monkeypatch.setattr(routes, "authorise", refuse)
    monkeypatch.setattr(routes, "flag_enabled", enabled)
    with pytest.raises(Refused):
        asyncio.run(routes.gate(_ctx(client=True), "search.read"))
    assert order == ["authorise"]


def test_the_flag_off_is_404_and_on_lets_the_request_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def allowed(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr(routes, "authorise", allowed)
    for on in (False, True):

        async def enabled(_tenant: object, flag: Flag, _on: bool = on) -> bool:
            assert flag is SEARCH_PALETTE
            return _on

        monkeypatch.setattr(routes, "flag_enabled", enabled)
        if on:
            assert asyncio.run(routes.gate(_ctx(), "search.read")) is None
        else:
            with pytest.raises(NotFound):
                asyncio.run(routes.gate(_ctx(), "search.read"))


def test_the_registration_api_is_on_platform_api() -> None:
    for name in (
        "SearchProjection",
        "SearchIndexDocument",
        "RelatedParty",
        "SearchRegistrationInvalid",
        "register_search_projection",
        "search_projection",
        "search_projections",
        "SEARCH_GROUP_ORDER",
    ):
        assert hasattr(platform_api, name), name
    assert platform_api.SEARCH_GROUP_ORDER[:3] == ("clients", "returns", "audits")
    assert "actions" not in platform_api.SEARCH_GROUP_ORDER


def test_agent_mode_alone_may_send_empty_text() -> None:
    agents = contract.SearchQueryIn(q="", types=["agents"])
    assert agents.q == ""
    # Any other empty query is refused by the service with 422 `q_invalid` (P-02-T08); the model
    # keeps the cleaned text so the service can decide with the types in hand.
    assert contract.SearchQueryIn(q="   ").q == ""
