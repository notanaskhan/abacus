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

On a methodology template (SPEC-035 Q3; TASK-074) a firm admin or practice leader asks
(`template_guidance.request`), reads (`template_guidance.read`) and decides
(`template_guidance.decide`); an approval keeps the final text on its decision, and publishing
makes the template's next version with it (D2, `methodology.manage` with fresh MFA).
"""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.kernel import _flags
from abacus.kernel.clock import system_now
from abacus.kernel.db import tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.events import GuidanceDraftDecided
from abacus.modules.agents.guidance_checks import check_draft
from abacus.modules.agents.guidance_draft import DRAFTER, model_available, template_item
from abacus.modules.agents.handoff import GuidanceDraft
from abacus.modules.agents.repository import (
    get_guidance_draft,
    get_template_draft,
    insert_draft_decision,
    insert_template_decision,
    pending_guidance_drafts,
    template_drafts,
)
from abacus.modules.agents.spec import spec
from abacus.modules.agents.workflow_types import GuidanceDraftInput
from abacus.modules.agents.workflows import GuidanceDraftWorkflow
from abacus.modules.engagements.api import (
    ApprovedGuidance,
    Effort,
    TemplateVersionSummary,
    get_ref,
    methodology_version,
    publish_drafted_version,
)
from abacus.modules.identity.api import AuthContext, Resource, authorise
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
    event = uuid5(NAMESPACE_URL, f"abacus:draft:{ctx.tenant_id}:{engagement_id}:{system_now()}")
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
        tx.emit(GuidanceDraftDecided(engagement_id=engagement_id))  # P-04-T16
    return len(approvals)


# --- On a methodology template (SPEC-035 Q3; TASK-074) ------------------------------------------


class NothingToPublish(DomainConflict):
    """No approved drafted guidance on this version yet."""

    code = "nothing_to_publish"


@dataclass(frozen=True)
class TemplateDraftStarted:
    positions: tuple[int, ...]


async def request_template_drafts(
    ctx: AuthContext, version_id: UUID, positions: Sequence[int] | None
) -> TemplateDraftStarted:
    """AC-1 on a template: drafts for the named items, or for every item without guidance and
    without a draft awaiting a decision or approved. One firm-level run each (D1)."""
    firm = Resource.firm(ctx.tenant_id)
    await authorise(ctx, "template_guidance.request", firm)
    if not await flag_enabled(ctx.tenant, _flags.GUIDANCE_DRAFTING) or not model_available():
        raise DraftingUnavailable(str(version_id))
    version = await methodology_version(ctx, version_id)
    named = set(positions or ())
    if any(not 0 <= p < len(version.items) for p in named):
        raise NotFound("template_item")
    async with tenant_session(ctx.tenant) as session:
        drafted = {
            d.position
            for d, c in await template_drafts(session, version_id)
            if c is None or c.decision == "approved"
        }
    chosen = [
        i
        for i, t in enumerate(version.items)
        if (i in named if named else not (t.why or t.good_looks_like or i in drafted))
    ][:MAX_ITEMS]
    event = uuid5(NAMESPACE_URL, f"abacus:draft:{ctx.tenant_id}:{version_id}:{system_now()}")
    async with uow(ctx.tenant) as tx:
        tx.record(
            "guidance_draft.requested",
            target=Target("methodology_version", version_id),
            after=Ref(items=len(chosen), user_id=ctx.user_id),
        )
    for position in chosen:
        with suppress(WorkflowAlreadyStartedError):
            await dispatch(
                GuidanceDraftWorkflow,
                GuidanceDraftInput(
                    str(ctx.tenant_id),
                    "",
                    "",
                    str(event),
                    str(ctx.user_id),
                    methodology_version_id=str(version_id),
                    position=position,
                ),
                id=f"guidance_draft:{ctx.tenant_id}:{version_id}:{position}:{event}",
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            )
    return TemplateDraftStarted(tuple(chosen))


@dataclass(frozen=True)
class TemplateDraftView:
    id: UUID
    position: int
    why: str
    good_looks_like: str
    effort: str | None
    effort_reason: str | None
    blocks_fieldwork: bool | None
    blocks_reason: str | None
    created_at: datetime
    status: str  # pending | approved (discarded drafts aren't listed)
    approved_by: UUID | None


async def template_drafts_for(ctx: AuthContext, version_id: UUID) -> list[TemplateDraftView]:
    """Per template item, its newest draft that passed code's checks, awaiting a decision or
    approved (and so waiting to be published); never one that failed or was discarded."""
    await authorise(ctx, "template_guidance.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        rows = await template_drafts(session, version_id)
    return [
        TemplateDraftView(
            d.id,
            d.position,
            c.why or d.why if c is not None else d.why,
            c.good_looks_like or d.good_looks_like if c is not None else d.good_looks_like,
            c.effort if c is not None else d.effort,
            d.effort_reason,
            c.blocks_fieldwork if c is not None else d.blocks_fieldwork,
            d.blocks_reason,
            d.created_at,
            "approved" if c is not None else "pending",
            c.decided_by if c is not None else None,
        )
        for d, c in rows
        if c is None or c.decision == "approved"
    ]


async def decide_template_drafts(
    ctx: AuthContext,
    version_id: UUID,
    approvals: Sequence[Approval],
    *,
    discard: bool = False,
    confirmed_read: bool = False,
) -> int:
    """AC-4 on a template: approve (each edit checked again; the final text is kept on the
    decision) or discard drafts, in one unit of work. Nothing reaches engagements until a new
    version is published (D2). More than one approval at a time needs `confirmed_read` (Q5)."""
    await authorise(ctx, "template_guidance.decide", Resource.firm(ctx.tenant_id))
    if not discard and len(approvals) > 1 and not confirmed_read:
        raise ReadNotConfirmed(str(version_id))
    version = await methodology_version(ctx, version_id)
    async with uow(ctx.tenant) as tx:
        for a in approvals:
            row = await get_template_draft(tx.session, a.draft_id)
            if row is None or row.methodology_version_id != version_id or not row.passed_checks:
                raise NotFound("guidance_draft")
            why = a.why if a.why is not None else row.why
            good = a.good_looks_like if a.good_looks_like is not None else row.good_looks_like
            edited = (why, good) != (row.why, row.good_looks_like)
            if not discard and edited:
                item = template_item(version, row.position)
                try:
                    text = GuidanceDraft(why=why, good_looks_like=good)
                except ValueError:
                    raise EditedDraftRefused(str(a.draft_id)) from None
                if item is None or check_draft(
                    text, description=item["description"], area=item["audit_area"]
                ):
                    raise EditedDraftRefused(str(a.draft_id))
            made = await insert_template_decision(
                tx.session,
                tenant_id=ctx.tenant_id,
                draft_id=a.draft_id,
                decision="discarded" if discard else "approved",
                why=None if discard else why,
                good_looks_like=None if discard else good,
                effort=None if discard else (a.effort if a.effort is not None else row.effort),
                blocks_fieldwork=None
                if discard
                else (
                    a.blocks_fieldwork if a.blocks_fieldwork is not None else row.blocks_fieldwork
                ),
                edited=edited and not discard,
                confirmed_read=confirmed_read or len(approvals) == 1,
                decided_by=ctx.user_id,
            )
            if not made:
                raise DraftAlreadyDecided(str(a.draft_id))
            tx.record(
                "guidance_draft.discarded" if discard else "guidance_draft.approved",
                target=Target("methodology_version", version_id),
                after=Ref(
                    draft_id=a.draft_id, position=row.position, edited=int(edited and not discard)
                ),
            )
    return len(approvals)


async def publish_template_drafts(ctx: AuthContext, version_id: UUID) -> TemplateVersionSummary:
    """D2: the template's next version, with every approved draft's text on its item (source
    `drafted`, with who approved). `methodology.manage` with fresh MFA (D3)."""
    await authorise(ctx, "template_guidance.decide", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        approved = [
            ApprovedGuidance(
                d.position,
                c.why or d.why,
                c.good_looks_like or d.good_looks_like,
                cast(Effort | None, c.effort),
                bool(c.blocks_fieldwork),
                c.decided_by,
            )
            for d, c in await template_drafts(tx.session, version_id)
            if c is not None and c.decision == "approved"
        ]
        if not approved:
            raise NothingToPublish(str(version_id))
        return await publish_drafted_version(tx, ctx, version_id, approved)
