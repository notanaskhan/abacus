# ac-test-author: ayushkbhatia
"""Q-04-T012 (TASK-1744; ADR-078 independent; c07 = Q-04-T007, c08 = Q-04-T008; Q-04 AC-8.1,
AC-8.2, AC-8.3, AC-8.4; DEC-834): the pilot tables and the weekly metrics, from the epic's
acceptance, not from T007's or T008's own suites.

Acceptance (the task row): "Tests prove snapshot immutability, that rerunning a week writes no
duplicate row for NULL-subject metrics (w4, w5, w6, inv_*), the system-of-record guard and metric
arithmetic on edge weeks, and fail when a rule is weakened."

- Immutability: the app role cannot update or delete a snapshot; a rerun after the facts change
  keeps the week's first numbers.
- NULL subject: the key is `UNIQUE NULLS NOT DISTINCT`, so a second NULL-subject row for the same
  week, metric and enrolment is refused even by the owner; a rerun writes nothing.
- The system-of-record guard: the table refuses the mode without a confirming person; the service
  refuses it without one and from shadow; `make pilot-mode` refuses a confirmer who is not an
  active member of the firm (AC-8.4's "named firm person").
- Edge weeks: an enrolment whose window touches the week by one day counts, one that misses it by
  a day does not; W6 reads `[Monday 00:00, next Monday 00:00)` UTC; an even count's median is the
  mean of the middle two; ratios round half up to four places and nothing-to-divide-by writes no
  row; a week across New Year ends on the Sunday in the next year.
- INV-4: forced RLS, and another firm's snapshots are invisible to the app role.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Final, cast

import asyncpg
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import Target, uow
from abacus.modules.platform.api import (
    PilotModeRefused,
    compute_pilot_week,
    enrol_pilot,
    pilot_ratio,
    set_pilot_mode,
)
from abacus_tools.pilots import confirmer_is_member

from .support import Migrated, Net, Person, Site

pytestmark = pytest.mark.asyncio
WEEK: Final = date(2027, 6, 7)  # a Monday
START: Final = datetime(2027, 6, 7, tzinfo=UTC)
END: Final = START + timedelta(days=7)
W4: Final = "w4_portal_activation.v1"
W6: Final = "w6_request_to_received_days.v1"
W6_BASE: Final = "w6_vs_baseline_days.v1"


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person

    async def site(self, label: str) -> Site:
        return await self.net.seed.site(self.tenant_id, self.admin.user_id, label)

    async def enrol(
        self,
        site: Site,
        *,
        start: date = date(2027, 6, 1),
        end: date = date(2027, 7, 12),
        baseline: int | None = 14,
    ) -> uuid.UUID:
        work_item = await self.net.seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 ORDER BY created_at LIMIT 1",
            site.engagement_id,
        )
        return cast(
            uuid.UUID,
            await self.net.seed.value(
                "INSERT INTO pilot_enrolments (tenant_id, work_item_id, window_start, "
                "window_end, baseline_days, created_by) VALUES ($1, $2, $3, $4, $5, $6) "
                "RETURNING id",
                self.tenant_id,
                work_item,
                start,
                end,
                baseline,
                self.admin.user_id,
            ),
        )

    async def contacts(self, site: Site, *states: str) -> None:
        for state in states:
            await self.net.seed.run(
                "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, "
                "portal_state) VALUES ($1, $2, $3, 'client_person', $4)",
                self.tenant_id,
                site.client_id,
                f"Contact {uuid.uuid4().hex[:6]}",
                state,
            )

    async def request(self, sent: datetime, uploaded: datetime) -> None:
        """One request's `sent` and `uploaded` audit events, recorded then dated (triggers off)."""
        tenant = TenantContext(self.tenant_id, "system", "q04t012-seed")
        target = uuid.uuid4()
        for action, at in (("request_item.sent", sent), ("request_item.uploaded", uploaded)):
            async with uow(tenant) as tx:
                tx.record(action, target=Target("request_item", target))
            await self.net.seed.run_untriggered(
                "WITH a AS (SELECT set_config('app.actor_kind', 'system', true), "
                "set_config('app.actor_id', 'q04t012-seed', true)) "
                "UPDATE audit_events SET occurred_at = $3 FROM a WHERE tenant_id = $1 "
                "AND target_id = $2 AND action = $4",
                self.tenant_id,
                str(target),
                at,
                action,
            )

    async def snapshots(self, enrolment: uuid.UUID | None = None) -> dict[str, Decimal]:
        rows = await self.net.seed.rows(
            "SELECT metric_key, value FROM pilot_metric_snapshots WHERE tenant_id = $1 "
            "AND ($2::uuid IS NULL OR enrolment_id = $2)",
            self.tenant_id,
            enrolment,
        )
        return {str(r["metric_key"]): Decimal(r["value"]) for r in rows}


