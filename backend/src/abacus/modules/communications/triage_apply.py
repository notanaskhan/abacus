"""Triage: INB-02's bundle, its destinations and Apply (N-01-T18; N-01 §3.4; ADR-210 clause 5;
DEC-1061).

- **Bundle:** a message's open attachments (New, Waiting, Held), each with its latest code flags,
  the classification and candidates where code has them (rule classification and the matcher
  land with N-01-T17), and defaults a person may change: File, forced to Hold when a flag says
  so.
- **Destinations:** a picker tree under the client, each node re-authorised: the client's
  permanent file and its work items, a work item's source documents folder, and what a module
  registers (`register_intake_destination`: requests' open items, notices, close receipts).
- **Apply:** one unit of work for the message: one insert-only decision per attachment by a live
  person (the table's CHECK), then the effect. File: a new item or version n+1 (supersede or keep
  both; superseding never deletes) through `evidence.api.file_intake_object`, and a request
  item's fulfilment (`requests.api.fulfil_by_upload`). Ignore needs `inbox.triage` and a reason.
  Hold needs `inbox.ask_client`. A `force_hold` flag refuses any decision but Hold.
- **Bulk-file:** only an unflagged attachment with one confident, unchanged candidate files as
  suggested; the rest say why.
The agent and the system are refused at the matrix, here and by the decisions table's CHECK.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import INBOX_FIRM_INTAKE
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.communications.intake_scope import readable_thread
from abacus.modules.engagements.api import client_of, work_item_index
from abacus.modules.evidence.api import IntakeObject, file_intake_object
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.requests.api import fulfil_by_upload, item_ref

FILE: Final = "inbox.file"
TRIAGE: Final = "inbox.triage"
ASK_CLIENT: Final = "inbox.ask_client"
OPEN: Final = ("new", "waiting", "held")
CONFIDENT: Final = 0.9


class FlagRequiresHold(DomainConflict):
    """A code flag on this file only allows Hold (`force_hold`)."""

    code = "flag_requires_hold"


class AttachmentNotOpen(DomainConflict):
    """The file was filed, ignored or withdrawn since the triage was read."""

    code = "attachment_not_open"


class DestinationRequired(DomainInvalid):
    """File needs a destination; Ignore needs a reason."""

    code = "decision_incomplete"


class DestinationOutsideClient(DomainConflict):
    """The destination belongs to another client than the file's."""

    code = "destination_outside_client"


# --- The destination slot ------------------------------------------------------------------------


@dataclass(frozen=True)
class Node:
    kind: str
    id: UUID
    label: str
    folder_kind: str | None = None
    has_children: bool = False
    selectable: bool = True
    reason_code: str | None = None


@dataclass(frozen=True)
class Placement:
    """Where a destination files: the engagement and work item (none for the permanent file)
    and, for a request, the item it fulfils."""

    engagement_id: UUID | None
    work_item_id: UUID | None
    client_id: UUID
    request_item_id: UUID | None = None


@dataclass(frozen=True)
class IntakeDestination:
    kind: str
    nodes: Callable[[AuthContext, UUID, UUID | None], Awaitable[Sequence[Node]]]
    place: Callable[[TenantContext, UnitOfWork, UUID], Awaitable[Placement]]


_DESTINATIONS: dict[str, IntakeDestination] = {}


def register_intake_destination(destination: IntakeDestination) -> None:
    """A module registers what an intake file may be filed into (once, at import)."""
    _DESTINATIONS[destination.kind] = destination


async def _work_item_facts(tx: UnitOfWork, work_item_id: UUID) -> tuple[UUID | None, UUID]:
    """The work item's engagement and client, from the engagements index."""
    items = work_item_index()
    found = (
        await tx.session.execute(
            items.select()
            .with_only_columns(items.c.engagement_id, items.c.client_id)
            .where(items.c.id == work_item_id)
        )
    ).one_or_none()
    if found is None:
        raise NotFound("work_item")
    return found.engagement_id, found.client_id


async def _work_item_nodes(ctx: AuthContext, client_id: UUID, parent: UUID | None) -> list[Node]:
    if parent is not None:
        return [Node("work_item_folder", parent, "Source documents", "source_documents")]
    items = work_item_index()
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                items.select()
                .with_only_columns(items.c.id, items.c.name)
                .where(items.c.client_id == client_id)
                .order_by(items.c.name)
            )
        ).all()
    return [Node("work_item", r.id, r.name, has_children=True, selectable=False) for r in rows]


