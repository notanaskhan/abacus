"""Account mapping data access (SPEC-316; TASK-345). Only ledger tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.ledger.models import (
    FsLine,
    FsLineRangeRule,
    Grouping,
    GroupingSet,
    GroupingSetVersion,
    MappingSet,
    MappingSetEdit,
)


async def grouping_sets(session: AsyncSession) -> Sequence[GroupingSet]:
    """The firm's grouping sets by key (LIST_EXEMPT: firm content, after a firm-level check)."""
    return (await session.execute(select(GroupingSet).order_by(GroupingSet.key))).scalars().all()


async def set_by_key(session: AsyncSession, key: str) -> GroupingSet | None:
    return await session.scalar(select(GroupingSet).where(GroupingSet.key == key))


async def versions_of_sets(
    session: AsyncSession, set_ids: Sequence[UUID]
) -> Sequence[GroupingSetVersion]:
    """Newest first (LIST_EXEMPT: firm content)."""
    if not set_ids:
        return []
    return (
        (
            await session.execute(
                select(GroupingSetVersion)
                .where(GroupingSetVersion.grouping_set_id.in_(set_ids))
                .order_by(GroupingSetVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )


async def get_version(session: AsyncSession, version_id: UUID) -> GroupingSetVersion | None:
    return await session.get(GroupingSetVersion, version_id)


async def next_version_no(session: AsyncSession, set_id: UUID) -> int:
    top = await session.scalar(
        select(func.max(GroupingSetVersion.version)).where(
            GroupingSetVersion.grouping_set_id == set_id
        )
    )
    return (top or 0) + 1


async def insert_set(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(GroupingSet).values(**values).returning(GroupingSet.id))
    ).scalar_one()


async def insert_version(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(
            insert(GroupingSetVersion).values(**values).returning(GroupingSetVersion.id)
        )
    ).scalar_one()


async def insert_grouping(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(Grouping).values(**values).returning(Grouping.id))
    ).scalar_one()


async def insert_fs_line(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(FsLine).values(**values).returning(FsLine.id))
    ).scalar_one()


async def insert_rules(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(FsLineRangeRule), rows)


async def insert_mapping_set(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(MappingSet).values(**values).returning(MappingSet.id))
    ).scalar_one()


async def publish(session: AsyncSession, version_id: UUID, **values: object) -> None:
    """Published at business time (`abacus_now()`, F-04-T11)."""
    await session.execute(
        update(GroupingSetVersion)
        .where(GroupingSetVersion.id == version_id)
        .values(**values, published_at=func.abacus_now())
    )


async def catalogue_rows(
    session: AsyncSession, version_id: UUID
) -> tuple[Sequence[Grouping], Sequence[FsLine], Sequence[FsLineRangeRule]]:
    """A version's groupings, FS lines and ranges in order (LIST_EXEMPT: firm content)."""
    groupings = (
        (
            await session.execute(
                select(Grouping)
                .where(Grouping.version_id == version_id)
                .order_by(Grouping.position)
            )
        )
        .scalars()
        .all()
    )
    lines = (
        (
            await session.execute(
                select(FsLine).where(FsLine.version_id == version_id).order_by(FsLine.position)
            )
        )
        .scalars()
        .all()
    )
    rules = (
        (
            await session.execute(
                select(FsLineRangeRule)
                .where(FsLineRangeRule.version_id == version_id)
                .order_by(FsLineRangeRule.position)
            )
        )
        .scalars()
        .all()
    )
    return groupings, lines, rules


async def mapping_set_for(session: AsyncSession, tb_id: UUID) -> MappingSet | None:
    return await session.scalar(select(MappingSet).where(MappingSet.trial_balance_id == tb_id))


async def get_mapping_set(session: AsyncSession, mapping_set_id: UUID) -> MappingSet | None:
    return await session.get(MappingSet, mapping_set_id)


async def mapping_editors(session: AsyncSession, mapping_set_id: UUID) -> set[UUID]:
    """Everyone who ever edited the mapping set (P-04-T15: its preparers; LIST_EXEMPT: the
    caller authorised on the engagement)."""
    found = await session.execute(
        select(MappingSetEdit.edited_by)
        .where(MappingSetEdit.mapping_set_id == mapping_set_id)
        .distinct()
    )
    return set(found.scalars().all())


async def newest_edits(session: AsyncSession, mapping_set_id: UUID) -> Sequence[MappingSetEdit]:
    """Each account's newest edit (LIST_EXEMPT: the caller authorised on the engagement)."""
    return (
        (
            await session.execute(
                select(MappingSetEdit)
                .where(MappingSetEdit.mapping_set_id == mapping_set_id)
                .distinct(MappingSetEdit.account_code)
                .order_by(
                    MappingSetEdit.account_code,
                    MappingSetEdit.created_at.desc(),
                    MappingSetEdit.id.desc(),
                )
            )
        )
        .scalars()
        .all()
    )


async def insert_edits(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(MappingSetEdit), rows)


async def discard_drafts(session: AsyncSession, set_id: UUID) -> int:
    """A-03-T06: a re-import discards the set's earlier draft (one live draft per set, 0521)."""
    discarded = await session.scalars(
        update(GroupingSetVersion)
        .where(GroupingSetVersion.grouping_set_id == set_id, GroupingSetVersion.status == "draft")
        .values(status="discarded")
        .returning(GroupingSetVersion.id)
    )
    return len(discarded.all())


async def version_by_number(session: AsyncSession, set_id: UUID, version_no: int) -> UUID | None:
    return await session.scalar(
        select(GroupingSetVersion.id).where(
            GroupingSetVersion.grouping_set_id == set_id, GroupingSetVersion.version == version_no
        )
    )


async def recent_fs_lines(
    session: AsyncSession, version_id: UUID, user_id: UUID, limit: int
) -> list[UUID]:
    """The person's own newest edits onto this version's FS lines, distinct, newest first
    (LIST_EXEMPT: the person's own choices of firm content; bounded by `limit`)."""
    rows = (
        await session.execute(
            select(MappingSetEdit.fs_line_id, func.max(MappingSetEdit.created_at).label("at"))
            .join(FsLine, FsLine.id == MappingSetEdit.fs_line_id)
            .where(MappingSetEdit.edited_by == user_id, FsLine.version_id == version_id)
            .group_by(MappingSetEdit.fs_line_id)
            .order_by(func.max(MappingSetEdit.created_at).desc())
            .limit(limit)
        )
    ).all()
    return [line for line, _ in rows if line is not None]


async def edits_of(session: AsyncSession, mapping_set_id: UUID) -> Sequence[MappingSetEdit]:
    """Every edit in the set, each account's oldest first (A-03-T08: "was …" and `seen_version`;
    LIST_EXEMPT: the caller authorised on the engagement)."""
    return (
        (
            await session.execute(
                select(MappingSetEdit)
                .where(MappingSetEdit.mapping_set_id == mapping_set_id)
                .order_by(
                    MappingSetEdit.account_code, MappingSetEdit.created_at, MappingSetEdit.id
                )
            )
        )
        .scalars()
        .all()
    )
