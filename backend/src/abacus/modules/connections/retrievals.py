"""Starting retrieval workflows from the API (TASK-010 design §7, revision 1). PROTECTED.

The workflow is bound to its run (`retrieval:<run_id>`): a new run always gets its own workflow,
and starting again for the same run attaches to the one already running. Only a run this request
created is ended when its workflow can't be started; someone else's run is left alone.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import ServiceUnavailable
from abacus.modules.connections.connector import Period
from abacus.modules.connections.pipeline import fail_run
from abacus.modules.connections.service import (
    RetrievalView,
    load_system_context,
    run_view,
    start_retrieval,
)
from abacus.modules.connections.workflow_types import RetrievalInput
from abacus.modules.connections.workflows import RetrievalWorkflow
from abacus.modules.engagements.api import gate_client_data
from abacus.modules.identity.api import AuthContext

EXECUTION_TIMEOUT_HOURS = 6
# Each workflow's work class (ADR-071; SPEC-003 Q1): a person waits on a retrieval they start.
# Registered here, beside the only code that starts it, so it can't be started unregistered.
WORKFLOWS: dict[type, WorkClass] = {RetrievalWorkflow: "interactive"}
register_work_classes(WORKFLOWS)
WORKFLOW_UNAVAILABLE = "workflow_unavailable"


class WorkflowUnavailable(ServiceUnavailable):
    """The run's workflow couldn't be started; a run this request created is ended as failed."""


def workflow_id(run_id: UUID) -> str:
    return f"retrieval:{run_id}"


async def _start(tenant_id: UUID, run_id: UUID) -> None:
    await dispatch(
        RetrievalWorkflow,
        RetrievalInput(str(tenant_id), str(run_id)),
        id=workflow_id(run_id),
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        execution_timeout=timedelta(hours=EXECUTION_TIMEOUT_HOURS),
    )


async def trigger_retrieval(
    ctx: AuthContext, *, engagement_id: UUID, request_item_id: UUID, period: Period
) -> RetrievalView:
    """Record the run (`start_retrieval`) and make sure its workflow is running."""
    await gate_client_data(ctx, engagement_id, "evidence.upload")  # SPEC-025 AC-7
    started = await start_retrieval(
        ctx, engagement_id=engagement_id, request_item_id=request_item_id, period=period
    )
    view = await run_view(ctx.tenant, started.run_id)
    if view.status != "running":
        return view
    try:
        await _start(ctx.tenant_id, started.run_id)
    except Exception:
        if started.created:
            system = await load_system_context(ctx.tenant_id, started.run_id)
            await fail_run(system, "failed", WORKFLOW_UNAVAILABLE)
        raise WorkflowUnavailable("retrieval workflow could not be started") from None
    return view
