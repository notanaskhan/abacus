"""Review notes on working papers and trial balances (P-04; SPEC-313; TASK-331).

A reviewer raises a note on a reviewable, optionally anchored to a cell or an account; anyone on
the team responds; only the person who raised it (or the engagement partner) clears it, and
clearing can be undone by reopening with a reason. Notes and events are appended (ADR-004);
only the note's `status` changes. That column is authoritative (ADR-160 clause 6, migration
0093) and is written in the same unit of work as each event, raising included; reopening sets
it back to open. An open or answered note blocks completion (G5) until it is cleared. The agent
raises, answers and clears nothing (the matrix denies it).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import PARTNER_ROLES, AuthContext, authorise, engagement_team
from abacus.modules.review.repository import (
    insert_note,
    insert_note_event,
    lock_note,
    note_events_of,
    notes_of,
    set_note_status,
)
from abacus.modules.review.slots import reviewables_of

NoteStatus = Literal["open", "responded", "cleared", "closed", "withdrawn"]
OPEN: Final = frozenset({"open", "responded"})


class NoteInvalid(DomainInvalid):
    code = "review_note_invalid"


class NoteState(DomainConflict):
    code = "review_note_state"


class NotTheRaiser(DomainConflict):
    """Only the reviewer who raised a note, or the engagement partner, clears it."""

    code = "not_the_raiser"


@dataclass(frozen=True)
class NoteEventView:
    kind: str
    body: str | None
    by_name: str
    at: datetime


@dataclass(frozen=True)
class NoteView:
    id: UUID
    target_type: str
    target_id: UUID
    target_code: str | None
    anchor: str | None
    body: str
    status: NoteStatus
    raised_by_name: str
    raised_at: datetime
    raised_by_me: bool
    events: list[NoteEventView]


# What each event leaves the note as (C3 adds closed and withdrawn).
AFTER: Final[dict[str, NoteStatus]] = {
    "raised": "open",
    "responded": "responded",
    "cleared": "cleared",
    "reopened": "open",
    "closed": "closed",
    "withdrawn": "withdrawn",
}


def status_of(status: str) -> NoteStatus:
    return status if status in AFTER.values() else "open"  # type: ignore[return-value]  # the CHECK's codes


def _text(value: str | None, limit: int, *, required: bool) -> str | None:
    text = (value or "").strip()
    if not text:
        if required:
            raise NoteInvalid("body")
        return None
    if len(text) > limit:
        raise NoteInvalid("length")
    return text


async def open_note_counts(tenant: TenantContext, engagement_id: UUID) -> dict[UUID, int]:
    """Open or answered notes per target (for the matrix and G5; callers authorised)."""
    async with tenant_session(tenant) as session:
        notes = await notes_of(session, engagement_id)
    counts: dict[UUID, int] = {}
    for n in notes:
        if n.status in OPEN:
            counts[n.target_id] = counts.get(n.target_id, 0) + 1
    return counts


async def notes_for(
    ctx: AuthContext,
    engagement_id: UUID,
    target_type: str | None = None,
    target_id: UUID | None = None,
) -> list[NoteView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "workpaper.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        notes = await notes_of(session, engagement_id, target_type, target_id)
        events = await note_events_of(session, [n.id for n in notes])
    codes = {r.target_id: r.code for r in await reviewables_of(ctx.tenant, engagement_id)}
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    out: list[NoteView] = []
    for n in notes:
        # The raise itself shows as raised_by and raised_at, not as an event row.
        mine = [e for e in events if e.note_id == n.id and e.kind != "raised"]
        out.append(
            NoteView(
                n.id,
                n.target_type,
                n.target_id,
                codes.get(n.target_id),
                n.anchor,
                n.body,
                status_of(n.status),
                names.get(n.raised_by, "Former member"),
                n.created_at,
                n.raised_by == ctx.user_id,
                [
                    NoteEventView(
                        e.kind, e.body, names.get(e.by_user, "Former member"), e.created_at
                    )
                    for e in mine
                ],
            )
        )
    return out


async def raise_note(
    ctx: AuthContext,
    engagement_id: UUID,
    target_type: str,
    target_id: UUID,
    anchor: str | None,
    body: str,
) -> UUID:
    text = _text(body, 2000, required=True)
    pin = _text(anchor, 64, required=False)
    targets = {
        (r.target_type, r.target_id) for r in await reviewables_of(ctx.tenant, engagement_id)
    }
    if (target_type, target_id) not in targets:
        raise NotFound("reviewable")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "review_note.raise", ref.resource())
        note_id = await insert_note(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            target_type=target_type,
            target_id=target_id,
            anchor=pin,
            body=text,
            raised_by=ctx.user_id,
        )
        await insert_note_event(
            tx.session,
            tenant_id=ctx.tenant_id,
            note_id=note_id,
            kind="raised",
            body=text,  # migration 0076: every event but a clear carries a body
            by_user=ctx.user_id,
        )
        tx.record("review_note.raised", target=Target("review_note", note_id))
    return note_id


async def add_event(
    ctx: AuthContext,
    engagement_id: UUID,
    note_id: UUID,
    kind: Literal["responded", "cleared", "reopened"],
    body: str | None,
) -> None:
    """Respond (anyone on the team), clear (the raiser or the partner) or reopen (with why)."""
    text = _text(body, 2000, required=kind != "cleared")
    action = {
        "responded": "review_note.respond",
        "cleared": "review_note.clear",
        "reopened": "review_note.clear",
    }[kind]
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, action, ref.resource())
        note = await lock_note(tx.session, note_id)
        if note is None or note.engagement_id != engagement_id:
            raise NotFound("review_note")
        status = status_of(note.status)
        if kind in ("responded", "cleared") and status not in OPEN:
            raise NoteState(status)
        if kind == "reopened" and status != "cleared":
            raise NoteState(status)
        if kind in ("cleared", "reopened") and note.raised_by != ctx.user_id:
            team = {m.user_id: m.role for m in await engagement_team(ctx, engagement_id)}
            if team.get(ctx.user_id) not in PARTNER_ROLES:
                raise NotTheRaiser(str(note_id))
        await insert_note_event(
            tx.session,
            tenant_id=ctx.tenant_id,
            note_id=note.id,
            kind=kind,
            body=text,
            by_user=ctx.user_id,
        )
        await set_note_status(tx.session, note.id, AFTER[kind])
        tx.record(
            f"review_note.{kind}",
            target=Target("review_note", note.id),
            after=Ref(kind=("responded", "cleared", "reopened").index(kind)),
        )
