"""`BringDown` (A-07-T23; TASK-6207; DEC-2807; A-07 F2, I-CLOCKS; ADR-090): the report-date
bring-down at 09:00 firm time on the report date.

A durable Temporal timer fires once at 09:00 in the firm's time zone on the report date (Northwind:
9:00 AM CDT on Fri Oct 9, 2026). If the report date moves, `report_date_changed` re-arms it to the
new date's 09:00. When it fires, the activity `assurance.bring_down`:

- reads the subsequent-events procedures and records how many were performed through the report
  date (it performs none: a procedure is a person's act);
- asks every engagement team member to reconfirm independence through the report date
  (`independence.reconfirmation_requested`, one outbox event per member);
- records `bring_down.completed` with those counts. It never records a going-concern conclusion,
  a subsequent event, or any decision (INV-1).

The starter (`schedule_bring_down`) starts the workflow, or signals the running one, only when the
firm's `assurance_release_mode` is `in_app` **and** its `audits.completion` flag is on (A-07-T33,
DEC-3106): no workflow starts and no timer exists while the flag is off. Fire times are computed
outside the workflow (UTC instants in the input and the signal), so the workflow stays
deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, ClassVar, Final
from uuid import UUID
from zoneinfo import ZoneInfo

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from sqlalchemy import select, text

    from abacus.kernel.classification import classified
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
    from abacus.modules.identity.api import engagement_team_query

BRING_DOWN_ID_PREFIX: Final = "bring_down:"
FIRES_AT: Final = time(9, 0)


@dataclass(frozen=True)
class BringDownInput:
    tenant_id: str
    work_item_id: str
    engagement_id: str
    report_date: str  # ISO date
    fire_at: str  # ISO UTC instant: 09:00 firm time on the report date


@dataclass(frozen=True)
class BringDownResult:
    report_date: str
    procedures: int
    performed_through_report_date: int
    reconfirmations_requested: int


@dataclass(frozen=True)
class ReportDateMoved:
    report_date: str
    fire_at: str


def fire_at(report_date: date, time_zone: str) -> datetime:
    """09:00 on the report date in the firm's zone, as a UTC instant (DST-aware)."""
    local = datetime.combine(report_date, FIRES_AT, tzinfo=ZoneInfo(time_zone))
    return local.astimezone(UTC)


@workflow.defn(name="BringDown")
class BringDownWorkflow:
    def __init__(self) -> None:
        self._report_date: str = ""
        self._fire_at: str = ""
        self._moved = False

    @workflow.signal
    def report_date_changed(self, moved: ReportDateMoved) -> None:
        self._report_date = moved.report_date
        self._fire_at = moved.fire_at
        self._moved = True

    @workflow.run
    async def run(self, params: BringDownInput) -> BringDownResult:
        # A signal delivered with the start (signal-with-start, or one queued before the first
        # task) runs before `run`: its date is newer than the start's, so it stands (S31 end pass).
        if not self._moved:
            self._report_date = params.report_date
            self._fire_at = params.fire_at
        while True:
            self._moved = False
            wait = datetime.fromisoformat(self._fire_at) - workflow.now()
            if wait <= timedelta(0):
                break
            try:
                await workflow.wait_condition(lambda: self._moved, timeout=wait)
            except TimeoutError:  # the timer fired: the report date's 09:00
                break
            # moved: re-arm on the new date's 09:00
        return await workflow.execute_activity(
            "assurance.bring_down",
            args=[params.tenant_id, params.work_item_id, params.engagement_id, self._report_date],
            result_type=BringDownResult,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


class IndependenceReconfirmationRequested(DomainEvent):
    """A team member is asked to reconfirm independence through the report date (AU-C 220)."""

    event_type: ClassVar[str] = "independence.reconfirmation_requested"

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]
    through: Annotated[date, classified("internal")]


_PROCEDURES = text(
    "SELECT count(*) AS total, count(*) FILTER (WHERE status = 'performed' "
    "AND performed_through >= :through) AS through FROM subsequent_event_procedures "
    "WHERE work_item_id = :wi"
)


@activity.defn(name="assurance.bring_down")
async def bring_down(
    tenant_id: str, work_item_id: str, engagement_id: str, report_date: str
) -> BringDownResult:
    tenant = TenantContext(UUID(tenant_id), "system", "bring_down")
    wi, engagement = UUID(work_item_id), UUID(engagement_id)
    through = date.fromisoformat(report_date)
    async with tenant_session(tenant) as session:
        counts = (await session.execute(_PROCEDURES, {"wi": wi, "through": through})).one()
        members = engagement_team_query().subquery()
        team = sorted(
            set(
                (
                    await session.execute(
                        select(members.c.user_id).where(members.c.engagement_id == engagement)
                    )
                ).scalars()
            )
        )
    async with uow(tenant) as tx:
        for user_id in team:
            tx.emit(
                IndependenceReconfirmationRequested(
                    engagement_id=engagement, work_item_id=wi, user_id=user_id, through=through
                )
            )
        tx.record(
            "bring_down.completed",
            target=Target("work_item", wi),
            after=Ref(
                through=report_date,
                procedures=int(counts.total),
                performed=int(counts.through),
                reconfirmations=len(team),
            ),
            scope=Scope(engagement_id=engagement, work_item_id=wi),
        )
    # A-07-T32 (DEC-3109): the run #4240 the dock shows, as the EP via Agent; no model call.
    from abacus.modules.assurance.agent_capabilities import record_bring_down

    await record_bring_down(
        tenant,
        wi,
        engagement,
        procedures=int(counts.total),
        performed=int(counts.through),
        reconfirmations=len(team),
    )
    return BringDownResult(report_date, int(counts.total), int(counts.through), len(team))


async def schedule_bring_down(
    tenant: TenantContext,
    *,
    work_item_id: UUID,
    engagement_id: UUID,
    report_date: date,
    time_zone: str,
) -> bool:
    """Start the bring-down for a report date, or re-arm the running one (one workflow per work
    item, `bring_down:<work item>`); False while A-07 is dark, and then nothing starts."""
    from abacus.kernel.dispatch import signal_with_start
    from abacus.modules.assurance.completion_projector import projector_live

    if not await projector_live(tenant):
        return False
    instant = fire_at(report_date, time_zone).isoformat()
    await signal_with_start(
        BringDownWorkflow,
        BringDownInput(
            str(tenant.tenant_id),
            str(work_item_id),
            str(engagement_id),
            report_date.isoformat(),
            instant,
        ),
        id=f"{BRING_DOWN_ID_PREFIX}{work_item_id}",
        signal="report_date_changed",
        payload=ReportDateMoved(report_date.isoformat(), instant),
    )
    return True


__all__ = [
    "BRING_DOWN_ID_PREFIX",
    "BringDownInput",
    "BringDownResult",
    "BringDownWorkflow",
    "IndependenceReconfirmationRequested",
    "ReportDateMoved",
    "bring_down",
    "fire_at",
    "schedule_bring_down",
]
