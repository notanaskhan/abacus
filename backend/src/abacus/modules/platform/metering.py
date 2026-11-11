"""Agent-minute metering (P-10-T42; SPEC-647 §3.10 AC-M1 to AC-M4; ADR-148, ADR P-28; DEC-3401).
Contract: `docs/contracts/agent-runs.md` §9 (firm usage, engagement effort).

- **Posting.** A v2 run's terminal state emits `agent_run.completed` (the agents module) with its
  `agent_ms` and the `agent_minutes` stored once on the run: round-half-up of `agent_ms ÷ 60,000`,
  so a run under 30 seconds posts 0 minutes but still counts as a run (AC-M2). This module's
  subscriber writes one insert-only `agent_minute_ledger` row per run (UNIQUE (tenant, run):
  redelivery posts nothing twice) and adds the same integer to the usage month's rollup row. An
  open run posts nothing (AC-M4).
- **Usage month.** Day 15 to day 14 of the next month (the plan anchor; Brightwater Hale's Sep 15
  to Oct 14, 2026 is `2026-09`). The month a run posts to is the business date it completed on,
  fixed in the event, never the day the relay delivered it.
- **Reads.** Every figure sums stored integers (AC-M1), so ADM-14a 14,920 = 8,640 + 4,610 + 1,420
  + 120 + 130 and ENG-06a 412 = 46 + 24 + 342 foot by construction. Minutes only: USD stays the
  internal safety layer and is never returned (AC-M3); minutes are never hours (D5).
- **Labels.** The engagements module names engagements and the agents module names capabilities;
  each registers a labeller here, so this module reads neither's tables (ADR-008). An engagement
  the reader may not see (walls, need to know) is folded into one "Other engagements" line, so
  the totals still foot and no walled name leaks.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel._flags import AGENT_RUNTIME_V2
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Handler, OutboxEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    engagement_resource,
    is_synthetic_firm,
)

MS_PER_MINUTE: Final = 60_000
USAGE_MONTH_ANCHOR_DAY: Final = 15  # the plan anchor (P-10 §4.2; ADM-14 "Sep 15 to Oct 14")
DEFAULT_ENGAGEMENT_BUDGET: Final = 1_500  # 0684's default; ADM-14 "Default engagement budget"
FIRM_SERVICE_LINE: Final = "firm"  # a firm-level run (no engagement): "Firm operations"
OTHER_ENGAGEMENTS: Final = "other"
_READER: Final = "agent-minute-ledger"

# ADM-14 "By service line" (verbatim): engagement service lines (0069) plus firm-level runs.
SERVICE_LINE_LABELS: Final[Mapping[str, str]] = {
    "tax": "Tax",
    "audit": "Audit & assurance",
    "cas": "Client accounting",
    "advisory": "Advisory & attest",
    FIRM_SERVICE_LINE: "Firm operations",
}
SERVICE_LINE_ORDER: Final = ("tax", "audit", "cas", "advisory", FIRM_SERVICE_LINE)

LabelKind = Literal["engagement", "capability"]
Labeller = Callable[[TenantContext, Sequence[str]], Awaitable[Mapping[str, str]]]
_labellers: dict[str, Labeller] = {}


def register_usage_labeller(kind: LabelKind, labeller: Labeller) -> None:
    """The engagements module names engagements, the agents module capabilities (ADR-008)."""
    _labellers[kind] = labeller


async def _labels(
    tenant: TenantContext, kind: LabelKind, keys: Sequence[str]
) -> Mapping[str, str]:
    labeller = _labellers.get(kind)
    if labeller is None or not keys:
        return {}
    return await labeller(tenant, keys)


# --- arithmetic (code computes, ADR-050) ---------------------------------------------------------


def agent_minutes(agent_ms: int) -> int:
    """AC-M1: round-half-up of `agent_ms ÷ 60,000`, in integers (29,999 ms is 0; 30,000 is 1)."""
    if agent_ms < 0:
        raise ValueError("agent_ms must not be negative")
    return (agent_ms + MS_PER_MINUTE // 2) // MS_PER_MINUTE


def usage_month_of(day: date) -> str:
    """The usage month `day` falls in, named by the month it starts in (`YYYY-MM`)."""
    year, month = day.year, day.month
    if day.day < USAGE_MONTH_ANCHOR_DAY:
        year, month = (year - 1, 12) if month == 1 else (year, month - 1)
    return f"{year:04d}-{month:02d}"


def usage_month_bounds(usage_month: str) -> tuple[date, date]:
    """The usage month's first and last business days (Sep 15 to Oct 14 for `2026-09`)."""
    try:
        year, month = (int(part) for part in usage_month.split("-"))
        start = date(year, month, USAGE_MONTH_ANCHOR_DAY)
    except ValueError as exc:
        raise DomainInvalid("usage_month_invalid", facts={"month": usage_month}) from exc
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    return start, date(next_year, next_month, USAGE_MONTH_ANCHOR_DAY - 1)


