"""The nightly QM monitoring run (Q-05-T08; S51 partials, TASK-8733; DEC-5727; Q-05 §6
`AgentMonitoringWorkflow`). Dark behind `quality.management`.

Firm by firm with the flag on, inside the year's QM cycle:
- every agent whose 30-day override rate is above the firm's tolerance (rated agents only; the
  rates are code's, `compute/override_rates.py`) gets one open QM finding, `source =
  agent_monitoring`, raised by the system, never by the agent; 0963's partial unique index keeps
  one open finding per cycle and agent, so a second night adds nothing;
- a finding due today tells its owner (`qm_finding.due`); thirty days before the evaluation date
  the individual with ultimate responsibility is told (`qm_evaluation.due`).
One firm's failure is logged by id and the others run.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel._flags import QUALITY_MANAGEMENT
from abacus.kernel.classification import classified
from abacus.kernel.clock import now as clock_now
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.practice import overrides

EVALUATION_NOTICE_DAYS: Final = 30
_FINGERPRINT: Final = "practice.qm_finding"
_log = get_logger(__name__)


class QmFindingDue(DomainEvent):
    """A QM finding is due today: its owner is told (C16 `qm_finding_due`)."""

    event_type: ClassVar[str] = "qm_finding.due"

    qm_finding_id: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]


class QmEvaluationDue(DomainEvent):
    """Thirty days before the evaluation date (C16 `qm_evaluation_due`)."""

    event_type: ClassVar[str] = "qm_evaluation.due"

    recipient_user_ids: Annotated[list[UUID], classified("internal")]


_CYCLE = text("SELECT id FROM qm_cycles WHERE year = :y")
_NEXT_REF = text("SELECT count(*) + 1 FROM qm_findings")
_RAISE = text(
    "INSERT INTO qm_findings (tenant_id, cycle_id, ref, source, agent_key, title_sealed, "
    "raised_by_kind) VALUES (:t, :c, :ref, 'agent_monitoring', :agent, :title, 'system') "
    "ON CONFLICT (tenant_id, cycle_id, agent_key) "
    "WHERE source = 'agent_monitoring' AND status <> 'remediated' DO NOTHING RETURNING id"
)
_DUE = text(
    "SELECT id, owner_user_id FROM qm_findings WHERE status <> 'remediated' AND due_on = :d "
    "AND owner_user_id IS NOT NULL"
)
_SETTINGS = text(
    "SELECT evaluation_as_of_month_day, ultimate_responsible_user_id FROM qm_settings LIMIT 1"
)


def title_of(agent_key: str, rate: Decimal, tolerance: Decimal) -> str:
    return (
        f"Agent monitoring: {agent_key} overrides at {rate}% over 30 days, "
        f"above the {tolerance}% tolerance"
    )


def evaluation_notice_due(today: date, month_day: str) -> bool:
    """Thirty days before this year's evaluation date (a Feb 29 date reads Feb 28 off-leap)."""
    month, day = (int(p) for p in month_day.split("-"))
    try:
        evaluation = date(today.year, month, day)
    except ValueError:
        evaluation = date(today.year, month, day - 1)
    return today + timedelta(days=EVALUATION_NOTICE_DAYS) == evaluation


async def monitor(tenant_id: UUID, at: datetime) -> int:
    """One firm's night: the findings raised (0 when the cycle is not set up)."""
    tenant = TenantContext(tenant_id, "system", "practice:agent_monitoring")
    today = at.date()
    async with tenant_session(tenant) as session:
        cycle = await session.scalar(_CYCLE, {"y": today.year})
        due = [tuple(r) for r in await session.execute(_DUE, {"d": today})]
        settings = (await session.execute(_SETTINGS)).first()
    raised = 0
    if cycle is not None:
        rates = await overrides.overrides(tenant, at, "30d", None)
        tol = cast(Decimal, rates["tolerance_pct"])
        for row in cast(list[dict[str, object]], rates["rows"]):
            if not row["above_tolerance"]:
                continue
            agent = str(row["agent_key"])
            title = title_of(agent, cast(Decimal, row["rate"]), tol)
            sealed = await seal(tenant_id, title.encode(), _FINGERPRINT)
            async with uow(tenant) as tx:
                await tx.session.execute(
                    text("SELECT pg_advisory_xact_lock(hashtext('qm_finding_ref:' || :t))"),
                    {"t": str(tenant_id)},
                )
                number = int(cast(int, await tx.session.scalar(_NEXT_REF)))
                found = await tx.session.scalar(
                    _RAISE,
                    {"t": tenant_id, "c": cycle, "ref": f"QM-F-{number:02d}", "agent": agent,
                     "title": sealed},
                )  # fmt: skip
                if found is not None:
                    raised += 1
                    tx.record(
                        "qm_finding.raised",
                        target=Target("qm_finding", cast(UUID, found)),
                        after=Ref(number=number),
                    )
    notice = (
        settings is not None
        and settings[1] is not None
        and evaluation_notice_due(today, str(settings[0]))
    )
    if due or notice:
        async with uow(tenant) as tx:
            for finding_id, owner in due:
                tx.emit(
                    QmFindingDue(
                        qm_finding_id=cast(UUID, finding_id),
                        recipient_user_ids=[cast(UUID, owner)],
                    )
                )
                tx.record(
                    "qm_finding.due_notified", target=Target("qm_finding", cast(UUID, finding_id))
                )
            if notice and settings is not None:
                tx.emit(QmEvaluationDue(recipient_user_ids=[cast(UUID, settings[1])]))
                tx.record("qm_evaluation.due_notified", target=Target("firm", tenant_id))
    return raised


async def sweep(at: datetime) -> int:
    from abacus.modules.identity.api import firm_tenant_ids

    total = 0
    for tenant_id in await firm_tenant_ids():
        if activity.in_activity():
            activity.heartbeat(str(tenant_id))
        try:
            tenant = TenantContext(tenant_id, "system", "practice:agent_monitoring")
            if await flag_enabled(tenant, QUALITY_MANAGEMENT):
                total += await monitor(tenant_id, at)
        except Exception as exc:
            _log.error(
                "agent_monitoring.failed", tenant_id=str(tenant_id), error=type(exc).__name__
            )
    return total


@activity.defn(name="practice.agent_monitoring_sweep")
async def agent_monitoring_activity() -> int:
    return await sweep(await clock_now())


__all__ = [
    "QmEvaluationDue",
    "QmFindingDue",
    "agent_monitoring_activity",
    "evaluation_notice_due",
    "monitor",
    "sweep",
    "title_of",
]
