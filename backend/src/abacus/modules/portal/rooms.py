"""The third-party room read model (R-01-T13; C5 section `portal-pbc`; POR-14; DEC-387). A BFF
over `requests.api`, `evidence.api`, `engagements.api` and `identity.api`: it owns no business
truth.

- The room is the caller's open delegations: requests they hold an active `request_item` grant
  on (CLI-04's `third_party`, P-06's `delegate`) whose delegation under that grant is open, of
  one engagement (the one delegated to them most recently). Each row is authorised
  `portal_documents.read` through `delegated_only` on its own facts before anything of it is
  read; nothing else of the engagement is read, counted or named (INV-4).
- Fail closed (ADR P-12): an engagement holding a tax return is left out without the client's
  C19 `third_party_disclosure` consent, which nobody holds until T-01 registers it.
- Rows by band (the request's category, in binder order): the sub-line state and its date, the
  disc, the firm-written guidance, files with receipts, the firm's return note, the shared
  thread's size and `allowed_actions` (`upload`, `withdraw`, `comment`; never `ignore`).
- `suggest`: "Which request is this for?" scored by code on file names only (ADR-050).

No field carries a firm status code, an amount, a confidence, the agent or another party's data.
A person with no delegation, a flag off or any refusal answers 404, one answer for every case.
Nothing here writes.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from abacus.kernel._flags import EVIDENCE_WITHDRAWAL, PORTAL_THIRD_PARTY_ROOM
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.engagements.api import (
    EngagementRef,
    client_contact_organisations_of_users,
    engagement_label,
    get_ref,
)
from abacus.modules.evidence.api import PortalFile, portal_files
from abacus.modules.identity.api import (
    DELEGATE_ROLES,
    AuthContext,
    Forbidden,
    ItemFacts,
    Resource,
    allowed_actions,
    authorise,
    firm_name,
    firm_time_zone,
    names_of,
    portal_scopes,
)
from abacus.modules.portal.documents import (
    UNCATEGORISED,
    code_of,
    receipt_kind,
    return_reason,
)
from abacus.modules.portal.pbc_contract import (
    Disc,
    PortalAction,
    PortalFileOut,
    PortalReceiptOut,
    PortalReturnedOut,
    PortalRoomBandOut,
    PortalRoomOut,
    PortalRoomRowOut,
    RoomRowState,
    RoomSuggestionOut,
    RoomSuggestOut,
)
from abacus.modules.requests.api import RoomItem, room_items, third_party_consented

READ: Final = "portal_documents.read"
_ROW_ACTIONS: Final = ("evidence.upload", "comment.create", "evidence.withdraw")
_UPLOADABLE: Final = frozenset({"requested", "uploaded", "returned"})
_DONE: Final = frozenset({"uploaded", "received"})
# A file-name token shorter than this, or a number, says nothing about which request it is.
_MIN_TOKEN: Final = 3
_STOP: Final = frozenset(
    {"pdf", "jpg", "jpeg", "png", "heic", "xlsx", "docx", "csv", "the", "and"}
)


# --- pure rules (unit-tested) -------------------------------------------------------------------


def row_state(
    status: str, files: Sequence[PortalFile], me: UUID, due_on: date | None, zone: ZoneInfo
) -> tuple[RoomRowState, date | None, Disc]:
    """The row's sub-line and disc: Returned (red tint, ring), the caller's own unaccepted upload
    in review ("You uploaded Sep 22 · {firm} is reviewing it", done), any other file in
    ("Uploaded Sep 2", done), else what is still owed ("Due Sep 18", ring)."""
    if status == "returned":
        back = files[0].sent_back if files else None
        return "returned", back.at.astimezone(zone).date() if back is not None else None, "ring"
    if status in _DONE and files:
        newest = files[0]
        own = newest.uploader_user_id == me and newest.arrived == "client_upload"
        if own and not newest.accepted and status == "uploaded":
            return "in_review", newest.created_at.astimezone(zone).date(), "done"
        return "uploaded", newest.created_at.astimezone(zone).date(), "done"
    return "due", due_on, "ring"


def tokens(text: str) -> frozenset[str]:
    """A name's words, folded: "Keystone_Bridge-Letter_Q4.pdf" -> {keystone, bridge, letter}."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().casefold()
    return frozenset(
        word
        for word in re.split(r"[^a-z0-9]+", folded)
        if len(word) >= _MIN_TOKEN and not word.isdigit() and word not in _STOP
    )


