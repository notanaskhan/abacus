"""Q-05-T09's routes (S51 partials, TASK-8729; DEC-5723; SPEC-711 AC-11 to AC-14; AUD-28).

Boundary: `create_app()` over HTTP on the migrated test database, `audit.consultations_log` on.
The create carries facts and the consulted role; the conclude records the implementation; reopen
clears the conclusion (0644's CHECK); a position is the caller's own role on the engagement; a
disagreeing position blocks release until the QM owner resolves it, once; the firm log counts
only what the reader may see.
"""

from __future__ import annotations

import uuid
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import release

from .support import Person
from .tb_support import Books, Json, books

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def world(net: object) -> Books:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    await found.seed.run(
        "INSERT INTO tenant_entitlements (tenant_id, module, valid_from, set_by) "
        "VALUES ($1, 'assurance_completion', '2000-01-01', 'test-seed') ON CONFLICT DO NOTHING",
        found.tenant_id,
    )
    await found.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'audit.consultations_log', 'true', 'test-seed', 'TASK-8729')",
        found.tenant_id,
    )
    return found


def _keyed() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


def _consultee(world: Books) -> Person:
    """The consultee: a partner (AUD-28 f lists partners and specialists)."""
    return world.partner


async def _raised(world: Books, consultee: Person) -> str:
    made = await world.call(
        "POST",
        f"/v1/work-items/{world.work_item_id}/consultations",
        world.manager,
        {
            "question": "Implementation fees: over the term, or a distinct obligation?",
            "consulted_with_user_id": str(consultee.user_id),
            "facts": "$33,540 + $15,060 = $48,600",
            "consulted_role": "specialist",
        },
        headers=_keyed(),
    )
    assert made.status_code == 201, made.text
    return str(cast(Json, made.json())["id"])


async def test_ac_create_with_facts_conclude_with_implementation_then_reopen(world: Books) -> None:
    celia = _consultee(world)
    cid = await _raised(world, celia)
    base = f"/v1/consultations/{cid}"
    got = await world.call("GET", base, celia)
    assert got.status_code == 200, got.text
    detail = cast(Json, got.json())
    assert (detail["facts"], detail["consulted_role"]) == (
        "$33,540 + $15,060 = $48,600",
        "specialist",
    )

    no_ref = {"conclusion": "Over the term.", "implemented": True}
    refused = await world.call("POST", f"{base}/conclude", celia, no_ref, headers=_keyed())
    assert refused.status_code == 422, refused.text

    body = {"conclusion": "Over the term.", "implemented": True, "implemented_reference": "F-01"}
    done = await world.call("POST", f"{base}/conclude", celia, body, headers=_keyed())
    assert done.status_code == 200, done.text
    detail = cast(Json, (await world.call("GET", base, celia)).json())
    assert (detail["implemented"], detail["implemented_reference"]) == (True, "F-01")

    by_manager = await world.call("POST", f"{base}/reopen", world.manager, headers=_keyed())
    assert by_manager.status_code == 403, by_manager.text  # neither the consultee nor the QM owner
    reopened = await world.call("POST", f"{base}/reopen", celia, headers=_keyed())
    assert reopened.status_code == 200, reopened.text
    after = cast(Json, reopened.json())
    assert (after["implemented"], after["implemented_reference"]) == (False, None)
    assert after["reopened_at"] is not None
    row = await world.seed.rows(
        "SELECT status, conclusion_sealed IS NULL AS cleared FROM consultations WHERE id = $1",
        uuid.UUID(cid),
    )
    assert (row[0]["status"], row[0]["cleared"]) == ("open", True)
    again = await world.call("POST", f"{base}/reopen", celia, headers=_keyed())
    assert again.status_code == 409, again.text


async def test_ac_a_position_is_the_callers_own_role_and_a_difference_blocks_release(
    world: Books,
) -> None:
    cid = await _raised(world, _consultee(world))
    base = f"/v1/consultations/{cid}"
    as_eqr = {"role": "eqr_reviewer", "agrees": False, "position": "A distinct obligation."}
    claimed = await world.call(
        "POST", f"{base}/positions", world.partner, as_eqr, headers=_keyed()
    )
    assert claimed.status_code == 403, claimed.text

    as_ep = {"role": "engagement_partner", "agrees": False, "position": "Over the term."}
    recorded = await world.call(
        "POST", f"{base}/positions", world.partner, as_ep, headers=_keyed()
    )
    assert recorded.status_code == 200, recorded.text
    shown = cast(Json, recorded.json())
    assert shown["difference_unresolved"] is True
    told = await world.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'consultation.difference_recorded'",
        world.tenant_id,
    )
    assert told == 1

    snap = await release.snapshot(_tenant(world), world.work_item_id)
    assert "also_required:consultation_differences" in snap.blockers

    qm = await world.seed.person(world.tenant_id, "quality_partner")
    # the QM owner reads consultations in scope: their service lines include the engagement's
    await world.seed.run(
        "UPDATE memberships SET service_lines = ARRAY['audit'] WHERE tenant_id = $1 "
        "AND user_id = $2",
        world.tenant_id,
        qm.user_id,
    )
    resolution = {"resolution": "EQR concurs; recognise over the term."}
    not_qm = await world.call(
        "POST", f"{base}/resolve-difference", world.manager, resolution, headers=_keyed()
    )
    assert not_qm.status_code == 403, not_qm.text
    resolved = await world.call(
        "POST", f"{base}/resolve-difference", qm, resolution, headers=_keyed()
    )
    assert resolved.status_code == 200, resolved.text
    out = cast(Json, resolved.json())
    assert out["difference_unresolved"] is False
    assert cast(Json, out["resolution"])["before_release"] is True
    twice = await world.call(
        "POST", f"{base}/resolve-difference", qm, resolution, headers=_keyed()
    )
    assert twice.status_code == 409, twice.text
    snap = await release.snapshot(_tenant(world), world.work_item_id)
    assert "also_required:consultation_differences" not in snap.blockers


async def test_ac_the_firm_log_counts_only_visible_rows(world: Books) -> None:
    await _raised(world, _consultee(world))
    mine = await world.call("GET", "/v1/consultations", world.manager)
    assert mine.status_code == 200, mine.text
    counts = cast(Json, cast(Json, mine.json())["counts"])
    assert (counts["open"], counts["concluded"]) == (1, 0)
    outsider = await world.seed.person(world.tenant_id)
    theirs = await world.call("GET", "/v1/consultations", outsider)
    assert theirs.status_code in (200, 403), theirs.text
    if theirs.status_code == 200:
        body = cast(Json, theirs.json())
        assert body["items"] == [] and body["counts"] == {"open": 0, "concluded": 0}


def _tenant(world: Books) -> TenantContext:
    return TenantContext(world.tenant_id, "system", "test")
