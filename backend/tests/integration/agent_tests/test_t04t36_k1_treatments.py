"""T-04-T36 (TASK-7309; SPEC-649 §3.7; TXI-02 a, d, e; DEC-84, DEC-88, DEC-4309).

Row acceptance: "Ridgeline shows 8 treatments with 7 proposed and treatment 8 approved, only PTET
is Changed vs 2024, an override without a reason answers 422, and a release that moves basis to
4,676,125 raises a re-proposal instead of editing the approved treatment." The activity and its
treatments are seeded as the agent's `k1_treatments` mode would leave them (T-04-T38 proposes)."""

from __future__ import annotations

import json
import uuid
from typing import cast

import httpx
import pytest

from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import OutboxEvent
from abacus.modules.tax import k1_treatments as k1
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


async def _return(seed: Seeder, world: World, who: Person) -> uuid.UUID:
    client = await seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.engagement_id
    )
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', 'Feld 1040', $5) "
            "RETURNING id",
            world.tenant_id,
            world.engagement_id,
            client,
            world.entity_id,
            who.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
        "form, tax_year) VALUES ($1, $2, $3, $4, '1040', 2025)",
        world.tenant_id,
        item,
        world.engagement_id,
        world.entity_id,
    )
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'tax.review_workspace', 'true', 't04-t36', 'T-04-T36') "
        "ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    forget_flags()
    return item


async def _reviewer(seed: Seeder, world: World, item: uuid.UUID, who: Person) -> None:
    """The matrix's `function_in` for approving and overriding treatments (the work item's)."""
    await seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, 'manager_reviewer', $4)",
        world.tenant_id,
        item,
        world.engagement_id,
        who.user_id,
    )


async def _ridgeline(seed: Seeder, world: World, item: uuid.UUID, samuel: Person) -> uuid.UUID:
    activity = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO k1_activities (tenant_id, engagement_id, tax_return_id, issuer_name, "
            "issuer_form, recipient_tsj, ownership_pct, content_hash) VALUES ($1, $2, $3, "
            "'Ridgeline Property Partners, LP', '1065', 'T', 25, $4) RETURNING id",
            world.tenant_id,
            world.engagement_id,
            item,
            "a" * 64,
        ),
    )
    for i, kind in enumerate(k1.KINDS):
        approved = i == 7
        prior = {"v": "Deduction", "year": 2024} if kind == "ptet_credits" else None
        await seed.run(
            "INSERT INTO k1_treatments (tenant_id, engagement_id, tax_return_id, k1_activity_id, "
            "kind, resolved, prior_year, changed_vs_prior, status, decided_by, decided_at) "
            "VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, $10, "
            "CASE WHEN $9 = 'approved' THEN clock_timestamp() END)",
            world.tenant_id,
            world.engagement_id,
            item,
            activity,
            kind,
            json.dumps({"v": "Credit" if kind == "ptet_credits" else "Default"}),
            json.dumps(prior) if prior else None,
            kind == "ptet_credits",
            "approved" if approved else "proposed",
            samuel.user_id if approved else None,
        )
    return activity


async def test_ridgeline_reads_eight_treatments_seven_proposed_and_only_ptet_changed(
    net: Net, seed: Seeder, world: World
) -> None:
    samuel = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, samuel, "manager")
    item = await _return(seed, world, samuel)
    await _ridgeline(seed, world, item, samuel)
    seen = await net.call("GET", f"/v1/tax/returns/{item}/k1-activities", samuel)
    assert seen.status_code == 200, seen.text
    (activity,) = cast(list[dict[str, object]], seen.json()["items"])
    rows = cast(list[dict[str, object]], activity["treatments"])
    assert len(rows) == 8
    assert sum(1 for r in rows if r["status"] == "proposed") == 7
    assert [r["line"] for r in rows if r["changed_vs_year"] == 2024] == ["Box 13"]
    assert activity["source_package_id"] is None


