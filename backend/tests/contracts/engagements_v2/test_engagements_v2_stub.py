"""The engagements family contract stub, v2 (P-07-T05; SPEC-321 AC-10 to AC-15): every route exists
with its one matrix action and answers 404 with `engagements.v2` off and 501 with it on; the
catalogue has no single_audit entry; the human-only actions deny agent and system; the v2 routes
sit beside the live ones without shadowing them. The consumers' own tests are P-07-T06's."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, cast

import pytest
import yaml
from fastapi.routing import APIRoute

from abacus.api import create_app
from abacus.api.export_openapi import document
from abacus.kernel._flags import ENGAGEMENTS_V2
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.engagements import contract
from abacus.modules.identity.api import AuthContext
from abacus.modules.identity.authz.matrix import RULES

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
SCHEMAS = cast(dict[str, Json], cast(Json, DOC["components"])["schemas"])
ERROR_CODES = Path(__file__).resolve().parents[4] / "docs" / "architecture" / "error-codes.yaml"
EID = "/v1/engagements/{engagement_id}"
DRAFT = "/v1/engagement-drafts/{draft_id}"
EXCLUDED = {"single_audit", "yellow_book", "pcaob_audit", "audit", "esg", "forensics"}

# (method, path) -> the one matrix action (P-07 §4.3).
ROUTES: dict[tuple[str, str], str] = {
    ("get", "/v1/engagements/index"): "engagement.read_metadata",
    ("get", f"{EID}/record"): "engagement.read_metadata",
    ("get", f"{EID}/gates"): "engagement.read_metadata",
    ("put", f"{EID}/letter/record"): "letter.record",
    ("get", "/v1/engagement-types"): "engagement.create",
    ("post", "/v1/engagement-drafts"): "engagement.create",
    ("get", DRAFT): "engagement.create",
    ("patch", DRAFT): "engagement.create",
    ("delete", DRAFT): "engagement.create",
    ("post", f"{DRAFT}/validate"): "engagement.create",
    ("post", f"{DRAFT}/start-acceptance"): "client.intake",
    ("post", f"{DRAFT}/create"): "engagement.create",
}
HUMAN_ONLY = {"engagement.create", "client.intake", "letter.record"}
# Live since P-07-T15 (index, record, gates, recorded letter) and P-07-T16 (catalogue, drafts,
# create); start-acceptance stays a stub until the acceptance record lands (P-07-T35, DEC-225).
LIVE = set(ROUTES) - {("post", f"{DRAFT}/start-acceptance")}
CLIENT_ROLES = {"client_admin", "client_contributor"}


def _props(schema: str) -> dict[str, Json]:
    return cast(dict[str, Json], SCHEMAS[schema]["properties"])


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac10_each_route_declares_its_action_and_the_stub_answer(method: str, path: str) -> None:
    op = PATHS[path][method]
    assert op["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, op["responses"]))
    assert "404" in responses
    assert ("501" in responses) == ((method, path) not in LIVE)


def test_ac10_create_takes_an_idempotency_key() -> None:
    params = cast(list[Json], PATHS[f"{DRAFT}/create"]["post"].get("parameters", []))
    keys = [p for p in params if p["name"] == "Idempotency-Key" and p["in"] == "header"]
    assert keys and keys[0]["required"] is True


def test_ac11_statuses_are_the_registry_enums() -> None:
    def ref(model: str, field: str) -> object:
        return _props(model)[field].get("$ref")

    for model in ("EngagementIndexRowOut", "EngagementRecordOut"):
        assert ref(model, "status") == "#/components/schemas/EngagementStatus"
    assert ref("EngagementLetterSummaryOut", "status") == "#/components/schemas/LetterRecordStatus"
    assert ref("EngagementLetterRecordOut", "status") == "#/components/schemas/LetterRecordStatus"


def test_ac11_the_catalogue_holds_eighteen_codes_and_no_single_audit() -> None:
    codes = set(cast(list[str], _props("EngagementTypeEntryOut")["code"]["enum"]))
    assert len(codes) == 18 and not codes & EXCLUDED
    types = set(cast(list[str], _props("EngagementTypeEntryOut")["engagement_type"]["enum"]))
    assert len(types) == 14 and not types & EXCLUDED  # C1's EngagementType, unchanged


def test_ac11_the_index_is_the_p36_envelope_with_a_summary() -> None:
    props = _props("EngagementIndexPage")
    assert {"items", "next_cursor", "total", "total_capped", "counts", "facets", "summary"} == set(
        props
    )
    assert not {p for p in props if "wall" in p or "hidden" in p}


@pytest.mark.parametrize("action", sorted(HUMAN_ONLY))
def test_ac12_human_only_actions_deny_agent_and_system(action: str) -> None:
    decisions = RULES[action].decisions
    assert decisions["agent"] == decisions["system"] == "deny"
    assert not {r for r in CLIENT_ROLES if decisions.get(r, "deny") != "deny"}


def test_ac12_client_intake_is_the_firm_admin_and_partners() -> None:
    granted = {r for r, d in RULES["client.intake"].decisions.items() if d != "deny"}
    assert granted == {"firm_admin", "firm_partner"}


async def test_ac13_flag_off_is_404_and_flag_on_is_501(monkeypatch: pytest.MonkeyPatch) -> None:
    user = uuid.uuid4()
    ctx = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)), user, uuid.uuid4(), None, None
    )
    seen: list[object] = []

    async def off(_tenant: object, flag: object) -> bool:
        seen.append(flag)
        return False

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await contract._stub(ctx)  # pyright: ignore[reportPrivateUsage] -- the stub gate
    assert seen == [ENGAGEMENTS_V2]
    monkeypatch.setattr(contract, "flag_enabled", on)
    with pytest.raises(NotImplementedYet):
        await contract._stub(ctx)  # pyright: ignore[reportPrivateUsage] -- the stub gate


class _RouteContext(Protocol):
    @property
    def original_route(self) -> object: ...


class _Included(Protocol):
    def effective_route_contexts(self) -> Iterable[_RouteContext]: ...


def _routes_in_order() -> list[APIRoute]:
    found: list[APIRoute] = []
    for item in create_app().routes:
        if isinstance(item, APIRoute):
            found.append(item)
        elif hasattr(item, "effective_route_contexts"):
            for context in cast(_Included, item).effective_route_contexts():
                assert isinstance(context.original_route, APIRoute)
                found.append(context.original_route)
    return found


def test_ac14_the_v2_index_is_matched_before_the_live_record_route() -> None:
    first = next(
        r
        for r in _routes_in_order()
        if "GET" in (r.methods or set()) and r.path_regex.match("/v1/engagements/index")
    )
    assert first.endpoint is contract.engagement_index_route


def test_ac14_the_live_engagement_routes_keep_their_shapes() -> None:
    def model(path: str, method: str) -> object:
        ok = cast(Json, cast(Json, PATHS[path][method]["responses"])["200"])
        return cast(Json, cast(Json, ok["content"])["application/json"])["schema"]

    assert model("/v1/engagements", "get") == {
        "type": "array",
        "items": {"$ref": "#/components/schemas/EngagementSummaryOut"},
        "title": "Response List Engagements",
    }
    assert model(EID, "get") == {"$ref": "#/components/schemas/EngagementOut"}
    assert PATHS[f"{EID}/letter"]["put"]["x-abacus-action"] == "letter.record"


def test_ac15_the_new_codes_are_in_the_catalogue() -> None:
    codes = cast(dict[str, Json], yaml.safe_load(ERROR_CODES.read_text())["codes"])
    assert codes["unknown_engagement_type"]["status"] == 422
    assert codes["letter_before_acceptance"]["status"] == 409
    assert codes["gate_unmet"]["status"] == 409
    assert codes["stale_version"]["status"] == 409
    assert codes["possible_duplicate"]["status"] == 409
