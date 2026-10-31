"""The sampling API stub (A-03-T02; docs/contracts/sampling.md; SPEC-580 AC-11, AC-12).

Every A-03 §4.3 sampling route exists with its one matrix action and documents 404 and 501; the
gate answers clients 404, authorises before reading the flag, answers 404 with the flag off and
501 with it on outside the Brightwater Hale fixture ids; every model field is classified; no
input carries a seed; the two status families are generated.
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
from abacus.kernel._flags import SAMPLING_SAMPLE_SETS
from abacus.kernel.classification import unclassified_fields
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.sampling import contract
from abacus.modules.sampling import contract_fixtures as fx

Json = dict[str, object]
DOC = cast(Json, json.loads(document()))
PATHS = cast(dict[str, dict[str, Json]], DOC["paths"])
WI = "/v1/work-items/{work_item_id}"
SS = "/v1/sample-sets/{sample_set_id}"
V = f"{SS}/versions/{{version_no}}"
ROUTES: dict[tuple[str, str], str] = {
    ("get", f"{WI}/sample-sets"): "sample_set.read",
    ("post", f"{WI}/sample-sets"): "sample_set.create",
    ("post", f"{WI}/populations"): "population.create",
    ("get", "/v1/populations/{population_id}"): "population.read",
    ("post", "/v1/populations/{population_id}/ties"): "population.create",
    ("post", f"{SS}/versions"): "sample_set.create",
    ("get", SS): "sample_set.read",
    ("get", f"{V}/draw"): "sample_set.read",
    ("get", f"{V}/items"): "sample_set.read",
    ("post", f"{V}/approve"): "sample_set.approve",
    ("get", f"{V}/export.xlsx"): "sample_set.export",
    ("post", f"{V}/item-requests/preview"): "sample_set.generate_requests",
    ("post", f"{V}/item-requests"): "sample_set.generate_requests",
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


# A-03-T07 made the population routes live and A-03-T10 the sample-set routes: they no longer
# answer 501 (the item-request fan-out stays a stub until A-03-T13).
SS = "/v1/sample-sets/{sample_set_id}"
LIVE = {
    ("post", f"{WI}/populations"),
    ("get", "/v1/populations/{population_id}"),
    ("post", "/v1/populations/{population_id}/ties"),
    ("get", f"{WI}/sample-sets"),
    ("post", f"{WI}/sample-sets"),
    ("post", f"{SS}/versions"),
    ("get", SS),
    ("get", f"{SS}/versions/{{version_no}}/draw"),
    ("get", f"{SS}/versions/{{version_no}}/items"),
    ("post", f"{SS}/versions/{{version_no}}/approve"),
    ("get", f"{SS}/versions/{{version_no}}/export.xlsx"),
}


@pytest.mark.parametrize(("method", "path"), sorted(ROUTES))
def test_ac11_each_sampling_route_declares_its_one_action_and_documents_404_and_501(
    method: str, path: str
) -> None:
    operation = PATHS[path][method]
    assert operation["x-abacus-action"] == ROUTES[(method, path)]
    responses = set(cast(Json, operation["responses"]))
    assert "404" in responses
    if (method, path) in LIVE:
        assert "501" not in responses
    else:
        assert "501" in responses


def test_ac11_the_family_is_exactly_these_routes() -> None:
    prefixes = ("/v1/populations", "/v1/sample-sets", f"{WI}/sample-sets", f"{WI}/populations")
    family = {(m, p) for p, ops in PATHS.items() if p.startswith(prefixes) for m in ops}
    assert family == set(ROUTES)


def test_ac11_draw_and_fan_out_take_an_idempotency_key_and_no_input_takes_a_seed() -> None:
    for path in (f"{SS}/versions", f"{V}/item-requests"):
        names = {p["name"] for p in cast(list[Json], PATHS[path]["post"]["parameters"])}
        assert "Idempotency-Key" in names, path
    for model in (contract.VersionIn, contract.ParametersIn, contract.SampleSetIn):
        assert not {f for f in model.model_fields if "seed" in f}, model


def test_ac11_every_field_is_classified() -> None:
    models = [
        v
        for v in vars(contract).values()
        if isinstance(v, type) and issubclass(v, BaseModel) and v.__module__ == contract.__name__
    ]
    assert models
    for model in models:
        assert unclassified_fields(model) == [], model.__name__


async def test_ac11_a_client_principal_gets_404_before_anything_else() -> None:
    with pytest.raises(NotFound):
        await contract.target_gate(_ctx(client=True), "sample_set.read")
    with pytest.raises(NotFound):
        await contract.work_item_gate(_ctx(client=True), "sample_set.read", uuid.uuid4())


async def test_ac11_a_work_item_route_authorises_on_its_engagement_then_reads_the_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    engagement_id = uuid.uuid4()

    async def engagement(_tenant: object, _wid: uuid.UUID) -> uuid.UUID:
        return engagement_id

    async def get_ref(_ctx: AuthContext, asked: uuid.UUID) -> object:
        assert asked == engagement_id
        return SimpleNamespace(resource=lambda: "engagement")

    async def authorise(_ctx: AuthContext, action: str, resource: object) -> None:
        calls.append(f"authorise:{action}:{resource}")

    async def off(_tenant: object, flag: object) -> bool:
        calls.append(f"flag:{getattr(flag, 'name', flag)}")
        return False

    monkeypatch.setattr(contract, "work_item_engagement", engagement)
    monkeypatch.setattr(contract, "get_ref", get_ref)
    monkeypatch.setattr(contract, "authorise", authorise)
    monkeypatch.setattr(contract, "flag_enabled", off)
    with pytest.raises(NotFound):
        await contract.work_item_gate(_ctx(), "sample_set.create", uuid.uuid4())
    assert calls == [
        "authorise:sample_set.create:engagement",
        f"flag:{SAMPLING_SAMPLE_SETS.name}",
    ]


async def test_ac11_a_target_write_refuses_a_non_person_and_authorises_its_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    async def authorise(_ctx: AuthContext, action: str, _resource: object) -> None:
        seen.append(action)

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(contract, "authorise", authorise)
    monkeypatch.setattr(contract, "flag_enabled", on)
    with pytest.raises(Forbidden):
        await contract.target_gate(_ctx(kind="agent"), "sample_set.approve")
    assert seen == []
    await contract.target_gate(_ctx(), "sample_set.approve")
    assert seen == ["sample_set.read"]
    # A-03-T10: the live approval refuses a non-person before any read; the service then
    # authorises on the set's own engagement.
    with pytest.raises(Forbidden):
        await contract.sample_set_approve_route(
            fx.PARTICIPANTS, 2, contract.ApproveIn(seen_hash="x"), _ctx(kind="agent")
        )


async def test_ac11_the_fixture_reads_answer_and_others_501(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def allow(*_: object) -> None:
        return None

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(contract, "authorise", allow)
    monkeypatch.setattr(contract, "flag_enabled", on)
    ctx = _ctx()
    approved = await contract.sample_set_route(fx.PARTICIPANTS, ctx)
    assert approved.status == _statuses.SampleSetVersionStatus.APPROVED
    assert approved.parameters.seed_hex == "0x5E2A91"
    assert approved.parameters.statistical_crosscheck_size == 22
    assert approved.population.record_count == 412
    assert [v.status for v in approved.versions] == ["approved", "superseded"]
    first = await contract.sample_items_route(fx.PARTICIPANTS, 2, ctx)
    assert [i.name for i in first.items[:5]] == [
        "Alicia Brennan",
        "Tomás Ibarra",
        "Priyanka Desai",
        "Gordon Whitfield",
        "Mei Tanaka",
    ]
    assert first.total == 25
    okoro = await contract.sample_items_route(fx.PARTICIPANTS, 2, ctx, q="Okoro")
    assert [(i.position, i.record_key) for i in okoro.items] == [(22, "NW-1158")]
    gl = await contract.sample_set_route(fx.GL_SAMPLE, ctx)
    assert [s.population_count for s in gl.strata] == [24, 1102, 786]
    assert gl.items_total == 40 and str(gl.items_amount) == "3698700.00"
    census = await contract.population_route(fx.CENSUS_V2, ctx)
    assert [t.result for t in census.ties] == ["tie", "tie"]
    # The fan-out is T13's: still 501 on every id.
    body = contract.ItemRequestsIn.model_validate(
        {"templates": [{"description": "Enrollment form"}], "due_on": "2026-10-01"}
    )
    with pytest.raises(NotImplementedYet):
        await contract.sample_item_requests_preview_route(uuid.uuid4(), 1, body, ctx)


def test_ac12_the_status_families_are_generated() -> None:
    assert [s.value for s in _statuses.SampleSetVersionStatus] == [
        "drawing",
        "draft",
        "approved",
        "superseded",
        "failed",
    ]
    assert [s.value for s in _statuses.CompletenessTieResultStatus] == ["tie", "off", "check"]


def test_ac11_the_flag_is_boolean_and_default_off() -> None:
    assert SAMPLING_SAMPLE_SETS.default == "false"
