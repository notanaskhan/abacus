"""Review notes on reviewables (P-04; SPEC-313; TASK-331; P-04-T21, TASK-1400; ADR-160 clause 6).

A reviewer raises a note on a reviewable, optionally anchored to a cell (`RA!C14`), a field key,
a section or a document region; anyone on the team responds; only the person who raised it (or
the engagement partner) clears it, and clearing can be undone by reopening with a reason; the
raiser alone withdraws it. Notes and events are appended (ADR-004); only the note's `status`
changes. That column is authoritative (ADR-160 clause 6, migration 0093) and is written in the
same unit of work as each event, raising included. An open or answered note blocks L2 and above
(R-SO-4) and completion (G5) until it is cleared or withdrawn; a comment never does (DEC-29: no
comment is read here). The agent raises, answers, clears and withdraws nothing (the matrix denies
it; a clear is a person's at the data layer too).

Bodies are sealed from P-04-T21 (migration 0210), each bound to its own note or event; SPEC-313
rows written before hold plaintext and read as they are. Handing a body to a person is an access
event, recorded first. Lists (`list_notes`) never carry a body.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.listing import (
    ListPage,
    capped_total,
    clamp_limit,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
    status_counts,
)
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import (
    PARTNER_ROLES,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    could,
    engagement_team,
    names_of,
)
from abacus.modules.review.events import (
    ReviewNoteCleared,
    ReviewNoteRaised,
    ReviewNoteReopened,
    ReviewNoteResponded,
    ReviewNoteWithdrawn,
)
from abacus.modules.review.models import ReviewableNote, ReviewableNoteEvent
from abacus.modules.review.repository import (
    get_note,
    insert_note,
    insert_note_event,
    lock_note,
    note_events_of,
    note_list_query,
    notes_of,
    set_note_status,
)
from abacus.modules.review.sealing import open_text, record_text_reads, seal_text
from abacus.modules.review.slots import reviewable_facts, reviewables_of

NoteStatus = Literal["open", "responded", "cleared", "closed", "withdrawn"]
EventKind = Literal["responded", "cleared", "reopened", "withdrawn"]
AnchorKind = Literal["cell", "field", "section", "region"]
OPEN: Final = frozenset({"open", "responded"})
RESOURCE: Final = "review_notes"
# The audit and access subject type: `review_note` is fieldwork's (SPEC-041) notes (ED-150).
SUBJECT: Final = "reviewable_note"
_BODY_LIMIT: Final = 2000
_ANCHOR_LIMIT: Final = 120
_LEGACY_ANCHOR: Final = 64  # the SPEC-313 `anchor` column
_ANCHOR_KINDS: Final = frozenset({"cell", "field", "section", "region"})


class NoteInvalid(DomainInvalid):
    code = "review_note_invalid"


class NoteState(DomainConflict):
    code = "review_note_state"


class NotTheRaiser(DomainConflict):
    """Only the reviewer who raised a note (or, to clear it, the engagement partner)."""

    code = "not_the_raiser"


@dataclass(frozen=True)
class NoteEventView:
    kind: str
    body: str | None
    by_name: str
    at: datetime
    by_user: UUID | None = None


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


@dataclass(frozen=True)
class NoteItem:
    """A note without its body (C3 list rows)."""

    id: UUID
    engagement_id: UUID
    target_type: str
    target_id: UUID
    anchor_kind: AnchorKind | None
    anchor_ref: str | None
    status: NoteStatus
    raised_by: UUID
    raised_by_initials: str
    raised_at: datetime
    assignee_user_id: UUID | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class NoteDetail:
    note: NoteItem
    body: str
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
_ACTIONS: Final[dict[str, str]] = {
    "responded": "review_note.respond",
    "cleared": "review_note.clear",
    "reopened": "review_note.clear",
    "withdrawn": "review_note.withdraw",
}
_EVENT_INDEX: Final = ("responded", "cleared", "reopened", "withdrawn")
_EVENTS = {
    "responded": ReviewNoteResponded,
    "cleared": ReviewNoteCleared,
    "reopened": ReviewNoteReopened,
    "withdrawn": ReviewNoteWithdrawn,
}


def status_of(status: str) -> NoteStatus:
    return status if status in AFTER.values() else "open"  # type: ignore[return-value]  # the CHECK's codes


def _text(value: str | None, limit: int, *, required: bool) -> str | None:
    text = (value or "").strip()
    if not text:
        if required:
            raise NoteInvalid(facts={"field": "body"})
        return None
    if len(text) > limit:
        raise NoteInvalid(facts={"field": "length"})
    return text


def _live_human(ctx: AuthContext) -> bool:
    """A note is a person's act: never an agent, a client principal or break-glass support."""
    return (
        isinstance(cast(object, ctx), AuthContext)  # an agent principal reaches a route too
        and not ctx.client
        and ctx.tenant.actor_kind == "human"
        and not ctx.is_support
    )


