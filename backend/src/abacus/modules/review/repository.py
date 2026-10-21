"""Review data access (P-04). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.review.models import SignOff


async def sign_offs_of(
    session: AsyncSession, target_type: str, target_ids: Sequence[UUID]
) -> Sequence[SignOff]:
    """Newest first (LIST_EXEMPT: the caller authorised on the target's engagement)."""
    if not target_ids:
        return []
    return (
        (
            await session.execute(
                select(SignOff)
                .where(SignOff.target_type == target_type, SignOff.target_id.in_(target_ids))
                .order_by(SignOff.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def insert_sign_off(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(SignOff).values(**values))
