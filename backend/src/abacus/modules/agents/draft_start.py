"""Drafted guidance in the product (SPEC-035; TASK-073). PROTECTED.

"Draft guidance" (`guidance_draft.request`, partner, manager, senior) starts one
`GuidanceDraftWorkflow` per chosen request item (`guidance_draft:<tenant>:<item>:<event>`, batch)
when the firm's `guidance.drafting` flag is on and a real model route exists; the gateway still
refuses a real firm (`data_boundary`, ADR-112). Items with the firm's own guidance are skipped
unless named. The firm reads pending drafts (`guidance_draft.read`): only drafts that passed
code's checks. A person approves (perhaps after editing; the edit is checked again) or discards
each (`guidance_draft.decide`); approval writes the item's guidance through requests, source
`drafted`, in the same unit of work (ADR-005). Clients see it only as the firm's setting allows
(requests, ADR-111).
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
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.guidance_checks import check_draft
from abacus.modules.agents.guidance_draft import DRAFTER, model_available
from abacus.modules.agents.handoff import GuidanceDraft
from abacus.modules.agents.repository import (
    get_guidance_draft,
    insert_draft_decision,
    pending_guidance_drafts,
)
from abacus.modules.agents.spec import spec
from abacus.modules.agents.workflow_types import GuidanceDraftInput
from abacus.modules.agents.workflows import GuidanceDraftWorkflow
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.requests.api import apply_drafted_guidance, request_items_for

WORKFLOWS: dict[type, WorkClass] = {GuidanceDraftWorkflow: spec(DRAFTER).work_class}
register_work_classes(WORKFLOWS)
MAX_ITEMS = 500


class DraftingUnavailable(DomainConflict):
    """The flag is off, or no real model route is enabled here."""

    code = "ai_drafting_unavailable"


class DraftAlreadyDecided(DomainConflict):
    code = "draft_already_decided"


class EditedDraftRefused(DomainInvalid):
    """The edited text fails the same checks a draft must pass (SPEC-035 §4.3)."""

    code = "edited_draft_refused"


class ReadNotConfirmed(DomainInvalid):
    """Bulk approval needs the person to confirm they read each draft (SPEC-035 Q5)."""

    code = "read_not_confirmed"


@dataclass(frozen=True)
class DraftStarted:
    items: tuple[UUID, ...]
    skipped: tuple[UUID, ...]  # the firm already wrote guidance on these


async def request_drafts(
    ctx: AuthContext, engagement_id: UUID, item_ids: Sequence[UUID] | None
) -> DraftStarted:
    """AC-1: drafts for the named items, or for every item without guidance."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "guidance_draft.request", engagement.resource())
    if not await flag_enabled(ctx.tenant, _flags.GUIDANCE_DRAFTING) or not model_available():
        raise DraftingUnavailable(str(engagement_id))
    items = await request_items_for(ctx, engagement_id)
    named = set(item_ids or ())
    chosen: list[UUID] = []
    skipped: list[UUID] = []
    for item in items:
        if named and item.id not in named:
            continue
        if not named and (item.why or item.good_looks_like):
            continue
        if not named and item.guidance_source == "firm":
            skipped.append(item.id)
            continue
        chosen.append(item.id)
    if named - {i.id for i in items}:
        raise NotFound("request_item")
    chosen = chosen[:MAX_ITEMS]
    event = uuid5(NAMESPACE_URL, f"abacus:draft:{ctx.tenant_id}:{engagement_id}:{datetime.now()}")
    async with uow(ctx.tenant) as tx:
        tx.record(
            "guidance_draft.requested",
            target=Target("engagement", engagement_id),
            after=Ref(items=len(chosen), user_id=ctx.user_id),
        )
    for item_id in chosen:
        with suppress(WorkflowAlreadyStartedError):
            await dispatch(
                GuidanceDraftWorkflow,
                GuidanceDraftInput(
                    str(ctx.tenant_id),
                    str(engagement_id),
                    str(item_id),
                    str(event),
                    str(ctx.user_id),
                ),
                id=f"guidance_draft:{ctx.tenant_id}:{item_id}:{event}",
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            )
    return DraftStarted(tuple(chosen), tuple(skipped))