def _initials(name: str) -> str:
    return "".join(w[0].upper() for w in name.split() if w[:1].isalpha())[:4]


# --- Sealed bodies -----------------------------------------------------------------------------


async def _note_body(tenant: TenantContext, note: ReviewableNote) -> str:
    if note.body_sealed is not None:
        return await open_text(tenant, note.body_sealed, SUBJECT, note.id, "body")
    return note.body or ""


async def _event_body(tenant: TenantContext, event: ReviewableNoteEvent) -> str | None:
    if event.body_sealed is not None:
        return await open_text(tenant, event.body_sealed, "review_note_event", event.id, "body")
    return event.body


async def _sealed(tenant: TenantContext, text: str | None, kind: str, row: UUID) -> bytes | None:
    return None if text is None else await seal_text(tenant, text, kind, row, "body")


# --- Reads -------------------------------------------------------------------------------------


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
    """SPEC-313's read: notes with their bodies (an access event per note handed over)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "workpaper.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        notes = await notes_of(session, engagement_id, target_type, target_id)
        events = await note_events_of(session, [n.id for n in notes])
    codes = {r.target_id: r.code for r in await reviewables_of(ctx.tenant, engagement_id)}
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    await record_text_reads(
        ctx.tenant,
        SUBJECT,
        [n.id for n in notes],
        engagement_id=engagement_id,
        client_id=ref.client_id,
    )
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
                await _note_body(ctx.tenant, n),
                status_of(n.status),
                names.get(n.raised_by, "Former member"),
                n.created_at,
                n.raised_by == ctx.user_id,
                [
                    NoteEventView(
                        e.kind,
                        await _event_body(ctx.tenant, e),
                        names.get(e.by_user, "Former member"),
                        e.created_at,
                        e.by_user,
                    )
                    for e in mine
                ],
            )
        )
    return out


async def _may(ctx: AuthContext, action: str, resource: Resource) -> bool:
    try:
        await authorise(ctx, action, resource)
    except Forbidden:
        return False
    return True


@dataclass(frozen=True)
class _Abilities:
    respond: bool
    clear: bool
    withdraw: bool
    partner: bool


async def _abilities(ctx: AuthContext, resource: Resource, engagement_id: UUID) -> _Abilities:
    if not _live_human(ctx):
        return _Abilities(False, False, False, False)
    team = {m.user_id: m.role for m in await engagement_team(ctx, engagement_id)}
    return _Abilities(
        await _may(ctx, "review_note.respond", resource),
        await _may(ctx, "review_note.clear", resource),
        await _may(ctx, "review_note.withdraw", resource),
        team.get(ctx.user_id) in PARTNER_ROLES,
    )


def _allowed(ctx: AuthContext, note: ReviewableNote, can: _Abilities) -> list[str]:
    status = status_of(note.status)
    mine = note.raised_by == ctx.user_id
    out: list[str] = []
    if status in OPEN and can.respond:
        out.append("review_note.respond")
    if status in OPEN and can.clear and (mine or can.partner):
        out.append("review_note.clear")
    if status in OPEN and can.withdraw and mine:
        out.append("review_note.withdraw")
    return out


def _item(
    ctx: AuthContext, note: ReviewableNote, names: dict[UUID, str], can: _Abilities | None
) -> NoteItem:
    anchor = note.anchor_ref or ({"kind": "cell", "ref": note.anchor} if note.anchor else None)
    kind = anchor.get("kind") if anchor else None
    return NoteItem(
        id=note.id,
        engagement_id=note.engagement_id,
        target_type=note.target_type,
        target_id=note.target_id,
        anchor_kind=cast(AnchorKind, kind) if kind in _ANCHOR_KINDS else None,
        anchor_ref=anchor.get("ref") if anchor else None,
        status=status_of(note.status),
        raised_by=note.raised_by,
        raised_by_initials=_initials(names.get(note.raised_by, "")),
        raised_at=note.created_at,
        assignee_user_id=note.assignee_user_id,
        allowed_actions=_allowed(ctx, note, can) if can is not None else [],
    )


async def list_notes(
    ctx: AuthContext,
    *,
    engagement_id: UUID | None,
    target_type: str | None,
    target_id: UUID | None,
    status: str | None,
    cursor: str | None,
    limit: int | None,
) -> ListPage[NoteItem]:
    """`GET /v1/review-notes`: notes on engagements the caller may read them in (`visible()`,
    walls excluded), oldest first, no bodies; `counts` per status without the status filter."""
    size = clamp_limit(limit)
    query = query_hash(
        engagement_id=engagement_id, target_type=target_type, target_id=target_id, status=status
    )
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=RESOURCE, query=query)
        if cursor
        else None
    )
    base, stmt, sort, id_column = note_list_query(
        ctx, engagement_id=engagement_id, target_type=target_type, target_id=target_id
    )
    if status is not None:
        stmt = stmt.where(ReviewableNote.status == status)
    async with tenant_session(ctx.tenant) as session:
        counts = await status_counts(session, base, ReviewableNote.status.expression)
        total = await capped_total(session, stmt)
        fetched = (
            (
                await session.execute(
                    keyset(stmt, sort=sort, id_column=id_column, after=after, limit=size)
                )
            )
            .scalars()
            .all()
        )
    rows, position = page_of(fetched, limit=size, key=lambda r: r.created_at, id_of=lambda r: r.id)
    names = await names_of(sorted({r.raised_by for r in rows}))
    abilities: dict[UUID, _Abilities] = {}
    for engagement in sorted({r.engagement_id for r in rows}):
        ref = await get_ref(ctx, engagement)
        abilities[engagement] = await _abilities(ctx, ref.resource(), engagement)
    return envelope(
        [_item(ctx, r, names, abilities.get(r.engagement_id)) for r in rows],
        next_position=position,
        tenant_id=ctx.tenant_id,
        resource=RESOURCE,
        query=query,
        total=total,
        counts=counts,
    )


async def _readable(ctx: AuthContext, note_id: UUID) -> tuple[ReviewableNote, Resource]:
    async with tenant_session(ctx.tenant) as session:
        note = await get_note(session, note_id)
    if note is None:
        raise NotFound(SUBJECT)
    ref = await get_ref(ctx, note.engagement_id)
    resource = ref.resource()
    await authorise(ctx, "review_note.read", resource)  # a wall answers 404
    return note, resource


async def note_detail(ctx: AuthContext, note_id: UUID) -> NoteDetail:
    """One note with its body and events; the read is an access event, recorded first."""
    note, resource = await _readable(ctx, note_id)
    async with tenant_session(ctx.tenant) as session:
        events = list(await note_events_of(session, [note.id]))
    await record_text_reads(
        ctx.tenant,
        SUBJECT,
        [note.id],
        engagement_id=note.engagement_id,
        client_id=resource.client_id,
    )
    people = sorted({note.raised_by, *(e.by_user for e in events)})
    names = await names_of(people)
    can = await _abilities(ctx, resource, note.engagement_id)
    return NoteDetail(
        _item(ctx, note, names, can),
        await _note_body(ctx.tenant, note),
        [
            NoteEventView(
                e.kind,
                await _event_body(ctx.tenant, e),
                names.get(e.by_user, "Former member"),
                e.created_at,
                e.by_user,
            )
            for e in events
        ],
    )


# --- Writes ------------------------------------------------------------------------------------


async def _write_raise(
    ctx: AuthContext,
    engagement_id: UUID,
    target_type: str,
    target_id: UUID,
    *,
    anchor_ref: dict[str, str] | None,
    body: str,
    assignee: UUID | None,
    notify: frozenset[UUID],
    work_item_id: UUID | None = None,
) -> UUID:
    note_id, event_id = uuid4(), uuid4()
    legacy_anchor = anchor_ref["ref"] if anchor_ref else None
    if legacy_anchor is not None and len(legacy_anchor) > _LEGACY_ANCHOR:
        legacy_anchor = None
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        resource = replace(ref.resource(), work_item_id=work_item_id)
        await authorise(ctx, "review_note.raise", resource)
        if assignee is not None and (
            assignee == ctx.user_id
            or not await could(ctx, assignee, "review_note.respond", resource)
        ):
            raise NoteInvalid(facts={"field": "assignee_user_id"})
        await insert_note(
            tx.session,
            id=note_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            target_type=target_type,
            target_id=target_id,
            anchor=legacy_anchor,
            anchor_ref=anchor_ref,
            body_sealed=await _sealed(ctx.tenant, body, SUBJECT, note_id),
            raised_by=ctx.user_id,
            assignee_user_id=assignee,
        )
        await insert_note_event(
            tx.session,
            id=event_id,
            tenant_id=ctx.tenant_id,
            note_id=note_id,
            kind="raised",
            body_sealed=await _sealed(ctx.tenant, body, "review_note_event", event_id),
            by_user=ctx.user_id,
        )
        tx.record(
            "review_note.raised",
            target=Target(SUBJECT, note_id),
            after=Ref(target=target_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        recipients = {assignee} if assignee is not None else set(notify)
        recipients.discard(ctx.user_id)
        tx.emit(
            ReviewNoteRaised(
                note_id=note_id,
                engagement_id=engagement_id,
                target_type=target_type,
                target_id=target_id,
                by_user=ctx.user_id,
                recipient_user_ids=sorted(recipients),
            )
        )
    return note_id


async def raise_note(
    ctx: AuthContext,
    engagement_id: UUID,
    target_type: str,
    target_id: UUID,
    anchor: str | None,
    body: str,
) -> UUID:
    """SPEC-313: a note on one of the engagement's reviewables, the anchor a cell."""
    if not _live_human(ctx):
        raise Forbidden("review_note.raise", "role")
    text = cast(str, _text(body, _BODY_LIMIT, required=True))
    pin = _text(anchor, _LEGACY_ANCHOR, required=False)
    targets = {
        (r.target_type, r.target_id) for r in await reviewables_of(ctx.tenant, engagement_id)
    }
    if (target_type, target_id) not in targets:
        raise NotFound("reviewable")
    return await _write_raise(
        ctx,
        engagement_id,
        target_type,
        target_id,
        anchor_ref={"kind": "cell", "ref": pin} if pin else None,
        body=text,
        assignee=None,
        notify=frozenset(),
    )


