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
from abacus.modules.requests.repository import (
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
        )
        if old.client_visible:
            await set_client_fields(tx.session, item_id, client_visible=True)
        tx.record(
            "request_item.created",
            target=Target("request_item", item_id),
            after=Ref(engagement_id=engagement_id, rolled_forward_from=old_id),
        )
        tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
    for seed in seeds:
        await insert_classified(
            tx, ctx, engagement_id, list_id, seed.description, seed.audit_area, seed.tier
        )
    return len(prior) + len(seeds)
