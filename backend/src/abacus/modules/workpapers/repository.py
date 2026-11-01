"""Working-paper data access (SPEC-308). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.workpapers.models import (
    AttentionFlag,
    Workpaper,
    WorkpaperCell,
    WorkpaperCellCitation,
    WorkpaperSection,
    WorkpaperVersion,
)


async def workpapers_of(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[Workpaper]:
    """The engagement's papers by code, through `visible()`."""
    return (
        (
            await session.execute(
                select(Workpaper)
                .where(
                    Workpaper.engagement_id == engagement_id,
                    visible(ctx, "workpaper.read", Workpaper.engagement_id),
                )
                .order_by(Workpaper.code)
            )
        )
        .scalars()
        .all()
    )


async def get_workpaper(session: AsyncSession, workpaper_id: UUID) -> Workpaper | None:
    return await session.get(Workpaper, workpaper_id)


async def code_taken(session: AsyncSession, engagement_id: UUID, code: str) -> bool:
    found = await session.scalar(
        select(Workpaper.id).where(
            Workpaper.engagement_id == engagement_id, Workpaper.code == code
        )
    )
    return found is not None


async def insert_workpaper(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(Workpaper).values(**values).returning(Workpaper.id))
    ).scalar_one()


async def newest_cells(
    session: AsyncSession, workpaper_ids: Sequence[UUID]
) -> Sequence[WorkpaperCell]:
    """Each cell's newest row (LIST_EXEMPT: the caller authorised on the engagement)."""
    if not workpaper_ids:
        return []
    return (
        (
            await session.execute(
                select(WorkpaperCell)
                .where(WorkpaperCell.workpaper_id.in_(workpaper_ids))
                .distinct(
                    WorkpaperCell.workpaper_id, WorkpaperCell.sheet_key, WorkpaperCell.cell_key
                )
                .order_by(
                    WorkpaperCell.workpaper_id,
                    WorkpaperCell.sheet_key,
                    WorkpaperCell.cell_key,
                    WorkpaperCell.created_at.desc(),
                    WorkpaperCell.id.desc(),
                )
            )
        )
        .scalars()
        .all()
    )


async def insert_cells(session: AsyncSession, rows: list[dict[str, Any]]) -> None:  # Any: values
    if rows:
        await session.execute(insert(WorkpaperCell), rows)


async def cell_setters(session: AsyncSession, workpaper_id: UUID) -> set[UUID]:
    """Everyone who ever set a cell of the paper (P-04-T15: its preparers; LIST_EXEMPT: the
    caller authorised on the engagement)."""
    found = await session.execute(
        select(WorkpaperCell.set_by).where(WorkpaperCell.workpaper_id == workpaper_id).distinct()
    )
    return set(found.scalars().all())


async def citations_of(
    session: AsyncSession, workpaper_ids: Sequence[UUID]
) -> Sequence[WorkpaperCellCitation]:
    """Oldest first (LIST_EXEMPT: the caller authorised on the engagement)."""
    if not workpaper_ids:
        return []
    return (
        (
            await session.execute(
                select(WorkpaperCellCitation)
                .where(WorkpaperCellCitation.workpaper_id.in_(workpaper_ids))
                .order_by(WorkpaperCellCitation.created_at, WorkpaperCellCitation.id)
            )
        )
        .scalars()
        .all()
    )


async def insert_citation(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(WorkpaperCellCitation).values(**values))


async def versions_of(session: AsyncSession, workpaper_id: UUID) -> Sequence[WorkpaperVersion]:
    """Newest first (LIST_EXEMPT: the caller authorised on the engagement)."""
    return (
        (
            await session.execute(
                select(WorkpaperVersion)
                .where(WorkpaperVersion.workpaper_id == workpaper_id)
                .order_by(WorkpaperVersion.version_no.desc())
            )
        )
        .scalars()
        .all()
    )


async def next_version_no(session: AsyncSession, workpaper_id: UUID) -> int:
    top = await session.scalar(
        select(func.max(WorkpaperVersion.version_no)).where(
            WorkpaperVersion.workpaper_id == workpaper_id
        )
    )
    return (top or 0) + 1


async def insert_version(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(WorkpaperVersion).values(**values))


