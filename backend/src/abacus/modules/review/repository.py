"""Review data access (P-04). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import Text, func, insert, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import ARRAY, distinct_on
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from abacus.modules.review.models import ReviewableNote, ReviewableNoteEvent, SignOff


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


async def stale_sign_offs(
    session: AsyncSession, target_type: str, current: Mapping[UUID, str]
) -> Sequence[SignOff]:
    """P-04-T14: the newest sign-off of each target and level whose recorded hash differs from
    the target's current one, computed in one query (no stale column exists: staleness is
    `content_hash <> target hash`). LIST_EXEMPT: the caller authorised on the engagement."""
    if not current:
        return []
    ids = list(current)
    newest = (
        select(SignOff)
        .where(SignOff.target_type == target_type, SignOff.target_id.in_(ids))
        .ext(distinct_on(SignOff.target_id, SignOff.level))
        .order_by(SignOff.target_id, SignOff.level, SignOff.created_at.desc(), SignOff.id.desc())
        .subquery()
    )
    signed = aliased(SignOff, newest)
    now = (
        func.unnest(
            sql_cast(ids, ARRAY(PG_UUID(as_uuid=True))),
            sql_cast([current[i] for i in ids], ARRAY(Text)),
        )
        .table_valued("target_id", "content_hash")
        .render_derived(name="current_hash")
    )
    query = (
        select(signed)
        .join(now, now.c.target_id == signed.target_id)
        .where(signed.content_hash != now.c.content_hash)
        .order_by(signed.target_id, signed.level)
    )
    return (await session.execute(query)).scalars().all()


async def insert_sign_off(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(SignOff).values(**values))


async def notes_of(
    session: AsyncSession,
    engagement_id: UUID,
    target_type: str | None = None,
    target_id: UUID | None = None,
) -> Sequence[ReviewableNote]:
    """Oldest first (LIST_EXEMPT: the caller authorised on the engagement)."""
    query = select(ReviewableNote).where(ReviewableNote.engagement_id == engagement_id)
    if target_type is not None:
        query = query.where(ReviewableNote.target_type == target_type)
    if target_id is not None:
        query = query.where(ReviewableNote.target_id == target_id)
    return (
        (await session.execute(query.order_by(ReviewableNote.created_at, ReviewableNote.id)))
        .scalars()
        .all()
    )


async def note_events_of(
    session: AsyncSession, note_ids: Sequence[UUID]
) -> Sequence[ReviewableNoteEvent]:
    """Oldest first (LIST_EXEMPT: notes read after authorising on their engagement)."""
    if not note_ids:
        return []
    return (
        (
            await session.execute(
                select(ReviewableNoteEvent)
                .where(ReviewableNoteEvent.note_id.in_(note_ids))
                .order_by(ReviewableNoteEvent.created_at, ReviewableNoteEvent.id)
            )
        )
        .scalars()
        .all()
    )


async def get_note(session: AsyncSession, note_id: UUID) -> ReviewableNote | None:
    return await session.get(ReviewableNote, note_id)


async def lock_note(session: AsyncSession, note_id: UUID) -> ReviewableNote | None:
    """The note, locked for its status change (so two answers can't race)."""
    return (
        await session.execute(
            select(ReviewableNote).where(ReviewableNote.id == note_id).with_for_update()
        )
    ).scalar_one_or_none()


async def set_note_status(session: AsyncSession, note_id: UUID, status: str) -> None:
    await session.execute(
        update(ReviewableNote).where(ReviewableNote.id == note_id).values(status=status)
    )


async def insert_note(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(ReviewableNote).values(**values).returning(ReviewableNote.id))
    ).scalar_one()


async def insert_note_event(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ReviewableNoteEvent).values(**values))


async def notes_of_target(session: AsyncSession, target_id: UUID) -> Sequence[ReviewableNote]:
    """LIST_EXEMPT: inside the owner's unit of work, after it authorised the sign-off."""
    return (
        (
            await session.execute(
                select(ReviewableNote).where(ReviewableNote.target_id == target_id)
            )
        )
        .scalars()
        .all()
    )
