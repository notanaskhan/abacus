"""A-04-T12 (TASK-2900; A-04 §3.3 AC3.1, AC3.3-AC3.6, AC3.9; SPEC-620; DEC-1950).

Row acceptance: "Only Margaret can decide the Northwind card, deciding writes v2 at 252,200 /
189,150 / 12,610 with materiality.decided in one unit of work, and Oct 6 records v3 No change
with the 700 difference." The Final layer needs an adjustment source (A-06, C8): until one
registers, a reassessment answers 409 `layer_unavailable`; the Oct 6 No-change clause is covered
once A-06-T05 registers the source (A-04-T17's golden suite).

Boundary: `create_app()` over HTTP on the migrated test database. The firm's materiality policy
goes in as a firm imports it (K-02's workbook, then its owner's publish). Every figure is typed
here from A-04 §3.3, never imported from the engine.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Final, cast

import pytest

from abacus.kernel.clock import today
from abacus.kernel.flags import forget_flags
from abacus.modules.methodology.api import (
    create_standard,
    import_standard_workbook,
    publish_standard,
    standard_workbook,
)

from .tb_support import Books, Json, books, snapshot

pytestmark = pytest.mark.asyncio

FLAGS: Final = ("assurance.materiality", "review.grammar_api")
NORTHWIND: Final = (
    ("1010", "KRS 500 Index Fund", "16500000.00", "0"),
    ("1200", "Notes receivable from participants", "312400.00", "0"),
    ("3000", "Net assets available for benefits", "0", "16812400.00"),
)
POLICY: Final[Json] = {
    "kind": "materiality_ranges",
    "rows": [
        {
            "engagement_kind": "EBP (defined contribution)",
            "benchmark": "Net assets available for benefits",
            "low_pct": "1.0",
            "high_pct": "2.0",
        },
        {
            "engagement_kind": "For-profit FS audit",
            "benchmark": "Pre-tax income",
            "low_pct": "3",
            "high_pct": "7",
        },
    ],
    "performance_materiality": {"low_pct": "50", "high_pct": "75"},
    "clearly_trivial_pct": "5",
}


@pytest.fixture
async def world(net: object) -> tuple[Books, uuid.UUID]:
    found = await books(net)  # pyright: ignore[reportArgumentType] -- the backfill `net` fixture
    for flag in FLAGS:
        await found.seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'A-04-T12') ON CONFLICT DO NOTHING",
            found.tenant_id,
            flag,
        )
    forget_flags()
    await found.seed.run_untriggered(
        "INSERT INTO assurance_work_items (work_item_id, tenant_id, engagement_id, "
        "assurance_type, ebp_plan_kind) VALUES ($1, $2, $3, 'ebp_audit', 'dc') "
        "ON CONFLICT (work_item_id) DO UPDATE SET ebp_plan_kind = 'dc'",
        found.work_item_id,
        found.tenant_id,
        found.site.engagement_id,
    )
    await found.seed.run(
        "UPDATE memberships SET firm_role = 'practice_leader', level = 'partner' "
        "WHERE tenant_id = $1 AND user_id = $2",
        found.tenant_id,
        found.partner.user_id,
    )
    owner = await found.human(found.partner)
    owner = replace(owner, firm_role="practice_leader")
    standard = await create_standard(
        owner,
        kind="materiality_ranges",
        key="bh-materiality-ranges",
        name="Materiality ranges",
        owner_id=owner.user_id,
    )
    await import_standard_workbook(
        owner, standard.id, standard_workbook(standard.kind, standard.name, POLICY)
    )
    await publish_standard(
        owner, standard.id, effective_from=await today(owner.tenant), change_summary="Version 1"
    )
    snap = await snapshot(found.tenant_id, found.senior.user_id, found.site.entity_id, NORTHWIND)
    tb_id = await found.adopted(snapshot_id=snap, prior=None, label="standard")
    return found, tb_id


def _path(world: Books, rest: str) -> str:
    return f"/v1/engagements/{world.site.engagement_id}/materiality{rest}"


def _keyed() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


async def _propose(world: Books, tb_id: uuid.UUID) -> Json:
    response = await world.call(
        "POST",
        _path(world, "/proposals"),
        world.manager,
        {"tb_snapshot_id": str(tb_id), "benchmark_key": "net_assets"},
        headers=_keyed(),
    )
    assert response.status_code == 201, response.text
    return cast(Json, response.json())


def _decide(**over: object) -> Json:
    body: Json = {
        "option_key": "rate_1_5",
        "factors": list[str](),
        "rationale": "1.5% of net assets: participants rely on the statements.",
        "seen_version": 1,
    }
    return body | over


async def test_ac3_1_options_by_code_on_the_unadjusted_trial_balance(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    proposed = await _propose(books_, tb_id)
    options = {
        cast(str, o["key"]): cast(Json, o["thresholds"])
        for o in cast(list[Json], proposed["options"])
    }
    assert set(options) == {"rate_1_0", "rate_1_5"}
    assert options["rate_1_0"]["overall"] == "168100.00"
    assert (
        options["rate_1_5"]["overall"],
        options["rate_1_5"]["pm"],
        options["rate_1_5"]["ct"],
    ) == (
        "252200.00",
        "189150.00",
        "12610.00",
    )
    assert options["rate_1_5"]["benchmark_amount"] == "16812400.00"
    stamp = cast(Json, options["rate_1_5"]["stamp"])
    assert stamp["engine_name"] == "materiality" and len(cast(str, stamp["inputs_hash"])) == 64
    version = cast(Json, proposed["version"])
    assert (version["version_no"], version["status"]) == (1, "proposed")
    # One card at a time: a second proposal waits for the partner.
    again = await books_.call(
        "POST",
        _path(books_, "/proposals"),
        books_.manager,
        {"tb_snapshot_id": str(tb_id), "benchmark_key": "net_assets"},
        headers=_keyed(),
    )
    assert (again.status_code, again.json()["detail"]) == (409, "proposal_pending")


async def test_ac3_3_preview_is_code_and_stays_inside_the_policy(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    await _propose(books_, tb_id)
    body = {"benchmark_key": "net_assets", "rate_pct": "1.5", "pm_pct": "75", "ct_pct": "5"}
    found = await books_.call("POST", _path(books_, "/preview"), books_.staff, body)
    assert found.status_code == 200, found.text
    assert (found.json()["overall"], found.json()["pm"]) == ("252200.00", "189150.00")
    outside = await books_.call(
        "POST", _path(books_, "/preview"), books_.staff, body | {"rate_pct": "2.5"}
    )
    assert (outside.status_code, outside.json()["detail"]) == (409, "outside_policy")
    assert outside.json()["facts"] == {"field": "rate_pct"}


async def test_ac3_4_ac3_5_only_the_partner_decides_and_v2_is_written_in_the_same_unit(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    proposed = await _propose(books_, tb_id)
    card = cast(str, proposed["decision_card_id"])
    decide = f"/v1/decision-cards/{card}/decide"
    for who in (books_.manager, books_.senior, books_.staff):
        refused = await books_.call("POST", decide, who, _decide())
        assert refused.status_code == 403, refused.text
    no_reason = await books_.call("POST", decide, books_.partner, _decide(rationale=None))
    assert (no_reason.status_code, no_reason.json()["detail"]) == (422, "rationale_required")
    # Nothing was written by the refusals.
    count = await books_.seed.value(
        "SELECT count(*) FROM materiality_versions WHERE work_item_id = $1", books_.work_item_id
    )
    assert count == 1
    decided = await books_.call("POST", decide, books_.partner, _decide())
    assert decided.status_code == 200, decided.text
    record = await books_.call("GET", _path(books_, "/current"), books_.manager)
    assert record.status_code == 200, record.text
    body = cast(Json, record.json())
    versions = cast(list[Json], body["versions"])
    assert [(v["version_no"], v["status"], v["superseded"]) for v in versions] == [
        (1, "proposed", True),
        (2, "decided", False),
    ]
    thresholds = cast(Json, versions[1]["thresholds"])
    assert (thresholds["overall"], thresholds["pm"], thresholds["ct"]) == (
        "252200.00",
        "189150.00",
        "12610.00",
    )
    assert versions[1]["decision_id"] is not None
    assert body["pending_card_id"] is None
    # The decision, the version and the event in one unit of work: one outbox row, one audit row.
    events = await books_.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'materiality.decided'",
        books_.tenant_id,
    )
    assert events == 1
    audited = await books_.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'materiality_version.decided'",
        books_.tenant_id,
    )
    assert audited == 1


async def test_ac3_6_a_reassessment_needs_the_final_layer(
    world: tuple[Books, uuid.UUID],
) -> None:
    books_, tb_id = world
    proposed = await _propose(books_, tb_id)
    card = cast(str, proposed["decision_card_id"])
    decided = await books_.call(
        "POST", f"/v1/decision-cards/{card}/decide", books_.partner, _decide()
    )
    assert decided.status_code == 200, decided.text
    found = await books_.call(
        "POST",
        _path(books_, "/reassessments"),
        books_.manager,
        {"tb_snapshot_id": str(tb_id)},
        headers=_keyed(),
    )
    # A-06 registers the adjustment source (C8), so the Final layer reads: with no proposed
    # entry it equals the unadjusted net assets and the decided overall stands.
    assert found.status_code == 201, found.text
    reassessment = cast(Json, cast(Json, found.json())["reassessment"])
    assert reassessment["final_amount"] == "16812400.00"
    assert (reassessment["at_rate"], reassessment["difference"]) == ("252200.00", "0.00")


async def test_ac3_9_no_client_reaches_materiality(world: tuple[Books, uuid.UUID]) -> None:
    books_, _ = world
    client = await books_.seed.client_contact(books_.site)
    found = await books_.call("GET", _path(books_, "/current"), client)
    assert found.status_code == 404
