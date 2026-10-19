"""The entry assessor in the product (SPEC-037 Q4; TASK-085). PROTECTED.

"Assess with AI" (`entry_assessment.request`: partner, manager, senior, staff) starts one
`EntryAssessWorkflow` per selected entry with a document to read and no assessment yet (or the
named entries), when the firm's `fieldwork.assessor` flag is on and a real model route exists;
the gateway still refuses a real firm until SPEC-036 clears the agent. The team reads each entry's
newest shown assessment (`procedure.read`); nothing is pre-filled into results (ADR-005).
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, UUID, uuid5

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel import _flags
from abacus.kernel.db import tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.entry_assess import ASSESSOR, model_available
from abacus.modules.agents.repository import newest_assessments
from abacus.modules.agents.spec import spec
from abacus.modules.agents.workflow_types import EntryAssessInput
from abacus.modules.agents.workflows import EntryAssessWorkflow
from abacus.modules.engagements.api import get_ref
from abacus.modules.fieldwork.api import assessable_items, selection_item_ids
from abacus.modules.identity.api import AuthContext, authorise

WORKFLOWS: dict[type, WorkClass] = {EntryAssessWorkflow: spec(ASSESSOR).work_class}
register_work_classes(WORKFLOWS)
MAX_ENTRIES = 200


class AssessorUnavailable(DomainConflict):
    """The flag is off, or no real model route is enabled here."""

    code = "ai_assessor_unavailable"


async def request_assessments(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, item_ids: Sequence[UUID] | None
) -> tuple[UUID, ...]:
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "entry_assessment.request", engagement.resource())
    if not await flag_enabled(ctx.tenant, _flags.FIELDWORK_ASSESSOR) or not model_available():
        raise AssessorUnavailable(str(engagement_id))
    ready = await assessable_items(ctx, engagement_id, procedure_id)
    if item_ids:
        chosen = [i for i in ready if i in set(item_ids)]
    else:
        async with tenant_session(ctx.tenant) as session:
            done = {
                a.selected_item_id
                for a in await newest_assessments(session, ctx, engagement_id, ready)
            }
        chosen = [i for i in ready if i not in done]
    chosen = chosen[:MAX_ENTRIES]
    event = uuid5(NAMESPACE_URL, f"abacus:assess:{procedure_id}:{datetime.now()}")
    async with uow(ctx.tenant) as tx:
        tx.record(
            "entry_assessment.requested",
            target=Target("procedure", procedure_id),
            after=Ref(items=len(chosen), user_id=ctx.user_id),
        )
    for item_id in chosen:
        with suppress(WorkflowAlreadyStartedError):
            await dispatch(
                EntryAssessWorkflow,
                EntryAssessInput(
                    str(ctx.tenant_id),
                    str(engagement_id),
                    str(item_id),
                    str(event),
                    str(ctx.user_id),
                ),
                id=f"entry_assess:{ctx.tenant_id}:{item_id}:{event}",
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            )
    return tuple(chosen)


@dataclass(frozen=True)
class AssessmentView:
    selected_item_id: UUID
    verdict: str  # as shown
    rationale: str
    citations: tuple[dict[str, object], ...]
    created_at: datetime


async def assessments_of(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID
) -> list[AssessmentView]:
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", engagement.resource())
    items = await selection_item_ids(ctx, engagement_id, procedure_id)
    async with tenant_session(ctx.tenant) as session:
        rows = await newest_assessments(session, ctx, engagement_id, items)
    return [
        AssessmentView(
            r.selected_item_id, r.shown_verdict, r.rationale, tuple(r.citations), r.created_at
        )
        for r in rows
    ]
