"""Review data access (P-04). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import ColumnElement, Select, Text, func, insert, or_, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.dialects.postgresql import ARRAY, distinct_on
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from abacus.modules.identity.api import Actor, visible
from abacus.modules.review.models import (
    Checkpoint,
    CheckpointDecision,
    CheckpointDiff,
    Decision,
    DecisionAnalysisRequest,
    DecisionCard,
    DecisionCardVersion,
    FieldValueVersion,
    ReviewableNote,
    ReviewableNoteEvent,
    SignOff,
)


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
                # The same tie-break as `stale_sign_offs`: a frozen clock stamps many rows alike.
                .order_by(SignOff.created_at.desc(), SignOff.id.desc())
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


async def lock_target(session: AsyncSession, target_type: str, target_id: UUID) -> None:
    """P-04-T18 (security review M1): serialise sign-offs on one target until commit. Advisory,
    so it needs no privilege on the owner's tables."""
    key = f"sign_off:{target_type}:{target_id}"
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))


async def insert_sign_off(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(SignOff).values(**values).returning(SignOff.id))
    ).scalar_one()


async def field_versions_of(
    session: AsyncSession, target_type: str, target_id: UUID, field_key: str
) -> Sequence[FieldValueVersion]:
    """P-04-T35: one field's versions, newest first (LIST_EXEMPT: one field, for a caller
    authorised on its target's engagement)."""
    return (
        (
            await session.execute(
                select(FieldValueVersion)
                .where(
                    FieldValueVersion.target_type == target_type,
                    FieldValueVersion.target_id == target_id,
                    FieldValueVersion.field_key == field_key,
                )
                .order_by(FieldValueVersion.seq.desc())
            )
        )
        .scalars()
        .all()
    )


