"""Starting retrievals from the API and reading their status (TASK-010 design §7, Q4).
PROTECTED."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.service import RPCError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.temporal import temporal_client
from abacus.modules.connections.connector import Period
from abacus.modules.connections.pipeline import fail_run
from abacus.modules.connections.repository import get_run
from abacus.modules.connections.service import load_system_context, start_retrieval
from abacus.modules.connections.workflow_types import RetrievalInput
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, authorise


class WorkflowUnavailable(Exception):
    """The run was recorded but its workflow couldn't be started; the run is ended as failed."""


@dataclass(frozen=True)
class RetrievalView:
    sync_run_id: UUID
    request_item_id: UUID
    status: str
    failure_code: str | None
    evidence_version_id: UUID | None


def workflow_id(request_item_id: UUID, period: Period) -> str:
    """One workflow per item and period (§12): a duplicate start attaches to the running one."""
    return f"retrieval:{request_item_id}:{period.start.isoformat()}_{period.end.isoformat()}"


async def _view(tenant: TenantContext, run_id: UUID) -> RetrievalView:
    async with tenant_session(tenant) as session:
        run = await get_run(session, run_id)
    if run is None:
        raise NotFound("sync_run")
    return RetrievalView(
        run.id, run.request_item_id, run.status, run.failure_code, run.evidence_version_id
    )


async def trigger_retrieval(
    ctx: AuthContext, *, engagement_id: UUID, request_item_id: UUID, period: Period
) -> RetrievalView:
    """Record the run (`start_retrieval`), then start its workflow. A running workflow for the
    same item and period is reused. If Temporal can't be reached, the run is ended as failed
    (`workflow_unavailable`) rather than left running with nothing behind it."""
    run_id = await start_retrieval(
        ctx, engagement_id=engagement_id, request_item_id=request_item_id, period=period
    )
    view = await _view(ctx.tenant, run_id)
    if view.status != "running":
        return view
    try:
        client = await temporal_client()
        await client.start_workflow(
            "retrieval",
            RetrievalInput(str(ctx.tenant_id), str(run_id)),
            id=workflow_id(request_item_id, period),
            task_queue=settings().temporal_task_queue,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    except (RPCError, OSError, RuntimeError):
        system = await load_system_context(ctx.tenant_id, run_id)
        await fail_run(system, "failed", "workflow_unavailable")
        raise WorkflowUnavailable("retrieval workflow could not be started") from None
    return view


async def retrieval_status(
    ctx: AuthContext, *, engagement_id: UUID, run_id: UUID
) -> RetrievalView:
    """A retrieval's state for anyone who may read the engagement's request items (Q4)."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "request_item.read", engagement.resource())
    async with tenant_session(ctx.tenant) as session:
        run = await get_run(session, run_id)
    if run is None or run.engagement_id != engagement_id:
        raise NotFound("sync_run")
    return RetrievalView(
        run.id, run.request_item_id, run.status, run.failure_code, run.evidence_version_id
    )