async def _firm(net: Net) -> Firm:
    tenant = await net.seed.firm()
    return Firm(net, tenant, await net.seed.person(tenant, "firm_admin"))


@pytest.fixture
async def firm(net: Net) -> Firm:
    return await _firm(net)


@pytest.fixture
async def app_role(migrated_db: Migrated) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(
        migrated_db.app_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    yield conn
    await conn.close()


async def _as_app(conn: asyncpg.Connection, tenant: uuid.UUID, sql: str, *args: object) -> object:
    async with conn.transaction():
        await conn.execute("SELECT set_config('app.tenant_id', $1, true)", str(tenant))
        await conn.execute("SELECT set_config('app.actor_kind', 'system', true)")
        await conn.execute("SELECT set_config('app.actor_id', 'q04t012', true)")
        return await conn.fetchval(sql, *args)


async def _activated(firm: Firm, label: str = "Pilot") -> tuple[Site, uuid.UUID]:
    """A site enrolled for the week with one invited contact who signed in (W4 = 1)."""
    site = await firm.site(label)
    enrolment = await firm.enrol(site)
    await firm.contacts(site, "active")
    return site, enrolment


# --- Immutability and the NULL subject (AC-8.2) -------------------------------------------------


async def test_ac_the_app_role_cannot_update_or_delete_a_snapshot(
    firm: Firm, app_role: asyncpg.Connection
) -> None:
    _, enrolment = await _activated(firm)
    assert await compute_pilot_week(firm.tenant_id, WEEK) >= 1
    for sql in (
        "UPDATE pilot_metric_snapshots SET value = 0 WHERE enrolment_id = $1",
        "DELETE FROM pilot_metric_snapshots WHERE enrolment_id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await _as_app(app_role, firm.tenant_id, sql, enrolment)
    assert (await firm.snapshots(enrolment))[W4] == Decimal("1.0000")


async def test_ac_a_rerun_after_the_facts_change_keeps_the_weeks_first_numbers(
    firm: Firm,
) -> None:
    site, enrolment = await _activated(firm)
    first = await compute_pilot_week(firm.tenant_id, WEEK)
    await firm.contacts(site, "invited", "invited", "invited")  # W4 would now read 0.2500
    assert await compute_pilot_week(firm.tenant_id, WEEK) == 0
    got = await firm.snapshots(enrolment)
    assert got[W4] == Decimal("1.0000")
    assert len(got) == first


async def test_ac_a_second_null_subject_row_is_refused_even_for_the_owner(firm: Firm) -> None:
    _, enrolment = await _activated(firm)
    insert = (
        "INSERT INTO pilot_metric_snapshots (tenant_id, enrolment_id, metric_key, subject_id, "
        "period_start, period_end, value) VALUES ($1, $2, $3, $4, $5, $6, 1)"
    )
    for metric in ("w4_portal_activation.v1", "w5_pbc_via_portal.v1", "inv_agent_never.v1"):
        await firm.net.seed.run(insert, firm.tenant_id, enrolment, metric, None, WEEK, WEEK)
        with pytest.raises(asyncpg.UniqueViolationError):
            await firm.net.seed.run(insert, firm.tenant_id, enrolment, metric, None, WEEK, WEEK)
    # A named subject is its own row: two distinct subjects of one metric both land.
    for _ in range(2):
        await firm.net.seed.run(
            insert, firm.tenant_id, enrolment, "w7.v1.probe", uuid.uuid4(), WEEK, WEEK
        )


async def test_ac_the_unique_key_is_nulls_not_distinct(firm: Firm) -> None:
    definition = await firm.net.seed.value(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'pilot_metric_snapshots_once'"
    )
    assert "NULLS NOT DISTINCT" in str(definition)
    for column in ("tenant_id", "enrolment_id", "metric_key", "subject_id", "period_start"):
        assert column in str(definition)


# --- The system-of-record guard (AC-8.4) --------------------------------------------------------


async def test_ac_the_table_refuses_system_of_record_without_a_confirming_person(
    firm: Firm,
) -> None:
    _, enrolment = await _activated(firm)
    for confirmed_by, confirmed_at in ((None, None), (firm.admin.user_id, None)):
        with pytest.raises(asyncpg.CheckViolationError):
            await firm.net.seed.run(
                "UPDATE pilot_enrolments SET mode = 'system_of_record', confirmed_by = $2, "
                "confirmed_at = $3 WHERE id = $1",
                enrolment,
                confirmed_by,
                confirmed_at,
            )


async def test_ac_the_service_refuses_system_of_record_without_a_person_or_from_shadow(
    firm: Firm,
) -> None:
    _, enrolment = await _activated(firm)
    operator = TenantContext(firm.tenant_id, "system", "operator:pilots", firm.admin.user_id)
    with pytest.raises(PilotModeRefused):  # shadow cannot skip live
        await set_pilot_mode(operator, enrolment, "system_of_record", firm.admin.user_id)
    await set_pilot_mode(operator, enrolment, "live")
    with pytest.raises(PilotModeRefused):
        await set_pilot_mode(operator, enrolment, "system_of_record")
    mode = await firm.net.seed.value("SELECT mode FROM pilot_enrolments WHERE id = $1", enrolment)
    assert mode == "live"
    await set_pilot_mode(operator, enrolment, "system_of_record", firm.admin.user_id)
    row = (
        await firm.net.seed.rows(
            "SELECT mode, confirmed_by, confirmed_at FROM pilot_enrolments WHERE id = $1",
            enrolment,
        )
    )[0]
    assert (row["mode"], row["confirmed_by"]) == ("system_of_record", firm.admin.user_id)
    assert row["confirmed_at"] is not None
    audited = await firm.net.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'pilot.mode_changed'",
        firm.tenant_id,
    )
    assert audited == 2


async def test_ac_the_confirmer_is_an_active_member_of_this_firm(net: Net, firm: Firm) -> None:
    assert await confirmer_is_member(firm.tenant_id, firm.admin.user_id)
    assert not await confirmer_is_member(firm.tenant_id, uuid.uuid4())
    elsewhere = await _firm(net)
    assert not await confirmer_is_member(firm.tenant_id, elsewhere.admin.user_id)
    gone = await net.seed.person(firm.tenant_id, "firm_admin")
    await net.seed.revoke(gone)
    assert not await confirmer_is_member(firm.tenant_id, gone.user_id)


async def test_ac_make_pilot_enrol_writes_through_the_service_with_its_audit_event(
    firm: Firm,
) -> None:
    site = await firm.site("Service")
    work_item = cast(
        uuid.UUID,
        await firm.net.seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 ORDER BY created_at LIMIT 1",
            site.engagement_id,
        ),
    )
    operator = TenantContext(firm.tenant_id, "system", "operator:pilots", firm.admin.user_id)
    enrolment = await enrol_pilot(
        operator, work_item, date(2027, 6, 1), date(2027, 7, 12), 14, firm.admin.user_id
    )
    mode = await firm.net.seed.value("SELECT mode FROM pilot_enrolments WHERE id = $1", enrolment)
    assert mode == "shadow"
    audited = await firm.net.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'pilot.enrolled' "
        "AND target_id = $2",
        firm.tenant_id,
        str(enrolment),
    )
    assert audited == 1