async def field_ticks_of(session: AsyncSession, field_id: UUID) -> Sequence[SignOff]:
    """P-04-T35: a field's ticks (`field_tick` sign-offs on its `field` target), newest first
    (LIST_EXEMPT: one field, for a caller authorised on its target's engagement)."""
    return (
        (
            await session.execute(
                select(SignOff)
                .where(
                    SignOff.target_type == "field",
                    SignOff.target_id == field_id,
                    SignOff.kind == "field_tick",
                )
                .order_by(SignOff.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


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


# --- P-04-T21: the C3 notes list ---------------------------------------------------------------


def note_list_query(
    ctx: Actor,
    *,
    engagement_id: UUID | None,
    target_type: str | None,
    target_id: UUID | None,
) -> tuple[
    Select[ReviewableNote],
    Select[ReviewableNote],
    ColumnElement[object],
    ColumnElement[object],
]:
    """Notes on engagements where the caller may read them (`visible()`, walls excluded), with
    the filters: (the base for per-status counts, the statement, its sort, its id column)."""
    engagement = ReviewableNote.engagement_id.expression
    base = select(ReviewableNote).where(visible(ctx, "review_note.read", engagement))
    if engagement_id is not None:
        base = base.where(ReviewableNote.engagement_id == engagement_id)
    if target_type is not None:
        base = base.where(ReviewableNote.target_type == target_type)
    if target_id is not None:
        base = base.where(ReviewableNote.target_id == target_id)
    return (
        base,
        base,
        cast(ColumnElement[object], ReviewableNote.created_at.expression),
        cast(ColumnElement[object], ReviewableNote.id.expression),
    )


# --- P-04-T23: decision cards ------------------------------------------------------------------


def card_list_query(
    ctx: Actor, *, engagement_id: UUID | None
) -> tuple[Select[DecisionCard], ColumnElement[object], ColumnElement[object]]:
    """Cards on engagements where the caller may read them (`visible()`, walls excluded)."""
    engagement = DecisionCard.engagement_id.expression
    base = select(DecisionCard).where(visible(ctx, "decision.read", engagement))
    if engagement_id is not None:
        base = base.where(DecisionCard.engagement_id == engagement_id)
    return (
        base,
        cast(ColumnElement[object], DecisionCard.created_at.expression),
        cast(ColumnElement[object], DecisionCard.id.expression),
    )


async def get_card(session: AsyncSession, card_id: UUID) -> DecisionCard | None:
    return await session.get(DecisionCard, card_id)


async def lock_card(session: AsyncSession, card_id: UUID) -> DecisionCard | None:
    """The card, locked for its status change (two decides can't race)."""
    return (
        await session.execute(
            select(DecisionCard).where(DecisionCard.id == card_id).with_for_update()
        )
    ).scalar_one_or_none()


async def cards_by_id(session: AsyncSession, card_ids: Sequence[UUID]) -> Sequence[DecisionCard]:
    """LIST_EXEMPT: a card's own chain, after authorising on its engagement."""
    if not card_ids:
        return []
    return (
        (await session.execute(select(DecisionCard).where(DecisionCard.id.in_(card_ids))))
        .scalars()
        .all()
    )


async def successors_of(session: AsyncSession, card_ids: Sequence[UUID]) -> Sequence[DecisionCard]:
    """LIST_EXEMPT: the cards that supersede these (callers authorised on their engagement)."""
    if not card_ids:
        return []
    return (
        (
            await session.execute(
                select(DecisionCard).where(DecisionCard.supersedes_id.in_(card_ids))
            )
        )
        .scalars()
        .all()
    )


async def set_card_status(session: AsyncSession, card_id: UUID, status: str) -> None:
    await session.execute(
        update(DecisionCard).where(DecisionCard.id == card_id).values(status=status)
    )


async def insert_card(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(DecisionCard).values(**values).returning(DecisionCard.id))
    ).scalar_one()


async def versions_of(
    session: AsyncSession, card_ids: Sequence[UUID]
) -> Sequence[DecisionCardVersion]:
    """LIST_EXEMPT: the history of cards read after authorising on their engagement."""
    if not card_ids:
        return []
    return (
        (
            await session.execute(
                select(DecisionCardVersion)
                .where(DecisionCardVersion.card_id.in_(card_ids))
                .order_by(DecisionCardVersion.version_no, DecisionCardVersion.created_at)
            )
        )
        .scalars()
        .all()
    )


async def current_version(session: AsyncSession, card_id: UUID) -> int:
    found = (
        await session.execute(
            select(func.max(DecisionCardVersion.version_no)).where(
                DecisionCardVersion.card_id == card_id
            )
        )
    ).scalar_one_or_none()
    return int(found or 0)


async def insert_version(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(DecisionCardVersion).values(**values))


async def decision_of(session: AsyncSession, card_id: UUID) -> Decision | None:
    return (
        await session.execute(select(Decision).where(Decision.card_id == card_id))
    ).scalar_one_or_none()


async def insert_decision(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(Decision).values(**values))


async def insert_analysis_request(session: AsyncSession, **values: object) -> datetime:
    return (
        await session.execute(
            insert(DecisionAnalysisRequest)
            .values(**values)
            .returning(DecisionAnalysisRequest.created_at)
        )
    ).scalar_one()


# --- Checkpoints (P-04-T32; SHL-16) -----------------------------------------------------------


async def checkpoints_of(
    session: AsyncSession, target_type: str, target_id: UUID
) -> Sequence[Checkpoint]:
    """One target's checkpoints, oldest first (LIST_EXEMPT: the caller authorised on the
    target's engagement; one target, bounded like a sign-off ladder)."""
    return (
        (
            await session.execute(
                select(Checkpoint)
                .where(Checkpoint.target_type == target_type, Checkpoint.target_id == target_id)
                .order_by(Checkpoint.seq)
            )
        )
        .scalars()
        .all()
    )


async def get_checkpoint(session: AsyncSession, checkpoint_id: UUID) -> Checkpoint | None:
    return await session.get(Checkpoint, checkpoint_id)


async def lock_checkpoint(session: AsyncSession, checkpoint_id: UUID) -> Checkpoint | None:
    """The checkpoint, locked for its status change (two approvals can't race)."""
    return (
        await session.execute(
            select(Checkpoint).where(Checkpoint.id == checkpoint_id).with_for_update()
        )
    ).scalar_one_or_none()


async def lock_proposed_for(
    session: AsyncSession, proposal_id: UUID, checkpoint_id: UUID | None
) -> Sequence[Checkpoint]:
    """The proposed checkpoints a proposal decides: those naming it, or the one it names; locked
    (LIST_EXEMPT: one proposal's, read inside its decision's unit of work)."""
    match = Checkpoint.proposal_id == proposal_id
    if checkpoint_id is not None:
        match = or_(match, Checkpoint.id == checkpoint_id)
    return (
        (
            await session.execute(
                select(Checkpoint)
                .where(match, Checkpoint.status == "proposed")
                .order_by(Checkpoint.seq)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )


async def next_checkpoint_seq(session: AsyncSession, target_type: str, target_id: UUID) -> int:
    """One more than the target's last checkpoint (the caller holds `lock_target`)."""
    found = (
        await session.execute(
            select(func.max(Checkpoint.seq)).where(
                Checkpoint.target_type == target_type, Checkpoint.target_id == target_id
            )
        )
    ).scalar_one_or_none()
    return int(found or 0) + 1


async def insert_checkpoint(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(Checkpoint).values(**values).returning(Checkpoint.id))
    ).scalar_one()


async def set_checkpoint(session: AsyncSession, checkpoint_id: UUID, **values: object) -> None:
    """Only `name`, `starred` and `status` (the column grant refuses anything else)."""
    await session.execute(
        update(Checkpoint).where(Checkpoint.id == checkpoint_id).values(**values)
    )


async def insert_checkpoint_diffs(
    session: AsyncSession, rows: Sequence[Mapping[str, object]]
) -> None:
    if rows:
        await session.execute(insert(CheckpointDiff), list(rows))


async def checkpoint_diffs_of(
    session: AsyncSession, checkpoint_ids: Sequence[UUID]
) -> Sequence[CheckpointDiff]:
    """LIST_EXEMPT: the diffs of checkpoints read after authorising on their engagement."""
    if not checkpoint_ids:
        return []
    return (
        (
            await session.execute(
                select(CheckpointDiff)
                .where(CheckpointDiff.checkpoint_id.in_(checkpoint_ids))
                .order_by(CheckpointDiff.created_at, CheckpointDiff.field_key)
            )
        )
        .scalars()
        .all()
    )


async def insert_checkpoint_decision(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(
            insert(CheckpointDecision).values(**values).returning(CheckpointDecision.id)
        )
    ).scalar_one()


async def checkpoint_decisions_of(
    session: AsyncSession, checkpoint_ids: Sequence[UUID]
) -> Sequence[CheckpointDecision]:
    """LIST_EXEMPT: the decisions of checkpoints read after authorising on their engagement."""
    if not checkpoint_ids:
        return []
    return (
        (
            await session.execute(
                select(CheckpointDecision)
                .where(CheckpointDecision.checkpoint_id.in_(checkpoint_ids))
                .order_by(CheckpointDecision.created_at, CheckpointDecision.id)
            )
        )
        .scalars()
        .all()
    )
