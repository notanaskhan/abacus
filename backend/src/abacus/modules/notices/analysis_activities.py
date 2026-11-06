"""`NoticeAnalysisWorkflow`'s activities (N-04-T11): identifiers in, the run's status out."""

from __future__ import annotations

from uuid import UUID

from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.dispatch import dispatch
from abacus.kernel.uow import OutboxEvent
from abacus.modules.notices.analysis import complete_run, mark_failed
from abacus.modules.notices.analysis_workflow import NoticeAnalysisWorkflow
from abacus.modules.notices.analysis_workflow_types import NoticeAnalysisInput
from abacus.modules.notices.events import NoticeAnalysisRequested


@activity.defn(name="notice_analysis.run")
async def run_activity(given: NoticeAnalysisInput) -> str:
    return await complete_run(UUID(given.tenant_id), UUID(given.notice_id), given.version)


@activity.defn(name="notice_analysis.mark_failed")
async def mark_failed_activity(given: NoticeAnalysisInput) -> str:
    return await mark_failed(UUID(given.tenant_id), UUID(given.notice_id), given.version)


def workflow_id(tenant_id: UUID, notice_id: UUID, version: int) -> str:
    return f"notice_analysis:{tenant_id}:{notice_id}:{version}"


async def on_analysis_requested(event: OutboxEvent) -> None:
    notice_id = UUID(str(event.payload["notice_id"]))
    version = int(str(event.payload["version"]))
    await dispatch(
        NoticeAnalysisWorkflow,
        NoticeAnalysisInput(str(event.tenant_id), str(notice_id), version),
        id=workflow_id(event.tenant_id, notice_id, version),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


ACTIVITIES = (run_activity, mark_failed_activity)
SUBSCRIPTIONS = {NoticeAnalysisRequested.event_type: on_analysis_requested}
