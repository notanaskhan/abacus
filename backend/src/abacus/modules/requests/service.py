"""Request item rules (TASK-008 design §3). Authorise before any write."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.models import RequestItem
from abacus.modules.requests.repository import (
    get_request_item,
    insert_request_item,
    list_request_items,
    request_list_for,
)


@dataclass(frozen=True)
class NewRequestItem:
    description: str
    audit_area: str


async def add_request_item(
    ctx: AuthContext, engagement_id: UUID, new: NewRequestItem
) -> RequestItem:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "request_item.create", ref.resource())
    item_id = uuid4()
    async with uow(ctx.tenant) as tx:
        list_id = await request_list_for(tx.session, ctx.tenant_id, engagement_id)
        await insert_request_item(
            tx.session,
            item_id=item_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_list_id=list_id,
            description=new.description,
            audit_area=new.audit_area,
            created_by=ctx.user_id,
        )
        tx.record("request_item.created", target=Target("request_item", item_id))
        tx.emit(RequestItemCreated(request_item_id=item_id, engagement_id=engagement_id))
    async with tenant_session(ctx.tenant) as session:
        item = await get_request_item(session, item_id)
    if item is None:  # committed above; only a concurrent purge could remove it
        raise NotFound("request_item")
    return item


async def request_items_for(ctx: AuthContext, engagement_id: UUID) -> Sequence[RequestItem]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "request_item.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        return await list_request_items(session, ctx, engagement_id)
