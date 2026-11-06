"""What the statements workflows run, and what starts them (A-06-T25; A-06 §4.5). The person's
route authorised the request; the activity proves its context from the run and version rows."""

from __future__ import annotations

from uuid import UUID

from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.db import TenantContext
from abacus.kernel.dispatch import dispatch
from abacus.kernel.uow import OutboxEvent
from abacus.modules.reporting import statements
from abacus.modules.reporting.statements_workflow_types import FsDraftInput, TieOutInput
from abacus.modules.reporting.statements_workflows import (
    DRAFT_ACTIVITY,
    DRAFT_FAILED_ACTIVITY,
    TIE_OUT_ACTIVITY,
    FsDraftWorkflow,
    TieOutWorkflow,
)


def _system(tenant_id: str) -> TenantContext:
    return TenantContext(UUID(tenant_id), "system", "reporting:statements")


@activity.defn(name=DRAFT_ACTIVITY)
async def draft_activity(given: FsDraftInput) -> str:
    version_id, _ = await statements.draft_in_run(_system(given.tenant_id), UUID(given.run_id))
    return str(version_id)


@activity.defn(name=DRAFT_FAILED_ACTIVITY)
async def draft_failed_activity(given: FsDraftInput) -> None:
    await statements.fail_draft_run(_system(given.tenant_id), UUID(given.run_id))


@activity.defn(name=TIE_OUT_ACTIVITY)
async def tie_out_activity(given: TieOutInput) -> str:
    found = await statements.run_tie_out(
        _system(given.tenant_id), UUID(given.statement_version_id)
    )
    return str(found["id"])


ACTIVITIES = (draft_activity, draft_failed_activity, tie_out_activity)


async def on_draft_requested(event: OutboxEvent) -> None:
    run = str(event.payload["run_id"])
    await dispatch(
        FsDraftWorkflow,
        FsDraftInput(
            str(event.tenant_id),
            run,
            str(event.payload["engagement_id"]),
            str(event.payload["work_item_id"]),
        ),
        id=f"fs_draft:{event.tenant_id}:{run}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def on_tie_out_requested(event: OutboxEvent) -> None:
    version = str(event.payload["statement_version_id"])
    await dispatch(
        TieOutWorkflow,
        TieOutInput(str(event.tenant_id), version),
        # A later request on the same version runs again: the run row is insert-only.
        id=f"tie_out:{event.tenant_id}:{version}:{event.event_id}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
