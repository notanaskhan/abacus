"""Requests data access: request lists and request items only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.requests.models import Fulfilment, RequestItem, RequestList


async def request_list_for(
    session: AsyncSession, tenant_id: UUID, engagement_id: UUID
) -> tuple[UUID, bool]:
    """The engagement's request list and whether this call created it (TASK-008 Q5). Concurrent
    first items both end up with the same list (one per engagement, enforced by the database)."""
    existing = (
        await session.execute(
            select(RequestList.id).where(RequestList.engagement_id == engagement_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    created = (
        await session.execute(
            pg_insert(RequestList)
            .values(id=uuid4(), tenant_id=tenant_id, engagement_id=engagement_id)
            .on_conflict_do_nothing(index_elements=["tenant_id", "engagement_id"])
            .returning(RequestList.id)
        )
    ).scalar_one_or_none()
    if created is not None:
        return created, True
    winner = (
        await session.execute(
            select(RequestList.id).where(RequestList.engagement_id == engagement_id)
        )
    ).scalar_one()
    return winner, False


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
) -> RequestItem:
    return (
        await session.execute(
            insert(RequestItem)
            .values(
                id=item_id,
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                request_list_id=request_list_id,
                description=description,
                audit_area=audit_area,
                created_by=created_by,
            )
            .returning(RequestItem)
        )
    ).scalar_one()


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


async def get_request_item(session: AsyncSession, item_id: UUID) -> RequestItem | None:
    return (
        await session.execute(select(RequestItem).where(RequestItem.id == item_id))
    ).scalar_one_or_none()


async def insert_fulfilment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    request_item_id: UUID,
    evidence_version_id: UUID,
    created_by_kind: str,
    created_by_id: str,
) -> UUID | None:
    """The new fulfilment's ID, or None if this version already fulfils this item."""
    return (
        await session.execute(
            pg_insert(Fulfilment)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                request_item_id=request_item_id,
                evidence_version_id=evidence_version_id,
                created_by_kind=created_by_kind,
                created_by_id=created_by_id,
            )
            .on_conflict_do_nothing(constraint="fulfilments_once")
            .returning(Fulfilment.id)
        )
    ).scalar_one_or_none()


async def mark_received(session: AsyncSession, item_id: UUID) -> bool:
    """`open → received`; False if the item was not open (already received or further on)."""
    result = await session.execute(
        update(RequestItem)
        .where(RequestItem.id == item_id, RequestItem.status == "open")
        .values(status="received")
        .returning(RequestItem.id)
    )
    return result.scalar_one_or_none() is not None
