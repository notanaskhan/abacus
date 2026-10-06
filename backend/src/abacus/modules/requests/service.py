"""Request item rules (TASK-008 design §3). Authorise before any write."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from abacus.kernel.db import tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.models import RequestItem
from abacus.modules.requests.repository import (
    insert_request_item,
    list_request_items,
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
