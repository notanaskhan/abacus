"""Tie-out check data access (SPEC-310). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.workpapers.tie_models import TieOutCheck, TieOutCheckVersion


async def checks_of(session: AsyncSession, target_id: UUID) -> Sequence[TieOutCheck]:
    """Oldest first (LIST_EXEMPT: the caller authorised on the target's engagement)."""
    return (
        (
            await session.execute(
                select(TieOutCheck)
                .where(TieOutCheck.target_id == target_id)
                .order_by(TieOutCheck.created_at, TieOutCheck.id)
            )
        )
        .scalars()
        .all()
    )


async def current_versions(
    session: AsyncSession, checks: Sequence[TieOutCheck]
) -> dict[UUID, TieOutCheckVersion]:
    if not checks:
        return {}
    wanted = {(c.id, c.current_version_no) for c in checks}
    rows = (
        (
            await session.execute(
                select(TieOutCheckVersion).where(
                    TieOutCheckVersion.check_id.in_([c.id for c in checks])
                )
            )
        )
        .scalars()
        .all()
    )
    return {r.check_id: r for r in rows if (r.check_id, r.version_no) in wanted}


async def lock_check(session: AsyncSession, check_id: UUID) -> TieOutCheck | None:
    return (
        await session.execute(
            select(TieOutCheck).where(TieOutCheck.id == check_id).with_for_update()
        )
    ).scalar_one_or_none()


async def key_taken(session: AsyncSession, target_id: UUID, key: str) -> bool:
    found = await session.scalar(
        select(TieOutCheck.id).where(TieOutCheck.target_id == target_id, TieOutCheck.key == key)
    )
    return found is not None


async def insert_check(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(TieOutCheck).values(**values).returning(TieOutCheck.id))
    ).scalar_one()


async def insert_check_version(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(TieOutCheckVersion).values(**values))


async def set_check_version(session: AsyncSession, check_id: UUID, version_no: int) -> None:
    await session.execute(
        update(TieOutCheck).where(TieOutCheck.id == check_id).values(current_version_no=version_no)
    )


async def set_issue_link(
    session: AsyncSession, check_id: UUID, issue_id: UUID, by: UUID, at: datetime
) -> None:
    """A-02-T17: the three issue-link columns at once (0193: all or none)."""
    await session.execute(
        update(TieOutCheck)
        .where(TieOutCheck.id == check_id)
        .values(issue_id=issue_id, issue_linked_by=by, issue_linked_at=at)
    )


async def checks_of_many(
    session: AsyncSession, target_ids: Sequence[UUID]
) -> Sequence[TieOutCheck]:
    """Every check on these trial balances (LIST_EXEMPT: the review digest's internal read for
    targets the caller already resolved on an authorised engagement)."""
    if not target_ids:
        return []
    return (
        (
            await session.execute(
                select(TieOutCheck)
                .where(TieOutCheck.target_id.in_(list(target_ids)))
                .order_by(TieOutCheck.target_id, TieOutCheck.key)
            )
        )
        .scalars()
        .all()
    )
