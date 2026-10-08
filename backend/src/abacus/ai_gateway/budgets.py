"""The budget hierarchy (ADR-069; SPEC-007 AC-1 to AC-3, AC-5). PROTECTED.

Before each model call, after the run's own budget: the engagement's month, the firm's month and
the platform's day, each with a soft and a hard limit. A soft limit defers deferrable work
(`NotAdmitted("deferred")`, which waits through the workflow's admission loop) and alerts once
per level and period; a hard limit refuses deferrable work (`BudgetExhausted`), and the
platform's daily hard limit refuses everything. Spend is committed usage plus this call's
estimate. If spend can't be read, deferrable work is refused (fail closed); essential work keeps
its per-call and per-run budgets. Sums are cached briefly per process and dropped after each
recorded call, so a few concurrent calls may overshoot a limit slightly (accepted, SPEC-007 §12).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.ai_gateway.admission import NotAdmitted
from abacus.ai_gateway.events import BudgetAnomaly, BudgetSoftCrossed
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Target, uow

CACHE_SECONDS: Final = 5.0
DEFER_SECONDS: Final = 300
_log = get_logger(__name__)
_crossed = meter(__name__).create_counter(
    "abacus.budget.soft_crossed", description="Budget soft limits crossed, by level"
)
_refused = meter(__name__).create_counter(
    "abacus.budget.refused", description="Calls refused or deferred by a budget, by level"
)
_cache: dict[tuple[str, UUID | None], tuple[float, Decimal]] = {}
_alerted: set[tuple[str, UUID | None, str]] = set()


class BudgetExhausted(Exception):
    """A hard budget limit: deferrable work (or, at the platform's limit, all work) stops."""


def forget_spend() -> None:
    """Drop cached sums (after a call is recorded)."""
    _cache.clear()


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _sum(tenant: TenantContext, level: str, engagement_id: UUID | None) -> Decimal:
    key = (level, engagement_id if level == "engagement" else tenant.tenant_id)
    hit = _cache.get(key)
    if hit is not None and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    async with tenant_session(tenant) as session:
        if level == "platform":
            value = await session.scalar(text("SELECT platform_spend_today()"))
        elif level == "engagement":
            value = await session.scalar(
                text(
                    "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_records "
                    "WHERE engagement_id = :e AND created_at >= :since"
                ),
                {"e": engagement_id, "since": _month_start()},
            )
        else:
            value = await session.scalar(
                text(
                    "SELECT COALESCE(SUM(cost_usd), 0) FROM usage_records "
                    "WHERE created_at >= :since"
                ),
                {"since": _month_start()},
            )
    spent = Decimal(str(value or 0))
    _cache[key] = (time.monotonic(), spent)
    return spent


async def _firm_limits(tenant: TenantContext) -> tuple[Decimal, Decimal]:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(text("SELECT monthly_soft_usd, monthly_hard_usd FROM budgets"))
        ).first()
    if row is None:
        return settings().firm_budget_usd
    return Decimal(str(row[0])), Decimal(str(row[1]))


def _period(level: str) -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%d") if level == "platform" else now.strftime("%Y-%m")


async def _publish_soft_crossed(tenant_id: UUID, level: str, engagement_id: UUID | None) -> None:
    """Audit and publish the crossing once per level and period (SPEC-013: firm admins, and an
    engagement's partner and managers, are notified). Never blocks the call it was found on."""
    ctx = TenantContext(tenant_id, "system", "budget:monitor")
    scoped = engagement_id if level == "engagement" else None
    try:
        async with uow(ctx) as tx:
            tx.record(
                "budget.soft_crossed",
                target=Target("engagement", scoped) if scoped else Target("firm", tenant_id),
            )
            tx.emit(
                BudgetSoftCrossed(
                    level="engagement" if level == "engagement" else "firm",
                    engagement_id=scoped,
                )
            )
    except Exception as exc:
        _log.warning("budget.soft_crossed_unpublished", error=type(exc).__name__)


async def check_budget(
    tenant: TenantContext, engagement_id: UUID | None, essential: bool, estimate: Decimal
) -> None:
    """Return if the call may go ahead; else raise `BudgetExhausted` or `NotAdmitted`."""
    s = settings()
    try:
        levels: list[tuple[str, Decimal, tuple[Decimal, Decimal]]] = [
            ("platform", await _sum(tenant, "platform", None), s.platform_daily_budget_usd),
            ("firm", await _sum(tenant, "firm", None), await _firm_limits(tenant)),
        ]
        if engagement_id is not None:
            spent = await _sum(tenant, "engagement", engagement_id)
            levels.append(("engagement", spent, s.engagement_budget_usd))
    except Exception as exc:
        _log.warning("budget.unavailable", error=exc)
        if essential:
            return
        _refused.add(1, {"reason": "unavailable", "outcome": "refused"})
        raise BudgetExhausted("budgets unavailable") from None
    for level, spent, (soft, hard) in levels:
        after = spent + estimate
        if after > hard and (level == "platform" or not essential):
            _refused.add(1, {"reason": level, "outcome": "refused"})
            _log.info("budget.refused", level=level, tenant_id=tenant.tenant_id)
            raise BudgetExhausted(f"{level} hard limit")
        if after > soft:
            scope = engagement_id if level == "engagement" else tenant.tenant_id
            key = (level, scope, _period(level))
            if key not in _alerted:
                _alerted.add(key)
                _crossed.add(1, {"reason": level})
                _log.warning("budget.soft_crossed", level=level, tenant_id=tenant.tenant_id)
                if level != "platform":  # the platform's own limit is an operator alert only
                    await _publish_soft_crossed(tenant.tenant_id, level, engagement_id)
            if not essential:
                _refused.add(1, {"reason": level, "outcome": "deferred"})
                raise NotAdmitted("deferred", DEFER_SECONDS)