# --- Edge weeks (AC-8.1) -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "end", "counted"),
    [
        (date(2027, 5, 1), WEEK, True),  # ends on the Monday
        (WEEK + timedelta(days=6), date(2027, 7, 1), True),  # starts on the Sunday
        (date(2027, 5, 1), WEEK - timedelta(days=1), False),  # ended the Sunday before
        (WEEK + timedelta(days=7), date(2027, 7, 1), False),  # starts the next Monday
    ],
)
async def test_ac_an_enrolment_counts_if_its_window_touches_the_week(
    firm: Firm, start: date, end: date, counted: bool
) -> None:
    site = await firm.site("Edge")
    enrolment = await firm.enrol(site, start=start, end=end)
    await firm.contacts(site, "active")
    await compute_pilot_week(firm.tenant_id, WEEK)
    assert (W4 in await firm.snapshots(enrolment)) is counted


async def test_ac_w6_reads_monday_to_monday_and_takes_the_middle_two_of_an_even_count(
    firm: Firm,
) -> None:
    _, enrolment = await _activated(firm)
    day = timedelta(days=1)
    await firm.request(START, START + 1 * day)  # sent at the first instant: in
    await firm.request(START + timedelta(hours=1), START + timedelta(hours=1) + 2 * day)
    await firm.request(START + timedelta(hours=2), START + timedelta(hours=2) + 3 * day)
    await firm.request(START + timedelta(hours=3), START + timedelta(hours=3) + 4 * day)
    await firm.request(START + 2 * day, END)  # uploaded at the next Monday 00:00: out
    await firm.request(START - timedelta(seconds=1), START + day)  # sent the Sunday before: out
    await compute_pilot_week(firm.tenant_id, WEEK)
    got = await firm.snapshots(enrolment)
    assert got[W6] == Decimal("2.5000")  # median of 1, 2, 3, 4 days
    assert got[W6_BASE] == Decimal("2.5000") - 14


