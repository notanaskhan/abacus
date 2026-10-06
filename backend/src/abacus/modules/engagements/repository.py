"""Engagements data access: the `engagements` table only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.engagements.models import Engagement
from abacus.modules.identity.api import AuthContext, visible


async def insert_engagement(
    session: AsyncSession,
    *,
    engagement_id: UUID,
    tenant_id: UUID,
    client_id: UUID,
    client_entity_id: UUID,
    name: str,
    fiscal_period_start: date,
    fiscal_period_end: date,
    created_by: UUID,
) -> None:
    await session.execute(
        insert(Engagement).values(
            id=engagement_id,
            tenant_id=tenant_id,
            client_id=client_id,
            client_entity_id=client_entity_id,
            name=name,
            fiscal_period_start=fiscal_period_start,
            fiscal_period_end=fiscal_period_end,
            created_by=created_by,
        )
    )


async def get_engagement(session: AsyncSession, engagement_id: UUID) -> Engagement | None:
    """Row-level security returns None for another firm's engagement, as for a missing one."""
    return (
        await session.execute(select(Engagement).where(Engagement.id == engagement_id))
    ).scalar_one_or_none()


async def list_engagements(session: AsyncSession, ctx: AuthContext) -> Sequence[Engagement]:
    return (
        (
            await session.execute(
                select(Engagement)
                .where(visible(ctx, "engagement.read_metadata", Engagement.id))
                .order_by(Engagement.created_at.desc(), Engagement.id)
            )
        )
        .scalars()
        .all()
    )