# --- posting (the subscriber) --------------------------------------------------------------------


@dataclass(frozen=True)
class RunMinutes:
    """One run's line, as `agent_run.completed` carries it (identifiers, codes, integers)."""

    run_id: UUID
    completed_on: date
    agent_ms: int
    minutes: int
    capability: str
    service_line: str
    engagement_id: UUID | None = None
    run_number: int | None = None
    definition_id: UUID | None = None
    work_item_ref: str | None = None
    phase: str | None = None
    cost_usd: Decimal = Decimal(0)


_LEDGER_INSERT: Final = text(
    "INSERT INTO agent_minute_ledger (tenant_id, usage_month, run_id, engagement_id, "
    "work_item_ref, service_line, definition_id, capability, phase, minutes, agent_ms, cost_usd, "
    "run_number) VALUES (:t, :month, :run, :engagement, :work_item, :line, :definition, "
    ":capability, :phase, :minutes, :ms, :cost, :number) "
    "ON CONFLICT (tenant_id, run_id) DO NOTHING RETURNING id"
)
_ROLLUP_ADD: Final = text(
    "INSERT INTO usage_month_rollups (tenant_id, usage_month, service_line, engagement_id, "
    "capability, phase, minutes, cost_usd) VALUES (:t, :month, :line, :engagement, :capability, "
    ":phase, :minutes, :cost) ON CONFLICT (tenant_id, usage_month, service_line, engagement_id, "
    "capability, phase) DO UPDATE SET minutes = usage_month_rollups.minutes + EXCLUDED.minutes, "
    "cost_usd = usage_month_rollups.cost_usd + EXCLUDED.cost_usd"
)


async def _post(tx: UnitOfWork, tenant_id: UUID, line: RunMinutes) -> bool:
    """One ledger row and its rollup; False when the run already posted (at-least-once)."""
    if line.minutes != agent_minutes(line.agent_ms):
        raise DomainInvalid("agent_minutes_mismatch", facts={"run_id": str(line.run_id)})
    if line.service_line not in SERVICE_LINE_LABELS:
        raise DomainInvalid("service_line_invalid", facts={"service_line": line.service_line})
    month = usage_month_of(line.completed_on)
    params = {
        "t": tenant_id,
        "month": month,
        "run": line.run_id,
        "engagement": line.engagement_id,
        "work_item": line.work_item_ref,
        "line": line.service_line,
        "definition": line.definition_id,
        "capability": line.capability,
        "phase": line.phase,
        "minutes": line.minutes,
        "ms": line.agent_ms,
        "cost": line.cost_usd,
        "number": line.run_number,
    }
    inserted = (await tx.session.execute(_LEDGER_INSERT, params)).first()
    if inserted is None:
        return False
    await tx.session.execute(_ROLLUP_ADD, params)
    tx.record(
        "agent_minutes.posted",
        target=Target("agent_run", line.run_id),
        after=Ref(minutes=line.minutes, agent_ms=line.agent_ms),
    )
    return True


