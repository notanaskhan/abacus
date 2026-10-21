"""Completion data access (SPEC-314). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.assurance.completion_models import (
    Archive,
    CompletionRecord,
    EqrConcurrence,
    Release,
)


async def records_of(session: AsyncSession, engagement_id: UUID) -> Sequence[CompletionRecord]:
    """Newest first (LIST_EXEMPT: the caller authorised on the engagement)."""
    return (
        (
            await session.execute(
                select(CompletionRecord)
                .where(CompletionRecord.engagement_id == engagement_id)
                .order_by(CompletionRecord.created_at.desc(), CompletionRecord.id.desc())
            )
        )
        .scalars()
        .all()
    )


async def newest_concurrence(session: AsyncSession, engagement_id: UUID) -> EqrConcurrence | None:
    return await session.scalar(
        select(EqrConcurrence)
        .where(EqrConcurrence.engagement_id == engagement_id)
        .order_by(EqrConcurrence.created_at.desc())
        .limit(1)
    )


async def release_of(session: AsyncSession, engagement_id: UUID) -> Release | None:
    return await session.scalar(select(Release).where(Release.engagement_id == engagement_id))


async def archive_of(session: AsyncSession, engagement_id: UUID) -> Archive | None:
    return await session.scalar(select(Archive).where(Archive.engagement_id == engagement_id))


async def insert_row(session: AsyncSession, model: type[object], **values: object) -> None:
    await session.execute(insert(model).values(**values))