ANOMALY_INTERVAL_SECONDS: Final = 3600
# The job reads across firms only through `engagement_spend_anomalies` (SECURITY DEFINER), which
# returns identifiers; the nil tenant matches no row under row-level security.
_PLATFORM = TenantContext(UUID(int=0), "system", "budget:anomaly")
_anomalies = meter(__name__).create_counter(
    "abacus.budget.anomaly", description="Engagements spending past the anomaly multiple"
)


async def flag_anomalies() -> int:
    """Log and count each engagement whose last hour passes the anomaly rule (SPEC-007 AC-6).
    It only alerts; it never blocks (Q5)."""
    s = settings()
    async with tenant_session(_PLATFORM) as session:
        rows = (
            await session.execute(
                text("SELECT tenant_id, engagement_id FROM engagement_spend_anomalies(:m, :f)"),
                {"m": s.anomaly_multiple, "f": s.anomaly_floor_usd},
            )
        ).all()
    for tenant_id, engagement_id in rows:
        _anomalies.add(1)
        _log.warning("budget.anomaly", tenant_id=tenant_id, engagement_id=engagement_id)
        async with uow(TenantContext(tenant_id, "system", "budget:anomaly")) as tx:
            tx.record("budget.anomaly", target=Target("engagement", engagement_id))
            tx.emit(BudgetAnomaly(engagement_id=engagement_id))
    return len(rows)


async def run_anomaly_job(stop: asyncio.Event) -> None:
    """Hourly until `stop`. A failed run is logged and retried next hour."""
    while not stop.is_set():
        try:
            await flag_anomalies()
        except Exception as exc:
            _log.warning("budget.anomaly_failed", error=exc)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), ANOMALY_INTERVAL_SECONDS)


@dataclass(frozen=True)
class FirmBudget:
    monthly_soft_usd: Decimal
    monthly_hard_usd: Decimal
    plan_cap_usd: Decimal
    spent_this_month_usd: Decimal
    is_default: bool


@dataclass(frozen=True)
class SpendLine:
    engagement_id: UUID | None
    agent_id: str | None
    cost_usd: Decimal


async def firm_budget(tenant: TenantContext) -> FirmBudget:
    """The firm's monthly budget (the defaults without a row) and this month's spend."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(text("SELECT monthly_soft_usd, monthly_hard_usd FROM budgets"))
        ).first()
        spent = await session.scalar(
            text("SELECT COALESCE(SUM(cost_usd), 0) FROM usage_records WHERE created_at >= :s"),
            {"s": _month_start()},
        )
    s = settings()
    soft, hard = (Decimal(str(row[0])), Decimal(str(row[1]))) if row else s.firm_budget_usd
    return FirmBudget(soft, hard, s.firm_budget_cap_usd, Decimal(str(spent)), row is None)


async def save_firm_budget(
    session: AsyncSession, tenant_id: UUID, user_id: UUID, soft: Decimal, hard: Decimal
) -> None:
    """Insert or replace the firm's row, inside the caller's unit of work (which audits it)."""
    await session.execute(
        text(
            "INSERT INTO budgets (tenant_id, monthly_soft_usd, monthly_hard_usd, updated_by) "
            "VALUES (:tenant, :soft, :hard, :by) "
            "ON CONFLICT (tenant_id) DO UPDATE SET monthly_soft_usd = EXCLUDED.monthly_soft_usd, "
            "monthly_hard_usd = EXCLUDED.monthly_hard_usd, updated_by = EXCLUDED.updated_by, "
            "updated_at = now()"
        ),
        {"tenant": tenant_id, "soft": soft, "hard": hard, "by": user_id},
    )
    forget_spend()


async def spend_by_engagement_and_agent(
    tenant: TenantContext, period: Literal["day", "month"]
) -> list[SpendLine]:
    """The firm's spend this day or month, per engagement and agent (SPEC-007 AC-8)."""
    since = (
        _month_start()
        if period == "month"
        else datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    )
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT engagement_id, agent_id, SUM(cost_usd) FROM usage_records "
                    "WHERE created_at >= :s GROUP BY engagement_id, agent_id "
                    "ORDER BY engagement_id, agent_id"
                ),
                {"s": since},
            )
        ).all()
    return [SpendLine(e, a, Decimal(str(c))) for e, a, c in rows]