def run_minutes_from(payload: Mapping[str, object]) -> RunMinutes:
    """`agent_run.completed`'s payload as a line (the agents module's `RunCompleted`)."""

    def _uuid(key: str) -> UUID | None:
        value = payload.get(key)
        return UUID(str(value)) if value else None

    def _text(key: str) -> str | None:
        value = payload.get(key)
        return str(value) if value else None

    number = payload.get("run_number")
    run_id = _uuid("run_id")
    if run_id is None:
        raise DomainInvalid("run_id_required")
    return RunMinutes(
        run_id=run_id,
        completed_on=date.fromisoformat(str(payload["completed_on"])),
        agent_ms=int(str(payload["agent_ms"])),
        minutes=int(str(payload["agent_minutes"])),
        capability=str(payload["capability"]),
        service_line=str(payload["service_line"]),
        engagement_id=_uuid("engagement_id"),
        run_number=int(str(number)) if number is not None else None,
        definition_id=_uuid("definition_id"),
        work_item_ref=_text("work_item_ref"),
        phase=_text("phase"),
        cost_usd=Decimal(str(payload.get("cost_usd") or "0")),
    )


class _NothingNew(Exception):
    """Every line was posted already (a redelivery): the unit writes nothing and rolls back, so
    it needs no audit event and the outbox does not retry it."""


async def _post_all(tenant: TenantContext, lines: Sequence[RunMinutes]) -> int:
    posted = 0
    try:
        async with uow(tenant) as tx:
            for line in lines:
                posted += await _post(tx, tenant.tenant_id, line)
            if not posted:
                raise _NothingNew
    except _NothingNew:
        return 0
    return posted


async def on_run_completed(event: OutboxEvent) -> None:
    """`agent_run.completed`: the run's minutes, once, on the month it completed in. A
    redelivered event finds its row and writes nothing (S36 end pass, DEC-3417)."""
    line = run_minutes_from(event.payload)
    tenant = TenantContext(event.tenant_id, "system", f"{_READER}:{line.run_id}")
    await _post_all(tenant, [line])


SUBSCRIPTIONS: Final[dict[str, Handler]] = {"agent_run.completed": on_run_completed}


async def record_synthetic_minutes(tenant: TenantContext, lines: Sequence[RunMinutes]) -> int:
    """The Brightwater Hale seed's usage history (P-10-T42): the metering lines of runs that
    completed before the scenario's runs are recorded, posted by the same code a completed run
    takes. Synthetic firms only (DEC-1530); returns how many lines were new."""
    if not await is_synthetic_firm(tenant):
        raise NotFound("agent_minute_ledger")
    return await _post_all(tenant, lines)


# --- reads ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class UsageLine:
    key: str
    label: str
    minutes: int


@dataclass(frozen=True)
class FirmUsage:
    usage_month: str
    starts_on: date
    ends_on: date
    used_minutes: int
    included_minutes: int
    by_service_line: list[UsageLine]
    by_engagement: list[UsageLine]
    by_capability: list[UsageLine]


@dataclass(frozen=True)
class EngagementEffort:
    engagement_id: UUID
    used_minutes: int
    budget_minutes: int
    runs: int
    lines: list[UsageLine]


async def _gate(ctx: AuthContext, action: str, resource: Resource) -> None:
    """The matrix first (a client principal never sees metering: 404, INV-4), then the runtime
    flag (`agent_runtime.v2`; off: 404, as every C6 v2 route)."""
    if ctx.client:
        raise NotFound("agent_minutes")
    await authorise(ctx, action, resource)
    if not await flag_enabled(ctx.tenant, AGENT_RUNTIME_V2):
        raise NotFound("agent_runtime.v2")


_ROLLUP_ROWS: Final = text(
    "SELECT service_line, engagement_id, capability, sum(minutes) AS minutes "
    "FROM usage_month_rollups WHERE usage_month = :month "
    "GROUP BY service_line, engagement_id, capability"
)
_INCLUDED: Final = text(
    "SELECT coalesce(sum(agent_minutes_allowance), 0) FROM tenant_entitlements "
    "WHERE enabled AND agent_minutes_allowance IS NOT NULL"
)


async def _seen(ctx: AuthContext, engagement_id: UUID) -> bool:
    try:
        await authorise(
            ctx, "engagement.read", await engagement_resource(ctx.tenant, engagement_id)
        )
    except (Forbidden, NotFound):
        return False
    return True


