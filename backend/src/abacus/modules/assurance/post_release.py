"""After the release (A-07-T36; A-07 F7, §4.4; SPEC-644 AC-36; ADR-090, ADR-071).

`report.released` (A-07-T30's G8) starts three things, each once:
1. the archive opens Assembling (A-07-T31's `archive_gate.on_report_released`);
2. an EBP audit's Form 5500 row opens in the filings tracker (`filings.open_filing`);
3. `PostReleaseClocksWorkflow` (`post_release_clocks:<tenant>:<work_item>`, background) sleeps on
   durable timers to the archive's deadline - 7 days, the deadline and the day after, and AU-C
   265's due date and the day after. At each it asks the database whether that clock still runs
   (the archive not locked, the 265 letter not sent): if so, `archive.deadline_risk` reaches the
   engagement's leads (Hannah and Margaret); if not, the timer passes silently, which is how
   `archive.locked` and `governance_communication.sent` cancel it. When both clocks have
   stopped, the workflow ends.

The release is also the P-14 retention clock's anchor (`report_release`): the engagement's stored
evidence versions are locked to at least the firm's audit documentation retention from the
release (`evidence.api.extend_retention_for`), before the seal at lock re-asserts it (A-07-T37).
History: `post-release-clocks-v1.json`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from sqlalchemy import text

    from abacus.kernel import clock
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.uow import OutboxEvent, Ref, Scope, Target, uow
    from abacus.modules.assurance.clocks import Timer, timers

ID_PREFIX: Final = "post_release_clocks:"
_RETRY = RetryPolicy(maximum_attempts=10, initial_interval=timedelta(seconds=10))
_TIMEOUT = timedelta(minutes=2)
# Timers fire at 9 AM in the firm's zone on their day.
WAKE: Final = time(9, 0)


@dataclass(frozen=True)
class ClocksInput:
    tenant_id: str
    engagement_id: str
    work_item_id: str
    release_date: str  # ISO date, the firm's business date of the release


@dataclass(frozen=True)
class FireResult:
    running: bool  # the clock still runs (so it was reported)
    both_stopped: bool


def workflow_id(tenant_id: UUID, work_item_id: UUID) -> str:
    return f"{ID_PREFIX}{tenant_id}:{work_item_id}"


def wake_at(day: date) -> datetime:
    return datetime.combine(day, WAKE, tzinfo=clock.FIRM_ZONE)


@workflow.defn(name="PostReleaseClocksWorkflow")
class PostReleaseClocksWorkflow:
    @workflow.run
    async def run(self, p: ClocksInput) -> int:
        fired = 0
        for t in timers(date.fromisoformat(p.release_date)):
            wait = wake_at(t.at) - workflow.now()
            if wait > timedelta(0):
                await workflow.sleep(wait)
            result = await workflow.execute_activity(
                "assurance.post_release.fire",
                args=[
                    p.tenant_id,
                    p.engagement_id,
                    p.work_item_id,
                    t.kind,
                    t.event,
                    t.at.isoformat(),
                ],
                result_type=FireResult,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
            fired += int(result.running)
            if result.both_stopped:
                break
        return fired


_ARCHIVE_STOPPED: Final = "SELECT status = 'locked' FROM archives WHERE work_item_id = :wi"
_LETTER_SENT: Final = (
    "SELECT bool_or(status IN ('sent', 'acknowledged')) FROM governance_communications "
    "WHERE work_item_id = :wi AND kind = 'sd_mw_265'"
)


async def _stopped(tenant: TenantContext, work_item_id: UUID) -> dict[str, bool]:
    async with tenant_session(tenant) as session:
        archive = await session.scalar(text(_ARCHIVE_STOPPED), {"wi": work_item_id})
        letter = await session.scalar(text(_LETTER_SENT), {"wi": work_item_id})
    return {"archive": bool(archive), "au_c_265": bool(letter)}


@activity.defn(name="assurance.post_release.fire")
async def fire_activity(
    tenant_id: str, engagement_id: str, work_item_id: str, kind: str, boundary: str, at: str
) -> FireResult:
    """One timer: report it when its clock still runs."""
    from abacus.modules.assurance.events import ArchiveDeadlineRisk

    wi = UUID(work_item_id)
    tenant = TenantContext(UUID(tenant_id), "system", f"post_release:{work_item_id}")
    stopped = await _stopped(tenant, wi)
    running = not stopped.get(kind, True)
    if running:
        async with uow(tenant) as tx:
            tx.record(
                "archive.deadline_risk",
                target=Target("work_item", wi),
                after=Ref(clock=kind, boundary=boundary, deadline=at),
                scope=Scope(engagement_id=UUID(engagement_id), work_item_id=wi),
            )
            tx.emit(
                ArchiveDeadlineRisk(
                    engagement_id=UUID(engagement_id),
                    work_item_id=wi,
                    clock=kind,
                    boundary=boundary,
                    deadline=at,
                )
            )
    return FireResult(running, all(stopped.values()))


async def start_clocks(
    tenant_id: UUID, engagement_id: UUID, work_item_id: UUID, release_date: date
) -> str:
    from abacus.kernel.dispatch import dispatch

    run_id = workflow_id(tenant_id, work_item_id)
    await dispatch(
        PostReleaseClocksWorkflow,
        ClocksInput(
            str(tenant_id), str(engagement_id), str(work_item_id), release_date.isoformat()
        ),
        id=run_id,
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


async def on_report_released(event: OutboxEvent) -> None:
    """`report.released` → the archive, the EBP filing row, the clocks, the retention anchor."""
    from abacus.modules.assurance.archive_gate import on_report_released as open_archive
    from abacus.modules.assurance.release import released

    await open_archive(event)
    work_item_id = UUID(str(event.payload["work_item_id"]))
    engagement_id = UUID(str(event.payload["engagement_id"]))
    tenant = TenantContext(event.tenant_id, "system", f"post_release:{work_item_id}")
    done = await released(tenant, work_item_id)
    if done is None:
        return
    release_date = done.released_at.astimezone(clock.FIRM_ZONE).date()
    await _open_filing(tenant, engagement_id, work_item_id)
    await _letter_due(tenant, engagement_id, work_item_id, release_date)
    await _anchor_retention(tenant, engagement_id, done.released_at)
    await start_clocks(event.tenant_id, engagement_id, work_item_id, release_date)


async def _open_filing(tenant: TenantContext, engagement_id: UUID, work_item_id: UUID) -> None:
    from abacus.modules.assurance.filings import open_filing
    from abacus.modules.engagements.api import engagement_label

    label = await engagement_label(tenant, engagement_id)
    if label is None or label.type != "ebp_audit" or label.fiscal_period_end is None:
        return
    async with uow(tenant) as tx:
        await open_filing(
            tx,
            tenant_id=tenant.tenant_id,
            engagement_id=engagement_id,
            work_item_id=work_item_id,
            filer_name=label.client_entity_name or label.client_name,
            plan_year_end=label.fiscal_period_end,
        )


async def _letter_due(
    tenant: TenantContext, engagement_id: UUID, work_item_id: UUID, release_date: date
) -> None:
    """AUD-22's AU-C 265 item reads its due date from the release (60 days), before it is sent."""
    from abacus.modules.assurance.clocks import deadline

    due = deadline("au_c_265", release_date)
    async with uow(tenant) as tx:
        moved = await tx.session.scalar(
            text(
                "UPDATE governance_communications SET due_on = :due, version = version + 1 "
                "WHERE work_item_id = :wi AND kind = 'sd_mw_265' AND due_on IS NULL "
                "AND status NOT IN ('sent', 'acknowledged') RETURNING id"
            ),
            {"due": due, "wi": work_item_id},
        )
        if moved is not None:
            tx.record(
                "governance_communication.due_set",
                target=Target("governance_communication", UUID(str(moved))),
                after=Ref(due_on=due.isoformat()),
                scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
            )


async def _anchor_retention(
    tenant: TenantContext, engagement_id: UUID, released_at: datetime
) -> None:
    """P-14: the release anchors the audit documentation's retention (`report_release`)."""
    from abacus.modules.evidence.api import engagement_stored_versions, extend_retention_for

    versions = await engagement_stored_versions(tenant, engagement_id)
    await extend_retention_for(tenant, versions, "audit_documentation", "audit", released_at)


SUBSCRIPTIONS: Final = {"report.released": on_report_released}
WORKFLOWS: Final[dict[type, str]] = {PostReleaseClocksWorkflow: "background"}
ACTIVITIES: Final[tuple[object, ...]] = (fire_activity,)


def due_label(t: Timer) -> str:
    """For logs and tests: the timer as `<clock>:<boundary>@<date>` (identifiers only)."""
    return f"{t.kind}:{t.event}@{t.at.isoformat()}"
