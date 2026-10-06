"""Request item rules (TASK-008 design §3). Authorise before any write."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session, transaction_context
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import Actor, AuthContext, SystemContext, authorise
from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.models import RequestItem
from abacus.modules.requests.repository import (
    get_request_item,
    insert_fulfilment,
    insert_request_item,
    items_fulfilled_by,
    list_request_items,
    mark_received,
    request_list_for,
)


@dataclass(frozen=True)
class RequestItemView:
    id: UUID
    engagement_id: UUID
    description: str
    audit_area: str
    status: str
    created_at: datetime


def _view(item: RequestItem) -> RequestItemView:
    return RequestItemView(
        item.id,
        item.engagement_id,
        item.description,
        item.audit_area,
        item.status,
        item.created_at,
    )


@dataclass(frozen=True)
class NewRequestItem:
    description: str
    audit_area: str


async def add_request_item(
    ctx: AuthContext, engagement_id: UUID, new: NewRequestItem
) -> RequestItemView:
    item_id = uuid4()
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "request_item.create", ref.resource())
        list_id, created = await request_list_for(tx.session, ctx.tenant_id, engagement_id)
        if created:
            tx.record(
                "request_list.created",
                target=Target("request_list", list_id),
                after=Ref(engagement_id=engagement_id),
            )
        item = await insert_request_item(
            tx.session,
            item_id=item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_list_id=list_id,
            description=new.description,
            audit_area=new.audit_area,
            created_by=ctx.user_id,
        )
        tx.record(
            "request_item.created",
            target=Target("request_item", item_id),
            after=Ref(engagement_id=engagement_id),
        )
        tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
        view = _view(item)
    return view


async def request_items_for(ctx: AuthContext, engagement_id: UUID) -> Sequence[RequestItemView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "request_item.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        return [_view(item) for item in await list_request_items(session, ctx, engagement_id)]


class ItemNotFulfillable(Exception):
    """Only open or received items take new evidence by rule."""


@dataclass(frozen=True)
class RequestItemRef:
    id: UUID
    engagement_id: UUID
    status: str


async def item_ref(tx: UnitOfWork, request_item_id: UUID) -> RequestItemRef:
    """The item as this transaction sees it (`NotFound` outside the tenant)."""
    item = await get_request_item(tx.session, request_item_id)
    if item is None:
        raise NotFound("request_item")
    return RequestItemRef(item.id, item.engagement_id, item.status)


@dataclass(frozen=True)
class FulfilmentRef:
    id: UUID | None  # None when this version already fulfilled this item
    received: bool  # the item moved open → received in this call


async def fulfil_by_rule(
    tx: UnitOfWork, ctx: Actor, *, request_item_id: UUID, evidence_version_id: UUID
) -> FulfilmentRef:
    """Link a version to the item it satisfies and move the item `open → received`.

    Authorises `fulfilment.propose` for `ctx` on the item's engagement, inside the caller's unit
    of work (the engagement is share-locked there). The kind follows the actor: the platform's
    links are `rule` (AC-10), a person's are `human`. The evidence must belong to the item's
    engagement (composite key). Only open or received items take new evidence."""
    tenant = await transaction_context(tx.session)
    item = await item_ref(tx, request_item_id)
    ref = await lock_ref(tx, item.engagement_id)
    await authorise(ctx, "fulfilment.propose", ref.resource())
    if item.status not in ("open", "received"):
        raise ItemNotFulfillable(item.status)
    fulfilment_id = await insert_fulfilment(
        tx.session,
        tenant_id=tenant.tenant_id,
        engagement_id=item.engagement_id,
        request_item_id=request_item_id,
        evidence_version_id=evidence_version_id,
        created_by_kind="rule" if isinstance(ctx, SystemContext) else "human",
        created_by_id=tenant.actor_id,
    )
    if fulfilment_id is not None:
        tx.record(
            "fulfilment.created",
            target=Target("fulfilment", fulfilment_id),
            after=Ref(request_item_id=request_item_id, evidence_version_id=evidence_version_id),
        )
    received = await mark_received(tx.session, request_item_id)
    if received:
        tx.record(
            "request_item.received",
            target=Target("request_item", request_item_id),
            after=Ref(evidence_version_id=evidence_version_id),
        )
    return FulfilmentRef(fulfilment_id, received)


@dataclass(frozen=True)
class RequestItemSummary:
    id: UUID
    description: str
    audit_area: str


async def fulfilled_items(
    tenant: TenantContext, evidence_version_id: UUID
) -> list[RequestItemSummary]:
    async with tenant_session(tenant) as session:
        items = await items_fulfilled_by(session, evidence_version_id)
        return [RequestItemSummary(i.id, i.description, i.audit_area) for i in items]