def suggest(file_name: str, rows: Sequence[tuple[UUID, str]]) -> UUID | None:
    """The one request whose title shares the most words with the file's name; none when no
    word is shared or two requests tie (the person chooses). Code only, names only (ADR-050)."""
    words = tokens(file_name)
    scored = sorted(
        ((len(words & tokens(title)), str(item), item) for item, title in rows),
        key=lambda s: (-s[0], s[1]),
    )
    if not scored or scored[0][0] == 0:
        return None
    if len(scored) > 1 and scored[1][0] == scored[0][0]:
        return None
    return scored[0][2]


# --- the room -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Row:
    room: RoomItem
    out: PortalRoomRowOut
    band: tuple[str, str, int, int]  # code, label, binder order, category position


@dataclass(frozen=True)
class _Room:
    engagement: EngagementRef
    rows: list[_Row]


def _facts(room: RoomItem) -> ItemFacts:
    return ItemFacts(
        room.client_visible, room.client_assignee_user_id, delegated_to=room.delegated_to
    )


def _resource(engagement: EngagementRef, room: RoomItem) -> Resource:
    return replace(engagement.resource(), work_item_id=room.binder.work_item_id, item=_facts(room))


async def _delegated(ctx: AuthContext) -> list[RoomItem]:
    if not await flag_enabled(ctx.tenant, PORTAL_THIRD_PARTY_ROOM):
        raise NotFound(PORTAL_THIRD_PARTY_ROOM.name)
    held = await portal_scopes(ctx)
    ids = [
        g.scope_id
        for g in held.scopes
        if g.role in DELEGATE_ROLES and g.scope_kind == "request_item"
    ]
    found = await room_items(ctx, ids) if ids else []
    if not found:
        raise NotFound("room")
    return found


async def _authorised(ctx: AuthContext) -> tuple[EngagementRef, list[RoomItem]]:
    """The newest-delegated engagement whose requests may go to a third party, and its rows the
    caller is authorised to read (each through `delegated_only`); else 404."""
    found = await _delegated(ctx)
    newest: dict[UUID, datetime] = {}
    for room in found:
        eid = room.item.engagement_id
        newest[eid] = max(newest.get(eid, room.delegated_at), room.delegated_at)
    for eid in sorted(newest, key=lambda e: (newest[e], str(e)), reverse=True):
        if not await third_party_consented(ctx.tenant, eid):
            continue  # §7216: fail closed (ADR P-12)
        try:
            engagement = await get_ref(ctx, eid)
        except NotFound:
            continue
        mine: list[RoomItem] = []
        for room in (r for r in found if r.item.engagement_id == eid):
            try:
                await authorise(ctx, READ, _resource(engagement, room))
            except (Forbidden, NotFound):
                continue
            mine.append(room)
        if mine:
            return engagement, mine
    raise NotFound("room")