async def _place_work_item_folder(
    tenant: TenantContext, tx: UnitOfWork, work_item_id: UUID
) -> Placement:
    del tenant
    engagement, client = await _work_item_facts(tx, work_item_id)
    return Placement(engagement, work_item_id, client)


async def _permanent_nodes(ctx: AuthContext, client_id: UUID, parent: UUID | None) -> list[Node]:
    return [] if parent is not None else [Node("permanent_file", client_id, "Permanent file")]


async def _place_permanent(tenant: TenantContext, tx: UnitOfWork, client_id: UUID) -> Placement:
    del tenant, tx
    return Placement(None, None, client_id)


async def _request_nodes(ctx: AuthContext, client_id: UUID, parent: UUID | None) -> list[Node]:
    return []  # requests lists its open items when it registers its own picker (DEC-1061)


async def _place_request(
    tenant: TenantContext, tx: UnitOfWork, request_item_id: UUID
) -> Placement:
    item = await item_ref(tx, request_item_id, lock=True)
    client = await client_of(tenant, item.engagement_id)
    if client is None:
        raise NotFound("request_item")
    return Placement(item.engagement_id, None, client, request_item_id)


register_intake_destination(
    IntakeDestination("permanent_file", _permanent_nodes, _place_permanent)
)
register_intake_destination(
    IntakeDestination("work_item_folder", _work_item_nodes, _place_work_item_folder)
)
register_intake_destination(IntakeDestination("request", _request_nodes, _place_request))