async def test_an_override_without_a_reason_answers_422(
    net: Net, seed: Seeder, world: World
) -> None:
    samuel = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, samuel, "manager")
    item = await _return(seed, world, samuel)
    await _reviewer(seed, world, item, samuel)
    activity = await _ridgeline(seed, world, item, samuel)
    treatment = await seed.value(
        "SELECT id FROM k1_treatments WHERE k1_activity_id = $1 AND kind = 'passive_nonpassive'",
        activity,
    )
    path = f"/v1/tax/k1-treatments/{treatment}/override"
    blank = await net.call(
        "POST", path, samuel, body={"value": "Nonpassive", "reason": " ", "seen_version": 1}
    )
    assert blank.status_code == 422
    done = await net.call(
        "POST",
        path,
        samuel,
        body={"value": "Nonpassive", "reason": "Material participation", "seen_version": 1},
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "overridden" and done.json()["treatment"] == "Nonpassive"


async def test_a_release_that_moves_basis_re_proposes_instead_of_editing(
    seed: Seeder, world: World
) -> None:
    samuel = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, samuel, "manager")
    item = await _return(seed, world, samuel)
    activity = await _ridgeline(seed, world, item, samuel)
    package = uuid.uuid4()
    await seed.run(
        "UPDATE k1_treatments SET status = 'approved', decided_by = $2, "
        "decided_at = clock_timestamp() WHERE k1_activity_id = $1 AND kind = 'basis_at_risk'",
        activity,
        samuel.user_id,
    )

    # The package, its draft lines and the hand-off's final values (Item L moved).
    issuing = await _return(seed, world, samuel)
    recipient = await seed.value(
        "INSERT INTO k1_recipients (tenant_id, work_item_id, engine_ref, display_name, "
        "recipient_kind, is_entity) VALUES ($1, $2, 'P-4', 'Jonah Feld', 'lp', false) "
        "RETURNING id",
        world.tenant_id,
        issuing,
    )
    await seed.run(
        "INSERT INTO k1_packages (id, tenant_id, recipient_id, work_item_id, form, tax_year, "
        "version_no) VALUES ($1, $2, $3, $4, '1065', 2025, 1)",
        package,
        world.tenant_id,
        recipient,
        issuing,
    )
    await seed.run(
        "INSERT INTO k1_box_lines (tenant_id, package_id, document_kind, box_code, description, "
        "amount, position) VALUES ($1, $2, 'k1', 'L', 'Item L ending capital', 1912500, 1)",
        world.tenant_id,
        package,
    )
    await seed.run(
        "INSERT INTO k1_handoffs (tenant_id, package_id, target_work_item_id, status, shared_by, "
        "replaced_at, final_values) VALUES ($1, $2, $3, 'final_replaced', $4, clock_timestamp(), "
        "$5::jsonb)",
        world.tenant_id,
        package,
        item,
        samuel.user_id,
        json.dumps({"L": "1914050"}),
    )
    await seed.run(
        "UPDATE k1_activities SET source_package_id = $2 WHERE id = $1", activity, package
    )
    await k1.on_package_released(
        OutboxEvent(
            event_id=uuid.uuid4(),
            tenant_id=world.tenant_id,
            event_type="k1_package.released",
            payload={"package_id": str(package), "work_item_id": str(issuing)},
        )
    )
    status = await seed.value(
        "SELECT status FROM k1_treatments WHERE k1_activity_id = $1 AND kind = 'basis_at_risk'",
        activity,
    )
    assert status == "proposed"  # re-proposed, never edited in place
    events = await seed.value(
        "SELECT string_agg(e.event, ',' ORDER BY e.at) FROM k1_treatment_events e "
        "JOIN k1_treatments t ON t.id = e.treatment_id WHERE t.k1_activity_id = $1",
        activity,
    )
    assert events == "went_stale,reproposed"
    assert (
        await seed.value("SELECT k1_state FROM k1_activities WHERE id = $1", activity)
        == "released"
    )
