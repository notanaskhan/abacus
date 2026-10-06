"""Requests data access: request lists and request items only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.requests.models import RequestItem, RequestList


async def request_list_for(session: AsyncSession, tenant_id: UUID, engagement_id: UUID) -> UUID:
    """The engagement's request list, created on first use (TASK-008 Q5). Concurrent first
    items both end up with the same list (one list per engagement, enforced by the database)."""
    await session.execute(
        pg_insert(RequestList)
        .values(id=uuid4(), tenant_id=tenant_id, engagement_id=engagement_id)
        .on_conflict_do_nothing(index_elements=["tenant_id", "engagement_id"])
    )
    return (
        await session.execute(
            select(RequestList.id).where(RequestList.engagement_id == engagement_id)
        )
    ).scalar_one()


async def insert_request_item(
    session: AsyncSession,
    *,
    item_id: UUID,
    tenant_id: UUID,
    engagement_id: UUID,
    request_list_id: UUID,
    description: str,
    audit_area: str,
    created_by: UUID,
) -> None:
    await session.execute(
        insert(RequestItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            request_list_id=request_list_id,
            description=description,
            audit_area=audit_area,
            created_by=created_by,
        )
    )


async def get_request_item(session: AsyncSession, item_id: UUID) -> RequestItem | None:
    return (
        await session.execute(select(RequestItem).where(RequestItem.id == item_id))
    ).scalar_one_or_none()


async def list_request_items(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[RequestItem]:
    return (
        (
            await session.execute(
                select(RequestItem)
                .where(
                    RequestItem.engagement_id == engagement_id,
                    visible(ctx, "request_item.read", RequestItem.engagement_id),
                )
                .order_by(RequestItem.created_at, RequestItem.id)
            )
        )
        .scalars()
        .all()
    )
