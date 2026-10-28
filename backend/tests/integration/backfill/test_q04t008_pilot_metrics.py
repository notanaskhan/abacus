# ac-test-author: ayushkbhatia
"""Q-04-T008 (TASK-1735; Q-04 AC-8.1, AC-8.2; DEC-825): the weekly pilot metrics.

Acceptance (the task row): "On the rehearsal tenant one snapshot per metric per week is written, a
rerun is idempotent, every value matches a hand count of the seeded events, and W7 equals make
shadow-report's override rate on the same decision set."

Here: W4 (2 of 3 invited contacts signed in → 0.6667), W6 (sent → uploaded, medians by hand) and
its baseline delta, one row each; a rerun writes nothing; a metric with nothing to divide by is
left out; an exited enrolment is skipped; a non-Monday is refused. W7 reuses `override_rate`
itself (asserted by identity); its live-decision equality runs with the batch review's fixtures.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow
from abacus.modules.agents import pilot_w7, shadow_score
from abacus.modules.platform.api import compute_pilot_week
from abacus.modules.platform.pilot_metrics import NotAMonday, last_week

from .support import Net, Site

pytestmark = pytest.mark.asyncio
WEEK: Final = date(2027, 6, 7)  # a Monday
BASELINE: Final = 14


async def _work_item(net: Net, site: Site) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await net.seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 ORDER BY created_at LIMIT 1",
            site.engagement_id,
        ),
    )


async def _enrol(net: Net, site: Site, *, mode: str = "shadow") -> uuid.UUID:
    work_item = await _work_item(net, site)
    admin = await net.seed.value(
        "SELECT user_id FROM memberships WHERE tenant_id = $1 LIMIT 1", site.tenant_id
    )
    enrolment = cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO pilot_enrolments (tenant_id, work_item_id, window_start, window_end, "
            "baseline_days, created_by) VALUES ($1, $2, '2027-06-01', '2027-07-12', $3, $4) "
            "RETURNING id",
            site.tenant_id,
            work_item,
            BASELINE,
            admin,
        ),
    )
    if mode == "exited":
        await net.seed.run_untriggered(
            "UPDATE pilot_enrolments SET mode = 'exited' WHERE id = $1", enrolment
        )
    return enrolment


async def _contacts(net: Net, site: Site, states: tuple[str, ...]) -> None:
    for n, state in enumerate(states):
        await net.seed.run(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, "
            "portal_state) VALUES ($1, $2, $3, 'client_person', $4)",
            site.tenant_id,
            site.client_id,
            f"Contact {n}",
            state,
        )


async def _requests(net: Net, site: Site, days: tuple[int, ...]) -> None:
    """One request per entry, sent at WEEK 09:00 UTC and uploaded `days` later (same week): the
    events are recorded now, then dated into the week with triggers off (the chain is not read)."""
    tenant = TenantContext(site.tenant_id, "system", "q04t008-seed")
    for n, gap in enumerate(days):
        target = uuid.uuid4()
        sent = datetime(2027, 6, 7, 9, tzinfo=UTC) + timedelta(hours=n)
        for action, at in (
            ("request_item.sent", sent),
            ("request_item.uploaded", sent + timedelta(days=gap)),
        ):
            async with uow(tenant) as tx:
                tx.record(action, target=Target("request_item", target))
            await net.seed.run_untriggered(
                "UPDATE audit_events SET occurred_at = $3 WHERE tenant_id = $1 "
                "AND target_id = $2 AND action = $4",
                site.tenant_id,
                str(target),
                at,
                action,
            )


async def _snapshots(net: Net, tenant: uuid.UUID) -> dict[str, Decimal]:
    rows = await net.seed.rows(
        "SELECT metric_key, value FROM pilot_metric_snapshots WHERE tenant_id = $1 "
        "AND period_start = $2",
        tenant,
        WEEK,
    )
    return {str(r["metric_key"]): Decimal(r["value"]) for r in rows}


async def test_ac_one_snapshot_per_metric_matching_a_hand_count(net: Net) -> None:
    tenant = await net.seed.firm()
    admin = await net.seed.person(tenant, "firm_admin")
    site = await net.seed.site(tenant, admin.user_id, "Rehearsal")
    await _enrol(net, site)
    await _contacts(net, site, ("active", "locked", "invited", "not_invited"))
    await _requests(net, site, (1, 3, 4))  # median 3 days
    written = await compute_pilot_week(tenant, WEEK)
    got = await _snapshots(net, tenant)
    assert got["w4_portal_activation.v1"] == Decimal("0.6667")  # 2 of 3 invited
    assert got["w6_request_to_received_days.v1"] == Decimal("3.0000")
    assert got["w6_vs_baseline_days.v1"] == Decimal("3.0000") - BASELINE
    assert written == len(got)
    assert "w5_pbc_via_portal.v1" not in got  # no published PBC binder: nothing to divide by


async def test_ac_a_rerun_is_idempotent(net: Net) -> None:
    tenant = await net.seed.firm()
    admin = await net.seed.person(tenant, "firm_admin")
    site = await net.seed.site(tenant, admin.user_id, "Rerun")
    await _enrol(net, site)
    await _contacts(net, site, ("active", "invited"))
    first = await compute_pilot_week(tenant, WEEK)
    again = await compute_pilot_week(tenant, WEEK)
    assert first >= 1 and again == 0
    count = await net.seed.value(
        "SELECT count(*) FROM pilot_metric_snapshots WHERE tenant_id = $1", tenant
    )
    assert count == first


async def test_ac_w7_is_the_shadow_reports_override_function() -> None:
    assert pilot_w7.live_override is shadow_score.live_override
    assert shadow_score.live_override.__module__ == shadow_score.override_rate.__module__
    assert shadow_score.OVERRIDE_ALGORITHM == "override_rate.v1"


async def test_an_exited_enrolment_is_skipped(net: Net) -> None:
    tenant = await net.seed.firm()
    admin = await net.seed.person(tenant, "firm_admin")
    site = await net.seed.site(tenant, admin.user_id, "Exited")
    await _enrol(net, site, mode="exited")
    await _contacts(net, site, ("active",))
    assert await compute_pilot_week(tenant, WEEK) == 0


async def test_a_week_starts_on_a_monday() -> None:
    with pytest.raises(NotAMonday):
        await compute_pilot_week(uuid.uuid4(), WEEK + timedelta(days=1))
    assert last_week(date(2027, 6, 14)) == WEEK
    assert last_week(date(2027, 6, 20)) == WEEK