def _sorted(totals: Mapping[str, int], labels: Mapping[str, str]) -> list[UsageLine]:
    """Largest first, then by label: the ADM-14 rows' order."""
    lines = [UsageLine(key, labels.get(key, key), minutes) for key, minutes in totals.items()]
    return sorted(lines, key=lambda line: (-line.minutes, line.label))


async def firm_usage(ctx: AuthContext, month: str | None = None) -> FirmUsage:
    """ADM-14's metering block: the usage month's minutes against the plan's included minutes."""
    await _gate(ctx, "usage.read", Resource.firm(ctx.tenant_id))
    usage_month = month or usage_month_of(await clock.today(ctx.tenant))
    starts_on, ends_on = usage_month_bounds(usage_month)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_ROLLUP_ROWS, {"month": usage_month})).all()
        included = int(await session.scalar(_INCLUDED) or 0)
    by_line: dict[str, int] = {}
    by_engagement: dict[str, int] = {}
    by_capability: dict[str, int] = {}
    seen: dict[UUID, bool] = {}
    for row in rows:
        minutes = int(row.minutes)
        by_line[row.service_line] = by_line.get(row.service_line, 0) + minutes
        by_capability[row.capability] = by_capability.get(row.capability, 0) + minutes
        if row.engagement_id is None:
            continue
        if row.engagement_id not in seen:
            seen[row.engagement_id] = await _seen(ctx, row.engagement_id)
        key = str(row.engagement_id) if seen[row.engagement_id] else OTHER_ENGAGEMENTS
        by_engagement[key] = by_engagement.get(key, 0) + minutes
    visible = [key for key in by_engagement if key != OTHER_ENGAGEMENTS]
    engagement_labels = dict(await _labels(ctx.tenant, "engagement", visible))
    engagement_labels[OTHER_ENGAGEMENTS] = "Other engagements"
    capability_labels = await _labels(ctx.tenant, "capability", list(by_capability))
    service_lines = [
        UsageLine(key, SERVICE_LINE_LABELS[key], by_line[key])
        for key in SERVICE_LINE_ORDER
        if key in by_line
    ]
    return FirmUsage(
        usage_month=usage_month,
        starts_on=starts_on,
        ends_on=ends_on,
        used_minutes=sum(by_line.values()),
        included_minutes=included,
        by_service_line=service_lines,
        by_engagement=_sorted(by_engagement, engagement_labels),
        by_capability=_sorted(by_capability, capability_labels),
    )


_EFFORT_ROWS: Final = text(
    "SELECT run_id, run_number, capability, minutes FROM agent_minute_ledger "
    "WHERE engagement_id = :engagement ORDER BY run_number NULLS LAST, recorded_at, run_id"
)
_BUDGET: Final = text(
    "SELECT minutes_per_usage_month FROM engagement_agent_budgets "
    "WHERE engagement_id = :engagement"
)


async def engagement_effort(ctx: AuthContext, engagement_id: UUID) -> EngagementEffort:
    """ENG-06's AI part: the engagement's completed runs, one line each ("Run #4019 · PBC list
    builder · 46"), over the engagement's life; open runs are not here (AC-M4)."""
    await _gate(ctx, "engagement.read", await engagement_resource(ctx.tenant, engagement_id))
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_EFFORT_ROWS, {"engagement": engagement_id})).all()
        budget = await session.scalar(_BUDGET, {"engagement": engagement_id})
    capability_labels = await _labels(
        ctx.tenant, "capability", sorted({r.capability for r in rows})
    )
    lines = [
        UsageLine(
            str(row.run_id),
            _run_label(row.run_number, capability_labels.get(row.capability, row.capability)),
            int(row.minutes),
        )
        for row in rows
    ]
    return EngagementEffort(
        engagement_id=engagement_id,
        used_minutes=sum(line.minutes for line in lines),
        budget_minutes=int(budget) if budget is not None else DEFAULT_ENGAGEMENT_BUDGET,
        runs=len(lines),
        lines=lines,
    )


def _run_label(run_number: int | None, capability: str) -> str:
    return f"Run #{run_number} · {capability}" if run_number is not None else capability
