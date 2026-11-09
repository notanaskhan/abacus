"""The governance room, part 1 (R-02-T12; R-02 §3.5; SPEC-646 AC-26 to AC-30; DEC-93, DEC-3010).
PROTECTED (assurance owns the governance tables, 0668 and 0710).

POR-15 for those charged with governance (TCWG): a room is a governance body (`governance_bodies`),
and its `governance_room` scope resolves to the body's client. Only a `tcwg` grant on the room
opens it (C10's reader rule, DEC-93): a management grant on the client or engagement reaches no
room and every room route answers 404 for it, as for anyone else.

- **Rooms**: the person's `tcwg` grants on `governance_room` scopes, each with the body's name,
  its subject (the client) and the person's role (chair or member, from their contact's current
  membership).
- **Letters**: the communications sent to the body (`governance_communication_sends`), newest
  first, with the person's state: `new` until they acknowledge it, `sent_acknowledged` once they
  have while others haven't, `acknowledged` when every current member has; a planned letter not
  yet sent reads `not_yet`. The committee lists current members with their acknowledgement date.
- **The paper**: the sent version's sections, unsealed, with every citation marker taken out
  (AC-28): the room reads the letter as the client's governance body gets it, never the firm's
  working references. `seen_hash` is the version's content hash.
- **Acknowledge** (`record_acknowledgement`): one insert-only row per version and contact,
  idempotent (a second acknowledgement answers the first); when every current member has
  acknowledged the version, the communication moves to `acknowledged` (AC-27).

Version sections are sealed JSON: `[{"heading": str | null, "body": str}]`; a body may carry
citation markers `[[cite:<id>]]` (A-07-T26 writes them).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from abacus.kernel.clock import today
from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, ScopeFacts, active_grants
from abacus.modules.organisations.api import contact_facts, contacts_of_user, entity_display_name

ROOM: Final = "governance_room"
TCWG: Final = "tcwg"
SECTIONS_FINGERPRINT: Final = "assurance.governance_sections"
_CITE: Final = re.compile(r"\s*\[\[cite:[^\]]{1,80}\]\]")
RoomState = Literal["new", "not_yet", "sent_acknowledged", "acknowledged"]
MemberRole = Literal["chair", "member"]

_UUIDS = ARRAY(PgUUID(as_uuid=True))


class LetterChanged(DomainConflict):
    """The acknowledge call's `seen_hash` is not the sent version's (reload)."""

    code = "item_changed"


# --- the scope resolver (identity's slot) --------------------------------------------------------

_BODY = text(
    "SELECT id, client_id, client_entity_id, name, status FROM governance_bodies WHERE id = :id"
)


async def room_scope(tenant: TenantContext, body_id: UUID) -> ScopeFacts | None:
    """`governance_room` resolves to the body's client; an inactive body opens nothing."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_BODY, {"id": body_id})).first()
    if row is None or row.status != "active":
        return None
    return ScopeFacts(row.client_id)


# --- who is in the room --------------------------------------------------------------------------

_MEMBERS = text(
    "SELECT body_id, contact_id, member_role FROM governance_body_members "
    "WHERE body_id = ANY(:bodies) AND ended_on IS NULL ORDER BY member_role, contact_id"
).bindparams(bindparam("bodies", type_=_UUIDS))


async def _room_grants(ctx: AuthContext) -> dict[UUID, UUID]:
    """The rooms the person's `tcwg` grants open: body id -> grant id."""
    if ctx.tenant.actor_kind != "human" or not ctx.client:
        return {}
    return {
        g.scope_id: g.id
        for g in await active_grants(ctx.tenant, ctx.user_id)
        if g.role == TCWG and g.scope_kind == ROOM
    }


@dataclass(frozen=True)
class RoomContact:
    contact_id: UUID
    name: str
    role: MemberRole


async def _members(
    tenant: TenantContext, body_ids: Sequence[UUID]
) -> dict[UUID, list[RoomContact]]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_MEMBERS, {"bodies": list(body_ids)})).all()
        facts = await contact_facts(session, [r.contact_id for r in rows])
    out: dict[UUID, list[RoomContact]] = {}
    for r in rows:
        name = facts[r.contact_id].display_name if r.contact_id in facts else "Former member"
        out.setdefault(r.body_id, []).append(
            RoomContact(r.contact_id, name, cast(MemberRole, r.member_role))
        )
    return out


