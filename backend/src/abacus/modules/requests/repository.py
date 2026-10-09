"""Requests data access: request lists and request items only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.identity.api import AuthContext, visible, visible_items
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
    retrievability_tier: str | None = None,
    dataset: str | None = None,
    tier_source: str | None = None,
    tier_rule: str | None = None,
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
                retrievability_tier=retrievability_tier,
                dataset=dataset,
                tier_source=tier_source,
                tier_rule=tier_rule,
            )
            .returning(RequestItem)
        )
    ).scalar_one()


async def list_request_items(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[tuple[RequestItem, UUID | None]]:
    """Each visible item of the engagement with the evidence version that last fulfilled it."""
    latest = (
        select(Fulfilment.evidence_version_id)
        .where(Fulfilment.request_item_id == RequestItem.id)
        .order_by(Fulfilment.created_at.desc(), Fulfilment.id.desc())
        .limit(1)
        .correlate(RequestItem)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(RequestItem, latest)
        .where(
            RequestItem.engagement_id == engagement_id,
            visible_items(
                ctx,
                "request_item.read",
                RequestItem.engagement_id,
                RequestItem.client_visible,
                RequestItem.client_assignee_user_id,
            ),
        )
        .order_by(RequestItem.created_at, RequestItem.id)
    )
    return [(item, version_id) for item, version_id in rows.all()]


async def set_client_fields(
    session: AsyncSession,
    item_id: UUID,
    *,
    client_visible: bool | None = None,
    client_assignee: UUID | Literal["unchanged"] | None = "unchanged",
) -> None:
    """Change the item's client facts (SPEC-020); the caller holds the item's lock."""
    values: dict[str, object] = {}
    if client_visible is not None:
        values["client_visible"] = client_visible
    if client_assignee != "unchanged":
        values["client_assignee_user_id"] = client_assignee
    if values:
        await session.execute(
            update(RequestItem).where(RequestItem.id == item_id).values(**values)
        )


async def fulfilling_versions(session: AsyncSession, item_id: UUID) -> Sequence[UUID]:
    """Every version that fulfils the item, oldest first, for a caller that authorised on the
    item (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(Fulfilment.evidence_version_id)
                .where(Fulfilment.request_item_id == item_id)
                .order_by(Fulfilment.created_at, Fulfilment.id)
            )
        )
        .scalars()
        .all()
    )


async def get_request_item(
    session: AsyncSession, item_id: UUID, *, lock: bool = False
) -> RequestItem | None:
    """The item; `lock` holds its row until the transaction ends, so a review decision and a new
    fulfilment of the same item never interleave (TASK-019 security review H3)."""
    query = select(RequestItem).where(RequestItem.id == item_id)
    if lock:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def insert_fulfilment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
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
                engagement_id=engagement_id,
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
    """`open` or `needs_revision` → `received`; False if the item was neither (already received or
    further on). A sent-back item takes new evidence (SPEC-004, TASK-019)."""
    result = await session.execute(
        update(RequestItem)
        .where(RequestItem.id == item_id, RequestItem.status.in_(("open", "needs_revision")))
        .values(status="received")
        .returning(RequestItem.id)
    )
    return result.scalar_one_or_none() is not None


async def newest_fulfilment(session: AsyncSession, item_id: UUID) -> UUID | None:
    """The version that last fulfilled the item (newest fulfilment first, then its id)."""
    return (
        await session.execute(
            select(Fulfilment.evidence_version_id)
            .where(Fulfilment.request_item_id == item_id)
            .order_by(Fulfilment.created_at.desc(), Fulfilment.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def list_fulfilled_versions(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[tuple[RequestItem, UUID, datetime, UUID]]:
    """Every (item, version, fulfilled at) of the engagement the actor may review (SPEC-004)."""
    rows = await session.execute(
        select(RequestItem, Fulfilment.evidence_version_id, Fulfilment.created_at, Fulfilment.id)
        .join(Fulfilment, Fulfilment.request_item_id == RequestItem.id)
        .where(
            RequestItem.engagement_id == engagement_id,
            visible(ctx, "review.read", RequestItem.engagement_id),
        )
        .order_by(RequestItem.created_at, RequestItem.id, Fulfilment.created_at, Fulfilment.id)
    )
    return [(item, version_id, at, fid) for item, version_id, at, fid in rows.all()]


async def set_status(
    session: AsyncSession, item_id: UUID, *, allowed_from: tuple[str, ...], to: str
) -> bool:
    """Move the item to `to` if it is in one of `allowed_from`; False otherwise."""
    result = await session.execute(
        update(RequestItem)
        .where(RequestItem.id == item_id, RequestItem.status.in_(allowed_from))
        .values(status=to)
        .returning(RequestItem.id)
    )
    return result.scalar_one_or_none() is not None


async def items_fulfilled_by(
    session: AsyncSession, evidence_version_id: UUID
) -> Sequence[RequestItem]:
    """Items a version fulfils, for a caller that authorised on the version's engagement
    (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(RequestItem)
                .join(Fulfilment, Fulfilment.request_item_id == RequestItem.id)
                .where(Fulfilment.evidence_version_id == evidence_version_id)
                .order_by(RequestItem.created_at, RequestItem.id)
            )
        )
        .scalars()
        .all()
    )


async def item_keys(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[tuple[str, str]]:
    """(audit area, description) of the engagement's items, for de-duplication (SPEC-018 Q3)."""
    rows = await session.execute(
        select(RequestItem.audit_area, RequestItem.description).where(
            RequestItem.engagement_id == engagement_id,
            visible(ctx, "request_item.read", RequestItem.engagement_id),
        )
    )
    return [(area, description) for area, description in rows.all()]


async def set_classification(
    session: AsyncSession,
    item_id: UUID,
    *,
    tier: str | None,
    dataset: str | None,
    source: str | None,
    rule: str | None,
) -> None:
    await session.execute(
        update(RequestItem)
        .where(RequestItem.id == item_id)
        .values(retrievability_tier=tier, dataset=dataset, tier_source=source, tier_rule=rule)
    )