async def _flagged(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("inbox")
    if not await flag_enabled(ctx.tenant, INBOX_FIRM_INTAKE):
        raise NotFound(INBOX_FIRM_INTAKE.name)


async def destinations(
    ctx: AuthContext, client_id: UUID, kind: str | None, parent: UUID | None
) -> list[Node]:
    """`GET /v1/destinations`: the picker's nodes under the client, for a person who may file
    there."""
    await _flagged(ctx)
    await authorise(ctx, TRIAGE, Resource.client(ctx.tenant_id, client_id))
    kinds = [kind] if kind is not None else list(_DESTINATIONS)
    out: list[Node] = []
    for k in kinds:
        found = _DESTINATIONS.get(k)
        if found is not None:
            out.extend(await found.nodes(ctx, client_id, parent))
    return out


async def thread_of(ctx: AuthContext, message_id: UUID) -> UUID:
    """The message's thread, once the caller may read it (404 otherwise)."""
    async with tenant_session(ctx.tenant) as session:
        thread = (
            await session.execute(
                text("SELECT thread_id FROM inbound_messages WHERE id = :id"), {"id": message_id}
            )
        ).scalar_one_or_none()
    if thread is None:
        raise NotFound("inbound_message")
    await readable_thread(ctx, thread)
    return thread


# --- The bundle ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Card:
    attachment_id: UUID
    file_name: str
    status: str
    flags: list[tuple[str, str]]
    decision: str
    decision_forced: bool


@dataclass(frozen=True)
class Bundle:
    message_id: UUID
    client_id: UUID | None
    cards: list[Card] = field(default_factory=list[Card])


async def bundle(ctx: AuthContext, message_id: UUID) -> Bundle:
    """`GET /v1/inbox/messages/{id}/triage`: the message's open files with their defaults."""
    await _flagged(ctx)
    async with tenant_session(ctx.tenant) as session:
        thread = (
            await session.execute(
                text("SELECT thread_id FROM inbound_messages WHERE id = :id"), {"id": message_id}
            )
        ).scalar_one_or_none()
    if thread is None:
        raise NotFound("inbound_message")
    header = await readable_thread(ctx, thread)
    if header.client_id is None:
        raise NotFound("inbound_message")  # matched first (INB-01 b), then triaged
    await authorise(ctx, TRIAGE, Resource.client(ctx.tenant_id, header.client_id))
    async with tenant_session(ctx.tenant) as session:
        files = (
            await session.execute(
                text(
                    "SELECT id, file_name, status FROM inbox_attachments "
                    "WHERE message_id = :id AND status = ANY(:open) ORDER BY created_at, id"
                ),
                {"id": message_id, "open": list(OPEN)},
            )
        ).all()
        flags = (
            await session.execute(
                text(
                    "SELECT f.attachment_id, f.kind, f.severity FROM inbox_attachment_flags f "
                    "WHERE f.attachment_id = ANY(:ids) AND f.run_no = (SELECT max(g.run_no) "
                    "FROM inbox_attachment_flags g WHERE g.attachment_id = f.attachment_id)"
                ),
                {"ids": [f.id for f in files]},
            )
        ).all()
    cards: list[Card] = []
    for f in files:
        mine = [(r.kind, r.severity) for r in flags if r.attachment_id == f.id]
        forced = any(sev == "force_hold" for _k, sev in mine)
        cards.append(Card(f.id, f.file_name, f.status, mine, "hold" if forced else "file", forced))
    return Bundle(message_id, header.client_id, cards)


# --- Apply ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Decision:
    attachment_id: UUID
    decision: str  # file | ignore | hold
    destination_kind: str | None = None
    destination_id: UUID | None = None
    version_mode: str | None = None
    supersede_version_id: UUID | None = None
    keep_both: bool = False
    rename_to: str | None = None
    reason_codes: tuple[str, ...] = ()
    tell_client: bool = False


@dataclass(frozen=True)
class Applied:
    filed: int
    ignored: int
    held: int
    notified_user_ids: list[UUID]


_ATTACHMENT = text(
    "SELECT a.id, a.client_id, a.thread_id, a.status, a.file_name, a.media_type, a.size_bytes, "
    "a.fingerprint, a.storage_key, a.storage_version_id, a.key_mode, m.channel "
    "FROM inbox_attachments a JOIN inbound_messages m ON m.id = a.message_id "
    "WHERE a.id = :id AND a.message_id = :message FOR UPDATE OF a"
)


async def _decide(tx: UnitOfWork, ctx: AuthContext, given: Decision, message_id: UUID) -> str:
    row = (
        await tx.session.execute(_ATTACHMENT, {"id": given.attachment_id, "message": message_id})
    ).one_or_none()
    if row is None:
        raise NotFound("inbox_attachment")
    if row.status not in OPEN:
        raise AttachmentNotOpen
    forced = (
        await tx.session.execute(
            text(
                "SELECT 1 FROM inbox_attachment_flags f WHERE f.attachment_id = :id "
                "AND f.severity = 'force_hold' AND f.run_no = (SELECT max(g.run_no) FROM "
                "inbox_attachment_flags g WHERE g.attachment_id = :id) LIMIT 1"
            ),
            {"id": row.id},
        )
    ).first()
    if forced is not None and given.decision != "hold":
        raise FlagRequiresHold
    client = Resource.client(ctx.tenant_id, row.client_id)
    filed_version: UUID | None = None
    if given.decision == "file":
        if given.destination_kind is None or given.destination_id is None:
            raise DestinationRequired
        destination = _DESTINATIONS.get(given.destination_kind)
        if destination is None:
            raise DestinationRequired
        placement = await destination.place(ctx.tenant, tx, given.destination_id)
        if placement.client_id != row.client_id:
            raise DestinationOutsideClient
        next_of = (
            given.supersede_version_id
            if given.version_mode in ("new_version", "new_version_supersede")
            and not given.keep_both
            else None
        )
        filed = await file_intake_object(
            tx,
            IntakeObject(
                attachment_id=row.id,
                client_id=row.client_id,
                channel=row.channel,
                storage_key=row.storage_key,
                storage_version_id=row.storage_version_id or "",
                fingerprint=row.fingerprint,
                size_bytes=int(row.size_bytes),
                media_type=row.media_type,
                detached=row.key_mode == "detached",
            ),
            tenant_id=ctx.tenant_id,
            title=(given.rename_to or row.file_name)[:200],
            engagement_id=placement.engagement_id,
            work_item_id=placement.work_item_id,
            next_version_of=next_of,
            supersede=given.version_mode == "new_version_supersede" and next_of is not None,
            actor_kind=ctx.tenant.actor_kind,
            actor_id=ctx.tenant.actor_id,
        )
        filed_version = filed.evidence_version_id
        if placement.request_item_id is not None:
            await fulfil_by_upload(
                tx,
                request_item_id=placement.request_item_id,
                evidence_version_id=filed.evidence_version_id,
            )
        status = "filed"
    elif given.decision == "ignore":
        if not given.reason_codes:
            raise DestinationRequired
        await authorise(ctx, TRIAGE, client)
        status = "ignored"
    else:
        await authorise(ctx, ASK_CLIENT, client)
        status = "held"
    await tx.session.execute(
        text(
            "INSERT INTO triage_decisions (tenant_id, attachment_id, thread_id, decision, "
            "destination_kind, destination_id, version_mode, supersede_version_id, keep_both, "
            "rename_to, reason_codes, tell_client) VALUES (:tenant, :attachment, :thread, "
            ":decision, :kind, :dest, :mode, :supersede, :keep, :rename, :reasons, :tell)"
        ),
        {
            "tenant": ctx.tenant_id,
            "attachment": row.id,
            "thread": row.thread_id,
            "decision": given.decision,
            "kind": given.destination_kind if given.decision == "file" else None,
            "dest": given.destination_id if given.decision == "file" else None,
            "mode": (given.version_mode or "new_document") if given.decision == "file" else None,
            "supersede": given.supersede_version_id if given.decision == "file" else None,
            "keep": given.keep_both,
            "rename": given.rename_to,
            "reasons": list(given.reason_codes) or None,
            "tell": given.tell_client,
        },
    )
    await tx.session.execute(
        text(
            "UPDATE inbox_attachments SET status = :status, "
            "filed_evidence_version_id = :version, "
            "filed_destination_kind = :kind, filed_destination_id = :dest WHERE id = :id"
        ),
        {
            "status": status,
            "version": filed_version,
            "kind": given.destination_kind if status == "filed" else None,
            "dest": given.destination_id if status == "filed" else None,
            "id": row.id,
        },
    )
    tx.record(
        f"inbox_attachment.{status}",
        target=Target("inbox_attachment", row.id),
        after=Ref(attachment_id=row.id),
    )
    return status


async def apply(ctx: AuthContext, message_id: UUID, decisions: Sequence[Decision]) -> Applied:
    """`POST /v1/inbox/messages/{id}/triage/apply`: every decision in one unit of work."""
    await _flagged(ctx)
    async with tenant_session(ctx.tenant) as session:
        thread = (
            await session.execute(
                text("SELECT thread_id FROM inbound_messages WHERE id = :id"), {"id": message_id}
            )
        ).scalar_one_or_none()
    if thread is None:
        raise NotFound("inbound_message")
    header = await readable_thread(ctx, thread)
    if header.client_id is None:
        raise NotFound("inbound_message")
    await authorise(ctx, FILE, Resource.client(ctx.tenant_id, header.client_id))
    counts = {"filed": 0, "ignored": 0, "held": 0}
    async with uow(ctx.tenant) as tx:
        for given in decisions:
            counts[await _decide(tx, ctx, given, message_id)] += 1
    return Applied(counts["filed"], counts["ignored"], counts["held"], [])


async def bulk_file(ctx: AuthContext, attachment_ids: Sequence[UUID]) -> list[tuple[UUID, str]]:
    """INB-01 e: file as suggested only an unflagged file with one confident, unchanged
    candidate. Until the matcher proposes (N-01-T17), none has one. The person must hold
    `inbox.file` on every attachment's client; an unknown or walled one answers 404 for the whole
    request, naming nothing (INV-3; N-01-T20 found the route unauthorised)."""
    await _flagged(ctx)
    async with tenant_session(ctx.tenant) as session:
        owners = dict(
            (
                await session.execute(
                    text("SELECT id, client_id FROM inbox_attachments WHERE id = ANY(:ids)"),
                    {"ids": list(attachment_ids)},
                )
            ).all()
        )
    if set(owners) != set(attachment_ids):
        raise NotFound("inbox_attachment")
    clients = {c for c in owners.values() if c is not None}
    try:
        for client in clients:
            await authorise(ctx, FILE, Resource.client(ctx.tenant_id, client))
        if not clients:
            await authorise(ctx, FILE, Resource.firm(ctx.tenant_id))
    except Forbidden:
        raise NotFound("inbox_attachment") from None
    out: list[tuple[UUID, str]] = []
    async with tenant_session(ctx.tenant) as session:
        flagged = set(
            (
                await session.execute(
                    text(
                        "SELECT DISTINCT attachment_id FROM inbox_attachment_flags "
                        "WHERE attachment_id = ANY(:ids)"
                    ),
                    {"ids": list(attachment_ids)},
                )
            ).scalars()
        )
    for attachment in attachment_ids:
        out.append((attachment, "has_flags" if attachment in flagged else "low_confidence"))
    return out