@dataclass(frozen=True)
class DraftView:
    id: UUID
    request_item_id: UUID
    why: str
    good_looks_like: str
    effort: str | None
    effort_reason: str | None
    blocks_fieldwork: bool | None
    blocks_reason: str | None
    created_at: datetime


async def pending_drafts(ctx: AuthContext, engagement_id: UUID) -> list[DraftView]:
    """SPEC-035 §4.5: drafts awaiting a decision, firm roles only; never one that failed."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "guidance_draft.read", engagement.resource())
    async with tenant_session(ctx.tenant) as session:
        rows = await pending_guidance_drafts(session, ctx, engagement_id)
    return [
        DraftView(
            r.id,
            r.request_item_id,
            r.why,
            r.good_looks_like,
            r.effort,
            r.effort_reason,
            r.blocks_fieldwork,
            r.blocks_reason,
            r.created_at,
        )
        for r in rows
    ]


@dataclass(frozen=True)
class Approval:
    draft_id: UUID
    why: str | None = None  # None: as drafted
    good_looks_like: str | None = None
    effort: str | None = None
    blocks_fieldwork: bool | None = None


async def decide_drafts(
    ctx: AuthContext,
    engagement_id: UUID,
    approvals: Sequence[Approval],
    *,
    discard: bool = False,
    confirmed_read: bool = False,
) -> int:
    """AC-4: approve (each edit checked again) or discard drafts, in one unit of work; each draft
    gets its own decision. More than one at a time needs `confirmed_read` (Q5)."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "guidance_draft.decide", engagement.resource())
    if not discard and len(approvals) > 1 and not confirmed_read:
        raise ReadNotConfirmed(str(engagement_id))
    items = {i.id: i for i in await request_items_for(ctx, engagement_id)}
    async with uow(ctx.tenant) as tx:
        for a in approvals:
            row = await get_guidance_draft(tx.session, a.draft_id)
            if row is None or row.engagement_id != engagement_id or not row.passed_checks:
                raise NotFound("guidance_draft")
            why = a.why if a.why is not None else row.why
            good = a.good_looks_like if a.good_looks_like is not None else row.good_looks_like
            edited = (why, good) != (row.why, row.good_looks_like)
            if not discard and edited:
                try:
                    text = GuidanceDraft(why=why, good_looks_like=good)
                except ValueError:
                    raise EditedDraftRefused(str(a.draft_id)) from None
                item = items.get(row.request_item_id)
                if item is None or check_draft(
                    text, description=item.description, area=item.audit_area
                ):
                    raise EditedDraftRefused(str(a.draft_id))
            made = await insert_draft_decision(
                tx.session,
                tenant_id=ctx.tenant_id,
                draft_id=a.draft_id,
                decision="discarded" if discard else "approved",
                edited=edited and not discard,
                confirmed_read=confirmed_read or len(approvals) == 1,
                decided_by=ctx.user_id,
            )
            if not made:
                raise DraftAlreadyDecided(str(a.draft_id))
            if not discard:
                await apply_drafted_guidance(
                    tx,
                    ctx,
                    engagement_id,
                    row.request_item_id,
                    why=why,
                    good_looks_like=good,
                    effort=a.effort if a.effort is not None else row.effort,
                    blocks_fieldwork=(
                        a.blocks_fieldwork
                        if a.blocks_fieldwork is not None
                        else row.blocks_fieldwork
                    ),
                )
            tx.record(
                "guidance_draft.discarded" if discard else "guidance_draft.approved",
                target=Target("request_item", row.request_item_id),
                after=Ref(draft_id=a.draft_id, edited=int(edited and not discard)),
            )
    return len(approvals)