async def raise_on_target(
    ctx: AuthContext,
    target_type: str,
    target_id: UUID,
    *,
    anchor_kind: str | None,
    anchor_ref: str | None,
    body: str,
    assignee: UUID | None,
) -> NoteDetail:
    """`POST /v1/review-notes` (P-04-T21): a note on a registered reviewable (fail closed), with
    an optional anchor and assignee. The assignee, or with none the target's preparers, gets
    `review_note_raised`."""
    if not _live_human(ctx):
        raise Forbidden("review_note.raise", "role")
    text = cast(str, _text(body, _BODY_LIMIT, required=True))
    pin: dict[str, str] | None = None
    if anchor_kind is not None or anchor_ref is not None:
        ref_text = _text(anchor_ref, _ANCHOR_LIMIT, required=True)
        if anchor_kind not in _ANCHOR_KINDS or ref_text is None:
            raise NoteInvalid(facts={"field": "anchor"})
        pin = {"kind": anchor_kind, "ref": ref_text}
    facts = await reviewable_facts(ctx.tenant, target_type, target_id)
    note_id = await _write_raise(
        ctx,
        facts.engagement_id,
        target_type,
        target_id,
        anchor_ref=pin,
        body=text,
        assignee=assignee,
        notify=facts.preparer_user_ids,
        work_item_id=facts.work_item_id,
    )
    return await note_detail(ctx, note_id)


