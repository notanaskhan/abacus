"""Weekly pilot metrics (Q-04-T008; Q-04 AC-8.1, AC-8.2; DEC-825).

`compute_week(tenant_id, week_start)` writes, for each enrolment live in the ISO week (Monday
`week_start` to Sunday), one `pilot_metric_snapshots` row per metric, computed by code, as the
platform in the firm's tenant. Platform is below every module, so the modules that own the facts
register their metric through `register_pilot_metric_source` (fail closed: an unregistered metric
is simply not written):

- `w4_portal_activation.v1` (engagements, over `organisations.api.portal_activation`): the
  client's contacts who signed in at least once ÷ invited.
- `w5_pbc_via_portal.v1` (requests): received ÷ asked over the work item's published PBC
  binders' client-visible requests, which reach the client only through the portal.
- `w6_request_to_received_days.v1` (audit_trail): the median days from a request's first
  `request_item.sent` to its last `request_item.uploaded` in the week, firm-wide (the allowlisted
  duration read), and `w6_vs_baseline_days.v1`, that median less the enrolment's baseline.
- `w7.v1.<agent>` (agents): Q-02-T50's `override_rate.v1` over the agent's live outputs in the
  week (`live_override`), only when enough were decided.

A metric with nothing to divide by is left out, never written as zero. A rerun inserts nothing
new (`ON CONFLICT DO NOTHING` on the table's `UNIQUE NULLS NOT DISTINCT`), and the table is
insert-only (0276), so a week's numbers never change. The INV counters wait for stored sources
(DEC-825).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow

ACTOR: Final = "pilot_metrics"
PLACES: Final = Decimal("0.0001")


class NotAMonday(ValueError):
    """A pilot week starts on a Monday (ISO week)."""


@dataclass(frozen=True)
class PilotWeek:
    """What a metric source reads: one enrolment's work item and baseline, and the week."""

    enrolment_id: UUID
    work_item_id: UUID
    baseline_days: int | None
    start: datetime  # Monday 00:00 UTC
    end: datetime  # the next Monday 00:00 UTC


MetricSource = Callable[[TenantContext, PilotWeek], Awaitable[dict[str, Decimal]]]
_SOURCES: dict[str, MetricSource] = {}


def register_pilot_metric_source(name: str, source: MetricSource) -> None:
    """A module registers its metric once, at import (a reload replaces itself)."""
    known = _SOURCES.get(name)
    if known is not None and known.__qualname__ != source.__qualname__:
        raise ValueError(f"pilot metric source {name!r} is already registered")
    _SOURCES[name] = source


def ratio(numerator: int, denominator: int) -> Decimal | None:
    """A share to four places (half up), or None with nothing to divide by."""
    if denominator <= 0:
        return None
    return (Decimal(numerator) / Decimal(denominator)).quantize(PLACES, ROUND_HALF_UP)


_LIVE = text(
    "SELECT id, work_item_id, baseline_days FROM pilot_enrolments WHERE mode <> 'exited' "
    "AND window_start <= :end AND window_end >= :start ORDER BY created_at, id"
)
_INSERT = text(
    "INSERT INTO pilot_metric_snapshots (tenant_id, enrolment_id, metric_key, subject_id, "
    "period_start, period_end, value) VALUES (:tenant, :enrolment, :key, NULL, :start, :end, "
    ":value) ON CONFLICT ON CONSTRAINT pilot_metric_snapshots_once DO NOTHING RETURNING id"
)


async def week_values(tenant: TenantContext, week: PilotWeek) -> dict[str, Decimal]:
    """Every registered metric of one enrolment-week that has something to divide by."""
    values: dict[str, Decimal] = {}
    for name in sorted(_SOURCES):
        values.update(await _SOURCES[name](tenant, week))
    return values


async def compute_week(tenant_id: UUID, week_start: date) -> int:
    """Write the week's snapshots for every live enrolment; returns how many rows were new."""
    if week_start.isoweekday() != 1:
        raise NotAMonday(str(week_start))
    end = week_start + timedelta(days=6)
    tenant = TenantContext(tenant_id, "system", ACTOR)
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_LIVE, {"start": week_start, "end": end})).all()
    written = 0
    for row in rows:
        week = PilotWeek(
            row.id,
            row.work_item_id,
            row.baseline_days,
            datetime.combine(week_start, time(0), tzinfo=UTC),
            datetime.combine(end + timedelta(days=1), time(0), tzinfo=UTC),
        )
        values = await week_values(tenant, week)
        if not values:
            continue
        async with uow(tenant) as tx:
            new = 0
            for key, value in sorted(values.items()):
                inserted = await tx.session.execute(
                    _INSERT,
                    {
                        "tenant": tenant_id,
                        "enrolment": row.id,
                        "key": key,
                        "start": week_start,
                        "end": end,
                        "value": value,
                    },
                )
                new += 1 if inserted.first() is not None else 0
            tx.record(
                "pilot_metrics.computed",
                target=Target("pilot_enrolment", row.id),
                after=Ref(
                    week_start=int(week_start.strftime("%Y%m%d")), metrics=len(values), new=new
                ),
            )
        written += new
    return written


def last_week(today: date) -> date:
    """The Monday of the ISO week before `today`'s (the Schedule's Monday run reads last week)."""
    return today - timedelta(days=today.isoweekday() - 1 + 7)