async def _my_contacts(ctx: AuthContext) -> list[UUID]:
    async with tenant_session(ctx.tenant) as session:
        return await contacts_of_user(session, ctx.user_id)


@dataclass(frozen=True)
class Room:
    id: UUID
    body_name: str
    subject: str
    member_role: MemberRole
    questions_for_you: int


async def rooms(ctx: AuthContext) -> list[Room]:
    """POR-15's rooms: the bodies the person's `tcwg` grants open (a management grant: none)."""
    grants = await _room_grants(ctx)
    if not grants:
        return []
    mine = set(await _my_contacts(ctx))
    members = await _members(ctx.tenant, list(grants))
    out: list[Room] = []
    async with tenant_session(ctx.tenant) as session:
        for body_id in grants:
            row = (await session.execute(_BODY, {"id": body_id})).first()
            if row is None or row.status != "active":
                continue
            role: MemberRole | None = next(
                (m.role for m in members.get(body_id, []) if m.contact_id in mine), None
            )
            if role is None:
                continue  # a grant without a current membership opens no room
            subject = (
                await entity_display_name(ctx.tenant, row.client_entity_id)
                if row.client_entity_id is not None
                else None
            )
            out.append(Room(body_id, str(row.name), subject or str(row.name), role, 0))
    return sorted(out, key=lambda r: (r.body_name, str(r.id)))


async def _open(ctx: AuthContext, room_id: UUID) -> list[UUID]:
    """The person's contacts that are current members of an open room; 404 otherwise."""
    if room_id not in await _room_grants(ctx):
        raise NotFound(ROOM)
    mine = set(await _my_contacts(ctx))
    members = (await _members(ctx.tenant, [room_id])).get(room_id, [])
    contacts = [m.contact_id for m in members if m.contact_id in mine]
    if not contacts:
        raise NotFound(ROOM)
    return contacts


# --- letters -------------------------------------------------------------------------------------

_SENT = text(
    "SELECT c.id, c.kind, c.status, c.due_on, s.version_id, s.sent_at, v.content_hash, "
    "s.sent_by FROM governance_communication_sends s "
    "JOIN governance_communication_versions v ON v.id = s.version_id "
    "JOIN governance_communications c ON c.id = v.communication_id "
    "WHERE s.governance_body_id = :room AND s.channel = 'governance_room' "
    "ORDER BY s.sent_at DESC"
)
_PLANNED = text(
    "SELECT c.id, c.kind, c.due_on FROM governance_communications c "
    "JOIN governance_recipients r ON r.work_item_id = c.work_item_id "
    "AND r.governance_body_id = :room WHERE c.status IN ('not_started', 'draft', "
    "'awaiting_ep_approval') AND c.channel IS DISTINCT FROM 'ack_envelope' ORDER BY c.due_on"
)
_ACKS = text(
    "SELECT version_id, acknowledged_by_contact_id, acknowledged_at "
    "FROM governance_acknowledgements WHERE version_id = ANY(:versions)"
).bindparams(bindparam("versions", type_=_UUIDS))
TITLE: Final[dict[str, str]] = {  # the room's words for each kind
    "planning_260": "Planning communication (AU-C 260)",
    "completion_260": "Communication at completion (AU-C 260)",
    "sd_mw_265": "Significant deficiencies and material weaknesses (AU-C 265)",
    "reportable_703": "Reportable findings (AU-C 703)",
    "management_letter": "Management letter",
}


@dataclass(frozen=True)
class LetterRow:
    id: UUID | None
    title: str
    status: RoomState
    sent_on: date | None
    due_on: date | None
    acknowledged_on: date | None


@dataclass(frozen=True)
class CommitteeMember:
    name: str
    role: MemberRole
    acknowledged_on: date | None


def roll_up(
    members: Sequence[UUID], acknowledged: dict[UUID, datetime], mine: Sequence[UUID]
) -> RoomState:
    """A sent letter's state for one reader: every current member acknowledged -> acknowledged;
    the reader has -> sent_acknowledged; otherwise new."""
    if members and all(m in acknowledged for m in members):
        return "acknowledged"
    if any(m in acknowledged for m in mine):
        return "sent_acknowledged"
    return "new"


