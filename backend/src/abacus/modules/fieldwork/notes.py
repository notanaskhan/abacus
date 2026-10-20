"""Review notes (SPEC-041; TASK-103).

A reviewer raises a note on a tested row or on the workpaper; the preparer responds; the reviewer
who raised it clears it or replies (which reopens it). Notes and their events are appended, never
edited (ADR-004): a note's state is its newest event's. A note that isn't cleared blocks the
reviewer's sign-off of its row, and of the workpaper (`open_note_targets`); comments never block.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.fieldwork.models import ReviewNote, ReviewNoteEvent
from abacus.modules.fieldwork.repository import (
    all_items,
    get_note,
    get_procedure,
    insert_note,
    insert_note_event,
    newest_selection,
    note_events_of,
    notes_of,
)
from abacus.modules.identity.api import AuthContext, authorise, engagement_team

STATES: Final = ("open", "responded", "cleared")


class NoteInvalid(DomainInvalid):
    code = "note_invalid"


class NoteCleared(DomainConflict):
    """AC-3: a cleared note is closed."""

    code = "note_cleared"


class NotesOpen(DomainConflict):
    """AC-4, AC-5: clear the review notes before signing as reviewer."""

    code = "notes_open"


class NotRaiser(DomainConflict):
    """AC-3: only the person who raised a note clears it."""

    code = "not_note_raiser"


@dataclass(frozen=True)
class NoteEntry:
    kind: str  # raised | responded | reopened | cleared
    body: str | None
    by: UUID
    name: str
    at: datetime


@dataclass(frozen=True)
class NoteView:
    id: UUID
    item_id: UUID | None
    state: str
    raised_by: UUID
    raised_by_name: str
    raised_at: datetime
    thread: list[NoteEntry]


def state_of(events: Sequence[ReviewNoteEvent]) -> str:
    """AC-6: none is Open; then the newest event decides."""
    if not events:
        return "open"
    last = events[-1].kind
    return "cleared" if last == "cleared" else "responded" if last == "responded" else "open"


async def _events_by_note(
    session: AsyncSession, notes: Sequence[ReviewNote]
) -> dict[UUID, list[ReviewNoteEvent]]:
    found: dict[UUID, list[ReviewNoteEvent]] = {n.id: [] for n in notes}
    for e in await note_events_of(session, [n.id for n in notes]):
        found[e.review_note_id].append(e)
    return found


async def open_note_targets(session: AsyncSession, procedure_id: UUID) -> set[UUID | None]:
    """The rows (and `None` for the workpaper) with a note that isn't cleared."""
    notes = await notes_of(session, procedure_id)
    events = await _events_by_note(session, notes)
    return {n.selected_item_id for n in notes if state_of(events[n.id]) != "cleared"}


async def note_states(session: AsyncSession, procedure_id: UUID) -> list[tuple[UUID, str]]:
    """Each note's raiser and state (for "waiting on you")."""
    notes = await notes_of(session, procedure_id)
    events = await _events_by_note(session, notes)
    return [(n.raised_by, state_of(events[n.id])) for n in notes]


async def _procedure(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> None:
    async with tenant_session(ctx.tenant) as session:
        found = await get_procedure(session, procedure_id)
    if found is None or found.engagement_id != engagement_id:
        raise NotFound("procedure")


def _text(body: str) -> str:
    body = body.strip()
    if not 1 <= len(body) <= 2000:
        raise NoteInvalid("body")
    return body


async def raise_note(
    ctx: AuthContext,
    engagement_id: UUID,
    procedure_id: UUID,
    item_id: UUID | None,
    body: str,
) -> UUID:
    """AC-1: on a row of the current selection, or on the workpaper (`item_id` None)."""
    text = _text(body)
    await _procedure(ctx, engagement_id, procedure_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "review_note.raise", ref.resource())
        if item_id is not None:
            selection = await newest_selection(tx.session, procedure_id)
            items: set[UUID] = (
                {i.id for i in await all_items(tx.session, selection.id)} if selection else set()
            )
            if item_id not in items:
                raise NotFound("selected_item")
        note_id = await insert_note(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            procedure_id=procedure_id,
            selected_item_id=item_id,
            body=text,
            raised_by=ctx.user_id,
        )
        tx.record(
            "review_note.raised",
            target=Target("procedure", procedure_id),
            after=Ref(review_note_id=note_id),
        )
    return note_id


async def _note(
    session: AsyncSession, procedure_id: UUID, note_id: UUID
) -> tuple[ReviewNote, list[ReviewNoteEvent]]:
    note = await get_note(session, note_id)
    if note is None or note.procedure_id != procedure_id:
        raise NotFound("review_note")
    events = (await _events_by_note(session, [note]))[note.id]
    return note, events


async def respond(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, note_id: UUID, body: str
) -> None:
    """AC-2: the preparer's response (Responded); the raiser's reply reopens it (Open)."""
    text = _text(body)
    await _procedure(ctx, engagement_id, procedure_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "review_note.respond", ref.resource())
        note, events = await _note(tx.session, procedure_id, note_id)
        if state_of(events) == "cleared":
            raise NoteCleared(str(note_id))
        kind = "reopened" if note.raised_by == ctx.user_id else "responded"
        await insert_note_event(
            tx.session,
            tenant_id=ctx.tenant_id,
            review_note_id=note_id,
            kind=kind,
            body=text,
            by_user=ctx.user_id,
        )
        tx.record(f"review_note.{kind}", target=Target("review_note", note_id))


async def clear(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, note_id: UUID) -> None:
    """AC-3: only the raiser clears; once."""
    await _procedure(ctx, engagement_id, procedure_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "review_note.clear", ref.resource())
        note, events = await _note(tx.session, procedure_id, note_id)
        if note.raised_by != ctx.user_id:
            raise NotRaiser(str(note_id))
        if state_of(events) == "cleared":
            raise NoteCleared(str(note_id))
        await insert_note_event(
            tx.session,
            tenant_id=ctx.tenant_id,
            review_note_id=note_id,
            kind="cleared",
            body=None,
            by_user=ctx.user_id,
        )
        tx.record("review_note.cleared", target=Target("review_note", note_id))


async def notes_for(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> list[NoteView]:
    """AC-7: every note on the procedure with its thread and state, oldest first."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    await _procedure(ctx, engagement_id, procedure_id)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    async with tenant_session(ctx.tenant) as session:
        notes = await notes_of(session, procedure_id)
        events = await _events_by_note(session, notes)
    return [
        NoteView(
            n.id,
            n.selected_item_id,
            state_of(events[n.id]),
            n.raised_by,
            names.get(n.raised_by, ""),
            n.created_at,
            [NoteEntry("raised", n.body, n.raised_by, names.get(n.raised_by, ""), n.created_at)]
            + [
                NoteEntry(e.kind, e.body, e.by_user, names.get(e.by_user, ""), e.created_at)
                for e in events[n.id]
            ],
        )
        for n in notes
    ]
