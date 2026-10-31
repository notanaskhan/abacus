"""C9 v2 stub, taxonomy and mapping (A-03-T03; docs/contracts/ledger-mapping.md; SPEC-580 AC-16).

Every C9 v2 route exists with its one matrix action and documents 404 and 501; the v0 SPEC-316
routes keep their paths; the reserved adopt route is not mounted; every model field is classified;
no state but the A-09 reserved ones is offered as written; the gate answers clients 404 and reads
the flag only after authorising; the Granite Peak fixture answers its list and run.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.api.export_openapi import document
from abacus.kernel import _statuses
from abacus.kernel._flags import LEDGER_TB_MAPPING
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.assurance import tb_mapping_contract as contract
from abacus.modules.assurance import tb_mapping_fixtures as fx
from abacus.modules.identity.api import AuthContext, Forbidden

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
MS = "/v1/mapping-sets/{mapping_set_id}"
V2: dict[tuple[str, str], str] = {
    ("get", "/v1/grouping-sets/catalogue"): "grouping_set.read",
    (
        "get",
        "/v1/grouping-sets/{grouping_set_id}/versions/{version_no}/lines",
    ): "grouping_set.read",
    ("get", "/v1/engagements/{engagement_id}/mapping-sets"): "mapping_set.read",
    ("post", "/v1/engagements/{engagement_id}/mapping-sets"): "mapping_set.run",
    ("get", MS): "mapping_set.read",
    ("get", f"{MS}/run"): "mapping_set.read",
    ("put", f"{MS}/accounts/{{account_code}}"): "account_mapping.edit",
    ("post", f"{MS}/confirm"): "mapping_set.confirm",
    ("get", f"{MS}/trial-balance"): "mapping_set.read",
}
# A-03-T06 (TASK-2506): the catalogue and the picker are live.
LIVE = {
    ("get", "/v1/grouping-sets/catalogue"),
    ("get", "/v1/grouping-sets/{grouping_set_id}/versions/{version_no}/lines"),
    # A-03-T08: the mapping routes are live (fixtures first for the Granite Peak ids).
    ("get", "/v1/engagements/{engagement_id}/mapping-sets"),
    ("post", "/v1/engagements/{engagement_id}/mapping-sets"),
    ("get", "/v1/mapping-sets/{mapping_set_id}"),
    ("get", "/v1/mapping-sets/{mapping_set_id}/run"),
    ("put", "/v1/mapping-sets/{mapping_set_id}/accounts/{account_code}"),
    ("post", "/v1/mapping-sets/{mapping_set_id}/confirm"),
    ("get", "/v1/mapping-sets/{mapping_set_id}/trial-balance"),
}
V0: dict[tuple[str, str], str] = {
    ("get", "/v1/grouping-sets"): "grouping_set.import",
    ("post", "/v1/grouping-sets/imports"): "grouping_set.import",
    ("post", "/v1/grouping-sets/versions/{version_id}/publish"): "grouping_set.publish",
    # A-03-T06: the raw-body workbook or CSV import beside v0's JSON CSV import.
    ("post", "/v1/grouping-sets/imports/file"): "grouping_set.import",
}


def _ctx(*, client: bool = False, kind: str = "human") -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(uuid.uuid4(), kind, str(user)),  # type: ignore[arg-type] -- an agent or human probe
        user,
        uuid.uuid4(),
        None,
        None,
        client=client,
    )


@pytest.mark.parametrize(("method", "path"), sorted(V2))
def test_ac16_each_v2_route_declares_its_one_action_and_documents_404_and_501(
    method: str, path: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == V2[(method, path)]
    responses = set(cast(Json, operation["responses"]))
    assert "404" in responses
    assert ("501" in responses) is ((method, path) not in LIVE)


@pytest.mark.parametrize(("method", "path"), sorted(V0))
def test_ac16_the_v0_routes_keep_their_paths_and_actions(method: str, path: str) -> None:
    assert PATHS[path][method]["x-abacus-action"] == V0[(method, path)]


def test_ac16_the_reserved_adopt_route_is_declared_but_not_mounted() -> None:
    assert not [p for p in PATHS if p.endswith("/adopt") and "mapping" in p]
    with open(_doc(), encoding="utf-8") as handle:
        assert "/accounts/{account_code}/adopt" in handle.read()


def _doc() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parents[4] / "docs/contracts/ledger-mapping.md")


def test_ac16_every_field_is_classified() -> None:
    models = [
        v
        for v in vars(contract).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == contract.__name__
    ]
    assert models
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


def test_ac16_the_computed_status_words_and_the_reserved_states() -> None:
    assert [s.value for s in _statuses.MappingSetStatus] == [
        "in_progress",
        "prepared",
        "reviewed",
        "changed_after_sign_off",
    ]
    assert {"unmapped", "rule", "edited", "suggested", "adopted"} == {
        s.value for s in _statuses.AccountMappingStateStatus
    }


async def test_ac16_clients_404_and_a_refused_principal_never_learns_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(NotFound):
        await contract.firm_gate(_ctx(client=True), "grouping_set.read")

    async def get_ref(_ctx: AuthContext, _eid: uuid.UUID) -> object:
        return SimpleNamespace(resource=lambda: "engagement")

    async def deny(_ctx: AuthContext, action: str, _resource: object) -> None:
        raise Forbidden(action, "role")

    async def flag(_tenant: object, _flag: object) -> bool:
        raise AssertionError("the flag is read only after authorise")

    monkeypatch.setattr(contract, "get_ref", get_ref)
    monkeypatch.setattr(contract, "authorise", deny)
    monkeypatch.setattr(contract, "flag_enabled", flag)
    with pytest.raises(Forbidden):
        await contract.engagement_gate(_ctx(), "mapping_set.run", uuid.uuid4())


async def test_ac16_a_non_person_never_edits_or_confirms(monkeypatch: pytest.MonkeyPatch) -> None:
    async def allow(*_: object) -> None:
        return None

    monkeypatch.setattr(contract, "authorise", allow)
    for action in ("account_mapping.edit", "mapping_set.confirm"):
        with pytest.raises(Forbidden):
            await contract.firm_gate(_ctx(kind="agent"), action)


async def test_ac16_flag_off_404_then_the_granite_peak_fixture_or_the_live_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = {"on": False}

    async def get_ref(_ctx: AuthContext, _eid: uuid.UUID) -> object:
        return SimpleNamespace(resource=lambda: "engagement")

    async def allow(*_: object) -> None:
        return None

    async def flag(_tenant: object, asked: object) -> bool:
        assert asked is LEDGER_TB_MAPPING
        return state["on"]

    monkeypatch.setattr(contract, "get_ref", get_ref)
    monkeypatch.setattr(contract, "authorise", allow)
    monkeypatch.setattr(contract, "flag_enabled", flag)
    ctx = _ctx()
    with pytest.raises(NotFound):
        await contract.mapping_sets_route(fx.GRANITE_ENGAGEMENT, ctx)
    state["on"] = True
    page = await contract.mapping_sets_route(fx.GRANITE_ENGAGEMENT, ctx)
    assert page.total == 1
    tallies = page.items[0].tallies
    assert (tallies.accounts, tallies.mapped, tallies.need_review) == (128, 128, 0)
    assert (tallies.tb_balanced, tallies.tb_count) == (1, 1)
    run = await contract.mapping_run_route(fx.GRANITE_MAPPING, ctx)
    assert (run.run_status, run.run_done, run.run_total) == ("ready", 128, 128)
    # Past the fixtures, A-03-T08's live service answers (no 501).
    from abacus.modules.assurance import mapping_live

    called: list[str] = []

    async def live_set(*_: object, **__: object) -> object:
        called.append("mapping_set")
        return "live"

    async def live_sets(*_: object, **__: object) -> object:
        called.append("mapping_sets")
        return "live"

    monkeypatch.setattr(mapping_live, "mapping_set", live_set)
    monkeypatch.setattr(mapping_live, "mapping_sets", live_sets)
    assert await contract.mapping_set_route(fx.GRANITE_MAPPING, ctx) == "live"
    assert await contract.mapping_sets_route(uuid.uuid4(), ctx) == "live"
    assert called == ["mapping_set", "mapping_sets"]