async def letters(
    ctx: AuthContext, room_id: UUID
) -> tuple[list[LetterRow], list[CommitteeMember]]:
    """The room's letters, newest first, and its committee (with the latest letter's dates)."""
    mine = await _open(ctx, room_id)
    members = (await _members(ctx.tenant, [room_id])).get(room_id, [])
    member_ids = [m.contact_id for m in members]
    async with tenant_session(ctx.tenant) as session:
        sent = (await session.execute(_SENT, {"room": room_id})).all()
        planned = (await session.execute(_PLANNED, {"room": room_id})).all()
        acks = (await session.execute(_ACKS, {"versions": [s.version_id for s in sent]})).all()
    by_version: dict[UUID, dict[UUID, datetime]] = {}
    for a in acks:
        by_version.setdefault(a.version_id, {})[a.acknowledged_by_contact_id] = a.acknowledged_at
    rows: list[LetterRow] = []
    seen: set[UUID] = set()
    for s in sent:
        if s.id in seen:
            continue  # the latest send of a communication only
        seen.add(s.id)
        acked = by_version.get(s.version_id, {})
        state = roll_up(member_ids, acked, mine)
        mine_at = min((acked[c] for c in mine if c in acked), default=None)
        rows.append(
            LetterRow(
                s.id, TITLE.get(str(s.kind), str(s.kind)), state, s.sent_at.date(), s.due_on,
                None if mine_at is None else mine_at.date(),
            )
        )  # fmt: skip
    for p in planned:
        if p.id not in seen:
            rows.append(
                LetterRow(
                    p.id, TITLE.get(str(p.kind), str(p.kind)), "not_yet", None, p.due_on, None
                )
            )
    latest = by_version.get(sent[0].version_id, {}) if sent else {}
    committee = [
        CommitteeMember(
            m.name, m.role, None if m.contact_id not in latest else latest[m.contact_id].date()
        )
        for m in members
    ]
    return rows, committee


@dataclass(frozen=True)
class LetterPart:
    heading: str | None
    body: str


@dataclass(frozen=True)
class Letter:
    id: UUID
    version_id: UUID
    title: str
    dated_on: date
    signed_by_user_id: UUID
    sections: tuple[LetterPart, ...]
    status: RoomState
    seen_hash: str
    committee: tuple[CommitteeMember, ...]
    can_acknowledge: bool


def paper(sections: object) -> tuple[LetterPart, ...]:
    """The approved sections as the room reads them: citation markers taken out (AC-28)."""
    out: list[LetterPart] = []
    if not isinstance(sections, list):
        return ()
    for raw in cast(list[object], sections):
        if not isinstance(raw, dict):
            continue
        entry = cast(dict[str, object], raw)
        body = entry.get("body")
        heading = entry.get("heading")
        if not isinstance(body, str):
            continue
        out.append(
            LetterPart(
                heading if isinstance(heading, str) else None,
                _CITE.sub("", body).strip(),
            )
        )
    return tuple(out)


_LETTER = text(
    "SELECT c.id, c.kind, c.status, s.version_id, s.sent_at, s.sent_by, v.content_hash, "
    "v.sections_sealed, s.governance_body_id FROM governance_communication_sends s "
    "JOIN governance_communication_versions v ON v.id = s.version_id "
    "JOIN governance_communications c ON c.id = v.communication_id "
    "WHERE c.id = :id AND s.channel = 'governance_room' ORDER BY s.sent_at DESC LIMIT 1"
)


async def _sent_letter(ctx: AuthContext, communication_id: UUID) -> object:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_LETTER, {"id": communication_id})).first()
    if row is None:
        raise NotFound("governance_communication")
    return row


