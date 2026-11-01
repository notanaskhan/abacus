# ac-test-author: ayushkbhatia
"""A-04-T16 (TASK-2904; ADR-078): independent acceptance tests for A-04-T04, T06 and T13 over
HTTP: INV-3 (walls and RLS), INV-4 (no client principal reaches a planning or workpaper route),
INV-5 (attribution) and the register's presumption and version rules.

Written from A-04 §3.1, §3.4 and §3.9, not from the builder's tests. The register's fixture is
A-04-T13's (its firm imports BH matrix v1 through K-02).
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from .tb_support import Books, Json, stranger_firm, without_independence
from .test_a04t13_risk_register import GRID, _create, _keyed, _patch, _path
from .test_a04t13_risk_register import world as register_world

pytestmark = pytest.mark.asyncio

world = register_world
READS: Final = (
    "/risks/register",
    "/risks/linkage",
    "/materiality/current",
    "/service-organizations",
    "/workpapers",
    "/procedures",
)


def _engagement(books_: Books, rest: str) -> str:
    return f"/v1/engagements/{books_.site.engagement_id}{rest}"


async def test_inv4_no_client_principal_reaches_a_planning_route(world: Books) -> None:
    client = await world.seed.client_contact(world.site)
    for path in READS:
        found = await world.call("GET", _engagement(world, path), client)
        assert found.status_code == 404, (path, found.status_code)


async def test_inv3_another_firm_never_sees_the_register(world: Books) -> None:
    await _create(world, *GRID[0])
    stranger = await stranger_firm(world.net)
    for path in READS:
        found = await world.call("GET", _engagement(world, path), stranger)
        assert found.status_code == 404, (path, found.status_code)


async def test_a_member_without_independence_is_refused(world: Books) -> None:
    who = await without_independence(world.seed, world.site)
    found = await world.call("GET", _path(world, "/register"), who)
    assert found.status_code == 403


async def test_inv5_a_created_risk_is_attributed_to_its_person(world: Books) -> None:
    risk = await _create(world, *GRID[1])
    actor = await world.seed.value(
        "SELECT actor_kind || ':' || actor_id FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'risk.created' AND target_id = $2",
        world.tenant_id,
        str(risk["id"]),
    )
    assert actor == f"human:{world.senior.user_id}"
    history = await world.seed.value(
        "SELECT count(*) FROM field_value_versions WHERE tenant_id = $1 AND target_type = 'risk' "
        "AND target_id = $2",
        world.tenant_id,
        risk["id"],
    )
    assert cast(int, history) >= 5  # every field written through record_value


async def test_management_override_reads_mandatory_and_is_never_rebuttable(world: Books) -> None:
    risk = await _create(world, *GRID[0])
    assert (risk["significance"], risk["fraud"]) == ("mandatory", "presumed")
    status, body = await _patch(world, risk, {"fraud": "rebuttal_proposed"})
    assert (status, body["detail"]) == (422, "presumption_not_rebuttable")
    status, body = await _patch(world, risk, {"significance": "not_significant"})
    assert status == 422
    row = await world.seed.value(
        "SELECT fraud FROM risk_register_rows WHERE id = $1", uuid.UUID(cast(str, risk["id"]))
    )
    assert row == "presumed"


async def test_a_stale_edit_writes_nothing(world: Books) -> None:
    risk = await _create(world, *GRID[3])
    status, _ = await _patch(world, risk, {"inherent_risk": "moderate"})
    assert status == 200
    before = await world.seed.value(
        "SELECT count(*) FROM field_value_versions WHERE target_id = $1",
        uuid.UUID(cast(str, risk["id"])),
    )
    stale, body = await _patch(world, risk, {"inherent_risk": "high"})
    assert (stale, body["detail"]) == (409, "version_conflict")
    after = await world.seed.value(
        "SELECT count(*) FROM field_value_versions WHERE target_id = $1",
        uuid.UUID(cast(str, risk["id"])),
    )
    assert after == before


async def test_linking_twice_is_409_and_unlinking_keeps_the_row(world: Books) -> None:
    risk = await _create(world, *GRID[1])
    body: Json = {"target_kind": "workpaper", "target_ref": "EBP-04"}
    first = await world.call(
        "POST", _path(world, f"/{risk['id']}/responses"), world.senior, body, headers=_keyed()
    )
    assert first.status_code == 201
    again = await world.call(
        "POST", _path(world, f"/{risk['id']}/responses"), world.senior, body, headers=_keyed()
    )
    assert (again.status_code, again.json()["detail"]) == (409, "already_linked")
    gone = await world.call(
        "DELETE",
        _path(world, f"/{risk['id']}/responses?target_kind=workpaper&target_ref=EBP-04"),
        world.senior,
    )
    assert gone.status_code == 200
    kept = await world.seed.value(
        "SELECT count(*) FROM risk_linkages WHERE risk_id = $1 AND removed_at IS NOT NULL",
        uuid.UUID(cast(str, risk["id"])),
    )
    assert kept == 1