async def add_event(
    ctx: AuthContext,
    engagement_id: UUID,
    note_id: UUID,
    kind: EventKind,
    body: str | None,
) -> None:
    """Respond (anyone on the team), clear (the raiser or the partner), reopen (the same, with
    why) or withdraw (the raiser alone, while the note is open or answered)."""
    if not _live_human(ctx):
        raise Forbidden(_ACTIONS[kind], "role")
    text = _text(body, _BODY_LIMIT, required=kind in ("responded", "reopened"))
    event_id = uuid4()
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, _ACTIONS[kind], ref.resource())
        note = await lock_note(tx.session, note_id)
        if note is None or note.engagement_id != engagement_id:
            raise NotFound(SUBJECT)
        status = status_of(note.status)
        if kind in ("responded", "cleared", "withdrawn") and status not in OPEN:
            raise NoteState(facts={"status": status})
        if kind == "reopened" and status != "cleared":
            raise NoteState(facts={"status": status})
        if kind == "withdrawn" and note.raised_by != ctx.user_id:
            raise NotTheRaiser(facts={"note": str(note_id)})
        if kind in ("cleared", "reopened") and note.raised_by != ctx.user_id:
            team = {m.user_id: m.role for m in await engagement_team(ctx, engagement_id)}
            if team.get(ctx.user_id) not in PARTNER_ROLES:
                raise NotTheRaiser(facts={"note": str(note_id)})
        await insert_note_event(
            tx.session,
            id=event_id,
            tenant_id=ctx.tenant_id,
            note_id=note.id,
            kind=kind,
            body_sealed=await _sealed(ctx.tenant, text, "review_note_event", event_id),
            by_user=ctx.user_id,
        )
        await set_note_status(tx.session, note.id, AFTER[kind])
        tx.record(
            f"review_note.{kind}",
            target=Target(SUBJECT, note.id),
            after=Ref(kind=_EVENT_INDEX.index(kind)),
            scope=Scope(engagement_id=engagement_id),
        )
        tx.emit(
            _EVENTS[kind](
                note_id=note.id,
                engagement_id=engagement_id,
                target_type=note.target_type,
                target_id=note.target_id,
                by_user=ctx.user_id,
            )
        )


async def note_event(
    ctx: AuthContext, note_id: UUID, kind: EventKind, body: str | None
) -> NoteDetail:
    """The C3 writes (`/v1/review-notes/{id}/respond|clear|withdraw`): the note's engagement
    is read first (a note the caller may not read answers 404), then `add_event`."""
    note, _resource = await _readable(ctx, note_id)
    await add_event(ctx, note.engagement_id, note_id, kind, body)
    return await note_detail(ctx, note_id)