async def letter(ctx: AuthContext, communication_id: UUID) -> Letter:
    """The sent letter as paper, for a member of the room it was sent to; 404 otherwise."""
    row = await _sent_letter(ctx, communication_id)
    room = cast(UUID, row.governance_body_id)  # type: ignore[attr-defined] -- a raw SQL row's column
    mine = await _open(ctx, room)
    rows, committee = await letters(ctx, room)
    state = cast(RoomState, next((r.status for r in rows if r.id == communication_id), "new"))
    sealed = cast(bytes | None, row.sections_sealed)  # type: ignore[attr-defined] -- a raw SQL row's column
    sections: object = []
    if sealed is not None:
        sections = json.loads(await open_sealed(ctx.tenant_id, sealed, SECTIONS_FINGERPRINT))
    async with tenant_session(ctx.tenant) as session:
        acked = (
            await session.execute(_ACKS, {"versions": [row.version_id]})  # type: ignore[attr-defined] -- a raw SQL row's column
        ).all()
    mine_acked = any(a.acknowledged_by_contact_id in mine for a in acked)
    return Letter(
        communication_id,
        cast(UUID, row.version_id),  # type: ignore[attr-defined] -- a raw SQL row's column
        TITLE.get(str(row.kind), str(row.kind)),  # type: ignore[attr-defined] -- a raw SQL row's column
        cast(datetime, row.sent_at).date(),  # type: ignore[attr-defined] -- a raw SQL row's column
        cast(UUID, row.sent_by),  # type: ignore[attr-defined] -- a raw SQL row's column
        paper(sections),
        state,
        str(row.content_hash),  # type: ignore[attr-defined] -- a raw SQL row's column
        tuple(committee),
        not mine_acked,
    )


# --- acknowledge ---------------------------------------------------------------------------------

_INSERT_ACK = text(
    "INSERT INTO governance_acknowledgements (tenant_id, engagement_id, work_item_id, "
    "communication_id, version_id, acknowledged_by_contact_id, acknowledged_at, channel) "
    "SELECT v.tenant_id, v.engagement_id, v.work_item_id, v.communication_id, v.id, :contact, "
    "clock_timestamp(), :channel FROM governance_communication_versions v WHERE v.id = :version "
    "ON CONFLICT (tenant_id, version_id, acknowledged_by_contact_id) DO NOTHING "
    "RETURNING acknowledged_at, engagement_id, work_item_id"
)
_ROLLED = text(
    "UPDATE governance_communications SET status = 'acknowledged', version = version + 1 "
    "WHERE id = :id AND status = 'sent'"
)


async def record_acknowledgement(
    tx: UnitOfWork,
    communication_id: UUID,
    version_id: UUID,
    contact_id: UUID,
    *,
    members: Sequence[UUID],
    channel: Literal["governance_room", "ack_envelope"] = "governance_room",
) -> bool:
    """One acknowledgement per version and contact (idempotent: False when it already stood).
    When every current member has acknowledged the version, the letter is `acknowledged`."""
    inserted = (
        await tx.session.execute(
            _INSERT_ACK, {"contact": contact_id, "channel": channel, "version": version_id}
        )
    ).first()
    if inserted is None:
        return False
    acked = {
        r.acknowledged_by_contact_id
        for r in (await tx.session.execute(_ACKS, {"versions": [version_id]})).all()
    }
    if members and all(m in acked for m in members):
        await tx.session.execute(_ROLLED, {"id": communication_id})
    tx.record(
        "governance_communication.acknowledged",
        target=Target("governance_communication", communication_id),
        after=Ref(version=version_id, contact=contact_id),
        scope=Scope(engagement_id=inserted.engagement_id, work_item_id=inserted.work_item_id),
    )
    return True


async def acknowledge(
    ctx: AuthContext, communication_id: UUID, seen_hash: str
) -> tuple[date, RoomState]:
    """POR-15's Acknowledge for a member: idempotent; the letter's state after it."""
    found = await letter(ctx, communication_id)
    if found.seen_hash != seen_hash:
        raise LetterChanged
    row = await _sent_letter(ctx, communication_id)
    room = cast(UUID, row.governance_body_id)  # type: ignore[attr-defined] -- a raw SQL row's column
    mine = await _open(ctx, room)
    members = [m.contact_id for m in (await _members(ctx.tenant, [room])).get(room, [])]
    async with uow(ctx.tenant) as tx:
        wrote = await record_acknowledgement(
            tx, communication_id, found.version_id, mine[0], members=members
        )
        if not wrote:
            tx.record(
                "governance_communication.acknowledgement_repeated",
                target=Target("governance_communication", communication_id),
                after=Ref(version=found.version_id, contact=mine[0]),
            )
    rows, _ = await letters(ctx, room)
    state = cast(
        RoomState,
        next((r.status for r in rows if r.id == communication_id), "sent_acknowledged"),
    )
    on = next((r.acknowledged_on for r in rows if r.id == communication_id), None)
    return (on or await today(ctx.tenant)), state