async def _rows(
    ctx: AuthContext, engagement: EngagementRef, rooms: list[RoomItem], zone: ZoneInfo
) -> list[_Row]:
    files = {
        r.item.id: await portal_files(
            ctx.tenant, r.item.id, [link.evidence_version_id for link in r.item.links]
        )
        for r in rooms
    }
    reviewers = {
        f.sent_back.by_user_id
        for fs in files.values()
        for f in fs
        if f.sent_back is not None and f.sent_back.by_user_id is not None
    }
    names = await names_of(sorted(reviewers, key=str))
    withdrawal_on = await flag_enabled(ctx.tenant, EVIDENCE_WITHDRAWAL)
    binders: dict[UUID, int] = {}
    out: list[_Row] = []
    for room in rooms:
        item = room.item
        own = files[item.id]
        actions: frozenset[str] = (
            frozenset()
            if engagement.archived
            else await allowed_actions(ctx, _resource(engagement, room), _ROW_ACTIONS)
        )
        linked_by = {link.evidence_version_id: link.created_by_kind for link in item.links}
        state, state_on, disc = row_state(item.status, own, ctx.user_id, item.due_on, zone)
        returned = None
        back = own[0].sent_back if own and item.status == "returned" else None
        if back is not None:
            returned = PortalReturnedOut(
                reason=return_reason(back.reason_code, room.binder_kind),
                note=back.note,
                by_name=names.get(back.by_user_id, "") if back.by_user_id is not None else "",
                on=back.at.astimezone(zone).date(),
            )
        out_files: list[PortalFileOut] = []
        for n, f in enumerate(own):
            kind = receipt_kind(f, linked_by.get(f.version_id, "human"), ctx.user_id)
            out_files.append(
                PortalFileOut(
                    id=f.version_id,
                    name=f.name,
                    size_bytes=f.size_bytes,
                    # Nobody else is named in a third party's room (INV-4).
                    receipt=PortalReceiptOut(kind=kind, on=f.created_at.astimezone(zone).date()),
                    withdrawable=withdrawal_on
                    and f.withdrawable_kind
                    and "evidence.withdraw" in actions
                    and f.uploader_user_id == ctx.user_id,
                    struck=n == 0 and back is not None,
                )
            )
        allowed: list[PortalAction] = []
        if item.status in _UPLOADABLE and "evidence.upload" in actions:
            allowed.append("upload")
        if any(f.withdrawable for f in out_files):
            allowed.append("withdraw")
        if "comment.create" in actions:
            allowed.append("comment")
        category = room.category
        band = (
            (code_of(category.name), category.name, category.position)
            if category is not None
            else (UNCATEGORISED, item.group, 1_000_000)
        )
        order = binders.setdefault(room.binder.id, len(binders))
        out.append(
            _Row(
                room,
                PortalRoomRowOut(
                    id=item.id,
                    engagement_id=item.engagement_id,
                    title=item.title,
                    state=state,
                    state_on=state_on,
                    disc=disc,
                    guidance=item.guidance,
                    files=out_files,
                    returned=returned,
                    comment_count=item.comment_count,
                    allowed_actions=allowed,
                ),
                (band[0], band[1], order, band[2]),
            )
        )
    return out


async def _room(ctx: AuthContext) -> _Room:
    engagement, rooms = await _authorised(ctx)
    zone = ZoneInfo(await firm_time_zone(ctx.tenant))
    return _Room(engagement, await _rows(ctx, engagement, rooms, zone))


async def read_room(ctx: AuthContext) -> PortalRoomOut:
    """POR-14: exactly the caller's delegated requests of one engagement, by band, "n of N"."""
    room = await _room(ctx)
    bands: dict[tuple[int, int, str], tuple[str, list[PortalRoomRowOut]]] = {}
    for row in room.rows:
        code, label, order, position = row.band
        bands.setdefault((order, position, code), (label, []))[1].append(row.out)
    out_bands = [
        PortalRoomBandOut(
            code=code,
            label=label,
            uploaded=sum(1 for r in rows if r.disc == "done"),
            total=len(rows),
            rows=rows,
        )
        for (_, _, code), (label, rows) in sorted(bands.items(), key=lambda kv: kv[0])
    ]
    total = len(room.rows)
    label = await engagement_label(ctx.tenant, room.engagement.id)
    organisations = await client_contact_organisations_of_users(
        ctx.tenant, room.engagement.id, [ctx.user_id]
    )
    return PortalRoomOut(
        engagement_label=f"{label.client_name} · {label.name}" if label is not None else "",
        firm_name=await firm_name(ctx.tenant_id),
        organisation_name=organisations.get(ctx.user_id, ""),
        intro=None,
        uploaded_count=sum(b.uploaded for b in out_bands),
        total=total,
        complete=total > 0 and all(r.room.item.status == "received" for r in room.rows),
        bands=out_bands,
    )


async def suggest_request(ctx: AuthContext, file_names: Sequence[str]) -> RoomSuggestOut:
    """ "Which request is this for?": per file name, the room's one request that still takes an
    upload whose title shares the most words with it, or none. Reads names only; writes nothing."""
    room = await _room(ctx)
    open_rows = [(r.out.id, r.out.title) for r in room.rows if "upload" in r.out.allowed_actions]
    return RoomSuggestOut(
        suggestions=[
            RoomSuggestionOut(file_name=name, request_item_id=suggest(name, open_rows))
            for name in file_names
        ]
    )
