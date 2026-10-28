"""Requests' part of a roll-forward (SPEC-025 AC-2; TASK-048 D1): last year's items for the
proposal, and the confirmed ones copied into the new engagement, registered with engagements."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.engagements.api import PriorItem, TemplateSeed
from abacus.modules.identity.api import Actor, AuthContext
from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.guidance import Guidance
from abacus.modules.requests.repository import (
    binder_items,
    insert_request_item,
    items_to_roll_forward,
    request_list_for,
    set_client_fields,
)
from abacus.modules.requests.service import insert_classified


async def proposed_items(ctx: Actor, prior_engagement_id: UUID) -> list[PriorItem]:
    if not isinstance(ctx, AuthContext):
        return []  # people roll forward, never agents or system runs
    async with tenant_session(ctx.tenant) as session:
        rows = await items_to_roll_forward(session, ctx, prior_engagement_id)
    return [
        PriorItem(
            r.id, r.description, r.audit_area, r.retrievability_tier, r.client_visible, r.status
        )
        for r in rows
    ]


async def copy_items(
    tx: UnitOfWork,
    ctx: AuthContext,
    engagement_id: UUID,
    prior_engagement_id: UUID,
    prior_item_ids: Sequence[UUID],
    seeds: Sequence[TemplateSeed],
) -> int:
    """The ticked items of last year, as they were (description, area, tier, dataset, client
    visibility; no client assignee, status `open`), then the ticked template additions."""
    wanted = set(prior_item_ids)
    prior = {
        r.id: r
        for r in await items_to_roll_forward(tx.session, ctx, prior_engagement_id)
        if r.id in wanted
    }
    if len(prior) != len(wanted):
        raise DomainInvalid("an item that isn't on the prior engagement")
    if not prior and not seeds:
        return 0
    list_id, created = await request_list_for(tx.session, ctx.tenant_id, engagement_id)
    if created:
        tx.record(
            "request_list.created",
            target=Target("request_list", list_id),
            after=Ref(engagement_id=engagement_id),
        )
    for old_id in prior_item_ids:
        old = prior[old_id]
        item_id = uuid4()
        await insert_request_item(
            tx.session,
            item_id=item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_list_id=list_id,
            description=old.description,
            audit_area=old.audit_area,
            created_by=ctx.user_id,
            retrievability_tier=old.retrievability_tier,
            dataset=old.dataset,
            tier_source=old.tier_source,
            tier_rule=old.tier_rule,
            document_kind=old.document_kind,  # SPEC-029 (TASK-055)
            document_kind_source=old.document_kind_source,
            guidance=Guidance(  # SPEC-031 AC-8; the still-needed note is last year's, not copied
                old.why,
                old.good_looks_like,
                old.blocks_fieldwork,
                old.effort,
                old.guidance_source,
                old.guidance_approved_by,
            ),
        )
        # Last year's visibility, either way: a new item defaults to visible, so an internal item
        # must be set back, or the roll-forward would show it to the client.
        await set_client_fields(tx.session, item_id, client_visible=old.client_visible)
        tx.record(
            "request_item.created",
            target=Target("request_item", item_id),
            after=Ref(engagement_id=engagement_id, rolled_forward_from=old_id),
        )
        tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
    for seed in seeds:
        t = seed.template
        await insert_classified(
            tx,
            ctx,
            engagement_id,
            list_id,
            seed.description,
            seed.audit_area,
            seed.tier,
            Guidance(
                t.why,
                t.good_looks_like,
                t.blocks_fieldwork,
                t.effort,
                t.guidance_source,
                t.guidance_approved_by,
            )
            if t
            else None,
        )
    return len(prior) + len(seeds)


async def count_prior_items(ctx: AuthContext, prior_engagement_id: UUID) -> int:
    """P-07-T55: how many requests last year's list has (ENG-13 "24 requests as Draft"), under
    `visible(roll_forward.read)` like the copy."""
    async with tenant_session(ctx.tenant) as session:
        return len(await items_to_roll_forward(session, ctx, prior_engagement_id))


async def copy_items_as_draft(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, prior_engagement_id: UUID
) -> int:
    """P-07-T55 (ENG-13, Story 7.1): last year's whole request list into the new engagement's,
    every item as Draft: the same wording, area, tier, dataset, document kind and guidance, no
    client assignee, no due date, and never client-visible (the status trigger keeps an item that
    is not client-visible `draft`), so the client sees nothing until the firm sends. Nothing the
    client uploaded moves: evidence stays on last year's items (ADR-004)."""
    prior = list(await items_to_roll_forward(tx.session, ctx, prior_engagement_id))
    if not prior:
        return 0
    list_id, created = await request_list_for(tx.session, ctx.tenant_id, engagement_id)
    if created:
        tx.record(
            "request_list.created",
            target=Target("request_list", list_id),
            after=Ref(engagement_id=engagement_id),
        )
    for old in prior:
        item_id = uuid4()
        await insert_request_item(
            tx.session,
            item_id=item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_list_id=list_id,
            description=old.description,
            audit_area=old.audit_area,
            created_by=ctx.user_id,
            retrievability_tier=old.retrievability_tier,
            dataset=old.dataset,
            tier_source=old.tier_source,
            tier_rule=old.tier_rule,
            document_kind=old.document_kind,
            document_kind_source=old.document_kind_source,
            guidance=Guidance(
                old.why,
                old.good_looks_like,
                old.blocks_fieldwork,
                old.effort,
                old.guidance_source,
                old.guidance_approved_by,
            ),
        )
        await set_client_fields(tx.session, item_id, client_visible=False)
        tx.record(
            "request_item.created",
            target=Target("request_item", item_id),
            after=Ref(engagement_id=engagement_id, rolled_forward_from=old.id),
        )
        tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
    return len(prior)


async def copy_binder_items(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    source_binder_id: UUID,
    binder_id: UUID,
    engagement_id: UUID,
    categories: dict[UUID, UUID],
) -> int:
    """P-06-T07 (Story 1.1): last year's binder's requests into a new Draft binder, by the same
    rules as `copy_items`: wording, area, tier, dataset, document kind and guidance as they
    were; the still-needed note dropped; no client assignee, no due date. Each keeps its section
    (`categories`: the source section's id -> the new one's) and is tagged `prior_year`. The
    caller authorised the source binder's read and the new binder's create."""
    copied = 0
    for old in await binder_items(tx.session, source_binder_id):
        item_id = uuid4()
        fields: dict[str, object] = {"kind": old.kind, "source_tag": "prior_year"}
        if old.title is not None:
            fields["title"] = old.title
        if old.category_id is not None and old.category_id in categories:
            fields["category_id"] = categories[old.category_id]
        await insert_request_item(
            tx.session,
            item_id=item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_list_id=binder_id,
            description=old.description,
            audit_area=old.audit_area,
            created_by=ctx.user_id,
            retrievability_tier=old.retrievability_tier,
            dataset=old.dataset,
            tier_source=old.tier_source,
            tier_rule=old.tier_rule,
            document_kind=old.document_kind,
            document_kind_source=old.document_kind_source,
            guidance=Guidance(
                old.why,
                old.good_looks_like,
                old.blocks_fieldwork,
                old.effort,
                old.guidance_source,
                old.guidance_approved_by,
            ),
            binder_fields=fields,
        )
        if not old.client_visible:  # a new item is client-visible by default (0028)
            await set_client_fields(tx.session, item_id, client_visible=False)
        tx.record(
            "request_item.created",
            target=Target("request_item", item_id),
            after=Ref(binder_id=binder_id, rolled_forward_from=old.id),
        )
        tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
        copied += 1
    return copied