@pytest.mark.parametrize(
    ("numerator", "denominator", "share"),
    [
        (1, 3, Decimal("0.3333")),
        (2, 3, Decimal("0.6667")),
        (1, 20_000, Decimal("0.0001")),  # 0.00005 rounds half up, not to even
        (3, 80_000, Decimal("0.0000")),  # 0.0000375 rounds down
        (0, 5, Decimal("0.0000")),
        (5, 5, Decimal("1.0000")),
        (1, 0, None),
        (0, 0, None),
    ],
)
async def test_ac_ratios_round_half_up_to_four_places_or_are_left_out(
    numerator: int, denominator: int, share: Decimal | None
) -> None:
    assert pilot_ratio(numerator, denominator) == share


async def test_ac_nothing_to_divide_by_writes_no_row(firm: Firm) -> None:
    site = await firm.site("Uninvited")
    enrolment = await firm.enrol(site, baseline=None)
    await firm.contacts(site, "not_invited", "not_invited")
    assert await compute_pilot_week(firm.tenant_id, WEEK) == 0
    assert await firm.snapshots(enrolment) == {}


async def test_ac_a_baseline_of_zero_is_a_baseline_and_none_writes_no_delta(firm: Firm) -> None:
    zero_site = await firm.site("Zero")
    zero = await firm.enrol(zero_site, baseline=0)
    none_site = await firm.site("None")
    none = await firm.enrol(none_site, baseline=None)
    await firm.request(START + timedelta(hours=9), START + timedelta(hours=9, days=3))
    await compute_pilot_week(firm.tenant_id, WEEK)
    assert (await firm.snapshots(zero))[W6_BASE] == Decimal("3.0000")
    assert W6_BASE not in await firm.snapshots(none)
    assert (await firm.snapshots(none))[W6] == Decimal("3.0000")


async def test_ac_a_week_across_new_year_ends_on_its_sunday(firm: Firm) -> None:
    site = await firm.site("New Year")
    enrolment = await firm.enrol(site, start=date(2027, 12, 1), end=date(2028, 1, 31))
    await firm.contacts(site, "active", "invited")
    await compute_pilot_week(firm.tenant_id, date(2027, 12, 27))
    rows = await firm.net.seed.rows(
        "SELECT period_start, period_end, value FROM pilot_metric_snapshots "
        "WHERE enrolment_id = $1 AND metric_key = $2",
        enrolment,
        W4,
    )
    assert [(r["period_start"], r["period_end"]) for r in rows] == [
        (date(2027, 12, 27), date(2028, 1, 2))
    ]
    assert Decimal(rows[0]["value"]) == Decimal("0.5000")


# --- INV-4: one tenant's numbers ----------------------------------------------------------------


async def test_inv4_the_pilot_tables_force_rls_and_hide_another_firms_snapshots(
    net: Net, firm: Firm, app_role: asyncpg.Connection
) -> None:
    forced = await net.seed.rows(
        "SELECT relname, relforcerowsecurity FROM pg_class WHERE relname IN "
        "('pilot_enrolments', 'pilot_metric_snapshots') AND relkind = 'r'"
    )
    assert {r["relname"]: r["relforcerowsecurity"] for r in forced} == {
        "pilot_enrolments": True,
        "pilot_metric_snapshots": True,
    }
    await _activated(firm)
    await compute_pilot_week(firm.tenant_id, WEEK)
    other = await _firm(net)
    seen = await _as_app(
        app_role,
        other.tenant_id,
        "SELECT count(*) FROM pilot_metric_snapshots WHERE tenant_id = $1",
        firm.tenant_id,
    )
    assert seen == 0
    assert (
        cast(
            int,
            await net.seed.value(
                "SELECT count(*) FROM pilot_metric_snapshots WHERE tenant_id = $1", firm.tenant_id
            ),
        )
        >= 1
    )