async def engagement_papers(session: AsyncSession, engagement_id: UUID) -> Sequence[Workpaper]:
    """By code (LIST_EXEMPT: for the review matrix and G5, after the caller authorised)."""
    return (
        (
            await session.execute(
                select(Workpaper)
                .where(Workpaper.engagement_id == engagement_id)
                .order_by(Workpaper.code)
            )
        )
        .scalars()
        .all()
    )


# --- A-04-T04: the record projection's reads (LIST_EXEMPT: the caller authorised on the
# engagement first) ------------------------------------------------------------------------------


async def sections_of(session: AsyncSession, workpaper_id: UUID) -> Sequence[WorkpaperSection]:
    """By position (LIST_EXEMPT: one paper's, after the caller authorised on its engagement)."""
    return (
        (
            await session.execute(
                select(WorkpaperSection)
                .where(WorkpaperSection.workpaper_id == workpaper_id)
                .order_by(WorkpaperSection.position, WorkpaperSection.sheet_key)
            )
        )
        .scalars()
        .all()
    )


async def cells_up_to(
    session: AsyncSession, workpaper_id: UUID, version_no: int | None
) -> Sequence[WorkpaperCell]:
    """Each cell's newest row as it stood at `version_no` (rows written before 0581 carry no
    version and belong to every version); None is now (LIST_EXEMPT: one paper's, after the caller
    authorised on its engagement)."""
    query = select(WorkpaperCell).where(WorkpaperCell.workpaper_id == workpaper_id)
    if version_no is not None:
        query = query.where(
            (WorkpaperCell.updated_version_no.is_(None))
            | (WorkpaperCell.updated_version_no <= version_no)
        )
    return (
        (
            await session.execute(
                query.distinct(WorkpaperCell.sheet_key, WorkpaperCell.cell_key).order_by(
                    WorkpaperCell.sheet_key,
                    WorkpaperCell.cell_key,
                    WorkpaperCell.created_at.desc(),
                    WorkpaperCell.id.desc(),
                )
            )
        )
        .scalars()
        .all()
    )


async def flags_of(session: AsyncSession, workpaper_id: UUID) -> Sequence[AttentionFlag]:
    """Oldest first (LIST_EXEMPT: one paper's, after the caller authorised on its engagement)."""
    return (
        (
            await session.execute(
                select(AttentionFlag)
                .where(AttentionFlag.workpaper_id == workpaper_id)
                .order_by(AttentionFlag.created_at, AttentionFlag.id)
            )
        )
        .scalars()
        .all()
    )


async def core_papers(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[Workpaper]:
    """The engagement's A-04 papers (those with a kind), by code, through `visible()`."""
    return (
        (
            await session.execute(
                select(Workpaper)
                .where(
                    Workpaper.engagement_id == engagement_id,
                    Workpaper.kind.is_not(None),
                    visible(ctx, "workpaper.read", Workpaper.engagement_id),
                )
                .order_by(Workpaper.code)
            )
        )
        .scalars()
        .all()
    )


async def sections_for(
    session: AsyncSession, workpaper_ids: Sequence[UUID]
) -> Sequence[WorkpaperSection]:
    """By position (LIST_EXEMPT: the papers `core_papers` listed through `visible()`)."""
    if not workpaper_ids:
        return []
    return (
        (
            await session.execute(
                select(WorkpaperSection)
                .where(WorkpaperSection.workpaper_id.in_(workpaper_ids))
                .order_by(WorkpaperSection.position, WorkpaperSection.sheet_key)
            )
        )
        .scalars()
        .all()
    )


async def version_at(
    session: AsyncSession, workpaper_id: UUID, version_no: int
) -> WorkpaperVersion | None:
    return await session.scalar(
        select(WorkpaperVersion).where(
            WorkpaperVersion.workpaper_id == workpaper_id,
            WorkpaperVersion.version_no == version_no,
        )
    )


async def papers_of_work_item(session: AsyncSession, work_item_id: UUID) -> Sequence[Workpaper]:
    """A-05-T09: a work item's designed papers (those with a kind), by code, for an owner's
    rail provider or export section that already authorised on the engagement."""
    return (
        (
            await session.execute(
                select(Workpaper)
                .where(Workpaper.work_item_id == work_item_id, Workpaper.kind.is_not(None))
                .order_by(Workpaper.code)
            )
        )
        .scalars()
        .all()
    )
