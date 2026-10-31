"""The firm Inbox's read models and its two thread actions (N-01-T13; N-01 §3.3, §4.3; DEC-75,
DEC-43, DEC-20; DEC-1059).

**Who sees a thread** (`intake_scope.py`'s rules, as list filters): a matched thread through
`visible_scope(inbox.read, client)`, which leaves walled clients out; an unmatched thread only for
the intake scope, by sender and subject. Counts are over those rows only, so a walled client is in
no count and nothing discloses it.

**Content** is a separate grant: a message body (sealed) shows only with `inbox.read_content` on
the client and is audited when read; an attachment's pages are its masked rendition only (C4,
AttachmentTriage); the original bytes and Download All need `inbox.download` and are audited. The
intake scope never reads a body or a file of an unmatched thread (DEC-75).

**Actions:** match a thread to a client (optionally remembering the sender: a rule on the
address's HMAC), which moves its New attachments to Waiting; ignore an unmatched thread with a
reason.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Final, cast
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    DateTime,
    Integer,
    Row,
    Text,
    and_,
    case,
    func,
    or_,
    select,
    text,
)
from sqlalchemy import column as col
from sqlalchemy import table as tbl
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import LargeBinary, Uuid

from abacus.kernel._flags import INBOX_FIRM_INTAKE
from abacus.kernel.clock import system_now
from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import (
    Position,
    capped_total,
    decode_cursor,
    keyset,
    page_of,
    query_hash,
    status_counts,
)
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.communications.events import InboxAttachmentMatchable
from abacus.modules.communications.intake_scope import intake_member, readable_thread
from abacus.modules.engagements.api import work_item_index
from abacus.modules.evidence.api import intake_masked_pages, read_staged
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    names_of,
    visible_scope,
    walled_from,
)
from abacus.modules.organisations.api import client_name_column, readable_client
from abacus.modules.platform.api import HomeCount

READ: Final = "inbox.read"
READ_CONTENT: Final = "inbox.read_content"
DOWNLOAD: Final = "inbox.download"
MATCH: Final = "inbox.match_sender"
TRIAGE: Final = "inbox.triage"
LIST_RESOURCE: Final = "inbox_threads"
# The roll-up dot: the most pressing attachment state wins.
_PRESSING: Final = ("new", "waiting", "held", "filed", "ignored", "withdrawn")
_ATTACHMENT_ACTIONS: Final = (TRIAGE, DOWNLOAD, READ_CONTENT, "inbox.file")

threads = tbl(
    "inbox_threads",
    col("id", Uuid()),
    col("source_kind", Text()),
    col("source_display", Text()),
    col("client_id", Uuid()),
    col("client_entity_id", Uuid()),
    col("subject_display", Text()),
    col("sender_display", Text()),
    col("match_method", Text()),
    col("ignored_reason", Text()),
    col("last_received_at", DateTime(timezone=True)),
)
messages = tbl(
    "inbound_messages",
    col("id", Uuid()),
    col("thread_id", Uuid()),
    col("channel", Text()),
    col("received_via", Text()),
    col("sender_display", Text()),
    col("sender_address_hmac", Text()),
    col("sender_contact_id", Uuid()),
    col("logged_by_user_id", Uuid()),
    col("subject_display", Text()),
    col("body_sealed", LargeBinary()),
    col("received_at", DateTime(timezone=True)),
)
attachments = tbl(
    "inbox_attachments",
    col("id", Uuid()),
    col("message_id", Uuid()),
    col("thread_id", Uuid()),
    col("client_id", Uuid()),
    col("file_name", Text()),
    col("media_type", Text()),
    col("size_bytes", Integer()),
    col("fingerprint", Text()),
    col("storage_key", Text()),
    col("storage_version_id", Text()),
    col("status", Text()),
    col("filed_destination_kind", Text()),
    col("filed_destination_id", Uuid()),
    col("created_at", DateTime(timezone=True)),
)
flags = tbl(
    "inbox_attachment_flags",
    col("attachment_id", Uuid()),
    col("kind", Text()),
    col("severity", Text()),
    col("ref_evidence_version_id", Uuid()),
    col("facts", JSONB()),
    col("run_no", Integer()),
)
T = threads.c
A = attachments.c
M = messages.c


class ThreadVersionChanged(DomainConflict):
    """Someone matched or ignored this thread since it was read: reload."""

    code = "thread_changed"


class ThreadAlreadyMatched(DomainConflict):
    """Only an unmatched thread can be ignored as a sender."""

    code = "thread_matched"


class NoSenderAddress(DomainInvalid):
    """The thread has no email sender to remember (portal or staff-logged)."""

    code = "no_sender_address"


async def _firm_and_flag(ctx: AuthContext) -> bool:
    """404 for a client principal or with the flag off; whether the caller is in the intake
    scope."""
    if ctx.client:
        raise NotFound("inbox")
    if not await flag_enabled(ctx.tenant, INBOX_FIRM_INTAKE):
        raise NotFound(INBOX_FIRM_INTAKE.name)
    return await intake_member(ctx)


async def visible_threads(ctx: AuthContext, in_scope: bool) -> ColumnElement[bool]:
    """Matched threads by client (walls excluded); unmatched ones for the intake scope only. The
    intake scope also reads matched threads of clients it is not walled from (DEC-819)."""
    matched = and_(T.client_id.is_not(None), visible_scope(ctx, READ, "client", T.client_id))
    if not in_scope:
        return matched
    walled = await walled_from(ctx.tenant, ctx.user_id)
    reachable = (
        and_(T.client_id.is_not(None), T.client_id.not_in(walled))
        if walled
        else (T.client_id.is_not(None))
    )
    return or_(T.client_id.is_(None), matched, reachable)


def _rollup() -> ColumnElement[str]:
    """The thread's dot: the most pressing state of its attachments."""
    rank = case(*((A.status == s, n) for n, s in enumerate(_PRESSING)), else_=len(_PRESSING))
    best = (
        select(func.min(rank))
        .select_from(attachments)
        .where(A.thread_id == T.id)
        .scalar_subquery()
    )
    return case(*((best == n, s) for n, s in enumerate(_PRESSING)), else_="new")


def _waiting() -> ColumnElement[int]:
    return (
        select(func.count())
        .select_from(attachments)
        .where(A.thread_id == T.id, A.status == "waiting")
        .scalar_subquery()
    )


def _messages() -> ColumnElement[int]:
    return select(func.count()).select_from(messages).where(M.thread_id == T.id).scalar_subquery()


# --- Summary -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Summary:
    waiting: int
    unmatched: int
    by_source: tuple[tuple[str, str | None, int], ...]


async def summary(ctx: AuthContext) -> Summary:
    """`GET /v1/inbox/summary`: waiting attachments and unmatched threads the viewer can see."""
    in_scope = await _firm_and_flag(ctx)
    seen = await visible_threads(ctx, in_scope)
    waiting = (
        select(T.source_kind, T.source_display, func.count(A.id))
        .select_from(threads.join(attachments, A.thread_id == T.id))
        .where(seen, A.status == "waiting")
        .group_by(T.source_kind, T.source_display)
    )
    unmatched = (
        select(func.count()).select_from(threads).where(seen, T.client_id.is_(None))
        if in_scope
        else None
    )
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(waiting)).all()
        n_unmatched = (
            int((await session.execute(unmatched)).scalar_one()) if unmatched is not None else 0
        )
    by_source = tuple((str(r[0]), r[1], int(r[2])) for r in rows)
    return Summary(sum(n for _k, _d, n in by_source), n_unmatched, by_source)


# --- Threads -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ThreadRow:
    id: UUID
    source_kind: str
    channel: str
    match_state: str
    client_id: UUID | None
    client_name: str | None
    subject_display: str
    sender_display: str
    last_received_at: datetime
    status: str
    waiting: int
    message_count: int


@dataclass(frozen=True)
class ThreadPage:
    rows: list[ThreadRow]
    next_position: Position | None
    total: tuple[int, bool]
    counts: dict[str, int]
    query: str


@dataclass(frozen=True)
class ThreadFilters:
    source: str | None = None
    client_id: UUID | None = None
    status: str | None = None
    received_since: date | None = None
    channel: str | None = None
    q: str | None = None
    show_ignored: bool = False
    show_filed: bool = True


def _escaped(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _first_channel() -> ColumnElement[str]:
    return (
        select(M.channel)
        .where(M.thread_id == T.id)
        .order_by(M.received_at, M.id)
        .limit(1)
        .scalar_subquery()
    )


def _match_state() -> ColumnElement[str]:
    return case(
        (T.ignored_reason.is_not(None), "ignored"),
        (T.client_id.is_(None), "unmatched"),
        else_="matched",
    )


async def list_threads(
    ctx: AuthContext, filters: ThreadFilters, cursor: str | None, limit: int
) -> ThreadPage:
    """`GET /v1/inbox/threads`: the INB-01 rail, newest first, under `visible_threads`."""
    in_scope = await _firm_and_flag(ctx)
    seen = await visible_threads(ctx, in_scope)
    query = query_hash(
        **{k: str(v) for k, v in filters.__dict__.items() if v is not None},
    )
    after = (
        None
        if cursor is None
        else decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=LIST_RESOURCE, query=query)
    )
    status = _rollup()
    where: list[ColumnElement[bool]] = [seen]
    if filters.source is not None:
        where.append(T.source_kind == filters.source)
    if filters.client_id is not None:
        where.append(T.client_id == filters.client_id)
    if filters.received_since is not None:
        since = datetime.combine(filters.received_since, time(0, 0), tzinfo=UTC)
        where.append(T.last_received_at >= since)
    if filters.channel is not None:
        where.append(_first_channel() == filters.channel)
    if not filters.show_ignored:
        where.append(T.ignored_reason.is_(None))
    if not filters.show_filed:
        where.append(status != "filed")
    if filters.q:
        pattern = _escaped(filters.q.strip())
        where.append(
            or_(
                T.subject_display.ilike(pattern, escape="\\"),
                T.sender_display.ilike(pattern, escape="\\"),
            )
        )
    base = select(T.id).select_from(threads).where(*where)
    narrowed = base.where(status == filters.status) if filters.status is not None else base
    stmt = keyset(
        narrowed.add_columns(T.last_received_at.label("sort_key")),
        sort=cast(ColumnElement[object], T.last_received_at),
        id_column=cast(ColumnElement[object], T.id),
        after=after,
        descending=True,
        limit=limit,
    )
    async with tenant_session(ctx.tenant) as session:
        fetched = (await session.execute(stmt)).all()
        page, last = page_of(fetched, limit=limit, key=lambda r: r.sort_key, id_of=lambda r: r.id)
        total = await capped_total(session, narrowed)
        counts = await status_counts(session, base, status)
        rows = await _thread_rows(session, [r.id for r in page])
    return ThreadPage(rows, last, total, counts, query)


async def _thread_rows(session: AsyncSession, ids: list[UUID]) -> list[ThreadRow]:
    if not ids:
        return []
    found = (
        await session.execute(
            select(
                T.id,
                T.source_kind,
                _first_channel().label("channel"),
                _match_state().label("match_state"),
                T.client_id,
                case((T.client_id.is_(None), None), else_=client_name_column(T.client_id)).label(
                    "client_name"
                ),
                T.subject_display,
                T.sender_display,
                T.last_received_at,
                _rollup().label("status"),
                _waiting().label("waiting"),
                _messages().label("message_count"),
            )
            .select_from(threads)
            .where(T.id.in_(ids))
        )
    ).all()
    by_id = {r.id: ThreadRow(*r) for r in found}
    return [by_id[i] for i in ids if i in by_id]


# --- Thread detail -------------------------------------------------------------------------------


@dataclass(frozen=True)
class FlagView:
    kind: str
    severity: str
    ref_evidence_version_id: UUID | None
    facts: dict[str, str | int | bool]


@dataclass(frozen=True)
class AttachmentView:
    id: UUID
    file_name: str
    media_type: str
    size_bytes: int
    fingerprint: str
    status: str
    flags: list[FlagView]
    filed_kind: str | None
    filed_id: UUID | None
    allowed_actions: list[str]


@dataclass(frozen=True)
class MessageView:
    id: UUID
    channel: str
    received_via: str | None
    sender_display: str
    logged_by_name: str | None
    subject_display: str
    received_at: datetime
    body: str | None
    attachments: list[AttachmentView]


@dataclass(frozen=True)
class ThreadDetail:
    thread: ThreadRow
    match_method: str
    messages: list[MessageView]
    allowed_actions: list[str]
    version: int


async def _client_resource(ctx: AuthContext, client_id: UUID | None) -> Resource:
    return (
        Resource.firm(ctx.tenant_id)
        if client_id is None
        else Resource.client(ctx.tenant_id, client_id)
    )


async def _may(
    ctx: AuthContext, client_id: UUID | None, actions: tuple[str, ...]
) -> frozenset[str]:
    """What the person may do here. On an unmatched thread the intake scope sees sender and
    subject only: no content, no download (DEC-75)."""
    if client_id is None:
        return frozenset(a for a in actions if a in (MATCH, TRIAGE))
    return await allowed_actions(ctx, await _client_resource(ctx, client_id), actions)


def _version(client_id: UUID | None, ignored_reason: str | None) -> int:
    """The thread's optimistic version: its match state, as a stable integer."""
    basis = f"{client_id}|{ignored_reason}"
    return int(hashlib.sha256(basis.encode()).hexdigest()[:8], 16)


async def thread_detail(ctx: AuthContext, thread_id: UUID) -> ThreadDetail:
    """`GET /v1/inbox/threads/{id}`: messages newest first; a body only with
    `inbox.read_content` (each one read is audited)."""
    await _firm_and_flag(ctx)
    header = await readable_thread(ctx, thread_id)
    may = await _may(ctx, header.client_id, (READ_CONTENT, DOWNLOAD, MATCH, TRIAGE, "inbox.file"))
    async with tenant_session(ctx.tenant) as session:
        head = (
            await session.execute(
                select(T.match_method, T.client_id, T.ignored_reason).where(T.id == thread_id)
            )
        ).one()
        rows = await _thread_rows(session, [thread_id])
        msgs = (
            await session.execute(
                select(messages)
                .where(M.thread_id == thread_id)
                .order_by(M.received_at.desc(), M.id)
            )
        ).all()
        files = (
            await session.execute(
                select(attachments)
                .where(A.thread_id == thread_id, A.status != "withdrawn")
                .order_by(A.created_at, A.id)
            )
        ).all()
        latest = (
            select(flags.c.attachment_id, func.max(flags.c.run_no).label("run_no"))
            .group_by(flags.c.attachment_id)
            .subquery()
        )
        raised = list(
            (
                await session.execute(
                    select(flags)
                    .join(
                        latest,
                        and_(
                            latest.c.attachment_id == flags.c.attachment_id,
                            latest.c.run_no == flags.c.run_no,
                        ),
                    )
                    .where(flags.c.attachment_id.in_([f.id for f in files]))
                )
            ).all()
            if files
            else []
        )
    names = await names_of([m.logged_by_user_id for m in msgs if m.logged_by_user_id])
    read_bodies = READ_CONTENT in may
    bodies: dict[UUID, str] = {}
    if read_bodies:
        for m in msgs:
            if m.body_sealed is not None:
                sealed = cast(bytes, m.body_sealed)
                bodies[m.id] = (
                    await open_sealed(ctx.tenant_id, sealed, f"inbound_message:{m.id}")
                ).decode()
        if bodies:
            async with uow(ctx.tenant) as tx:
                tx.record(
                    "inbound_message.body_read",
                    target=Target("inbox_thread", thread_id),
                    after=Ref(messages=len(bodies)),
                )
    attachment_may = [a for a in _ATTACHMENT_ACTIONS if a in may]
    by_message: dict[UUID, list[AttachmentView]] = {}
    for f in files:
        by_message.setdefault(f.message_id, []).append(
            AttachmentView(
                id=f.id,
                file_name=f.file_name,
                media_type=f.media_type,
                size_bytes=int(f.size_bytes),
                fingerprint=f.fingerprint,
                status=f.status,
                flags=[
                    FlagView(r.kind, r.severity, r.ref_evidence_version_id, _facts(r.facts))
                    for r in raised
                    if r.attachment_id == f.id
                ],
                filed_kind=f.filed_destination_kind,
                filed_id=f.filed_destination_id,
                allowed_actions=attachment_may
                if f.status in ("new", "waiting", "held")
                else [a for a in attachment_may if a in (DOWNLOAD, READ_CONTENT)],
            )
        )
    return ThreadDetail(
        thread=rows[0],
        match_method=head.match_method,
        messages=[
            MessageView(
                id=m.id,
                channel=m.channel,
                received_via=m.received_via,
                sender_display=m.sender_display,
                logged_by_name=names.get(m.logged_by_user_id) if m.logged_by_user_id else None,
                subject_display=m.subject_display,
                received_at=m.received_at,
                body=bodies.get(m.id),
                attachments=by_message.get(m.id, []),
            )
            for m in msgs
        ],
        allowed_actions=sorted(a for a in may if a in (MATCH, TRIAGE, "inbox.file", DOWNLOAD)),
        version=_version(head.client_id, head.ignored_reason),
    )


def _facts(raw: object) -> dict[str, str | int | bool]:
    if isinstance(raw, dict):
        return {
            str(k): v
            for k, v in cast(dict[object, object], raw).items()
            if isinstance(v, (str, int, bool))
        }
    return {}


# --- Attachments: the masked viewer, the original, Download All ----------------------------------


@dataclass(frozen=True)
class _File:
    id: UUID
    thread_id: UUID
    message_id: UUID
    client_id: UUID | None
    file_name: str
    media_type: str
    size_bytes: int
    fingerprint: str
    storage_key: str
    storage_version_id: str | None


async def _readable_file(ctx: AuthContext, attachment_id: UUID, action: str) -> _File:
    """The attachment, when its thread is readable, it is matched (the intake scope never
    reads an unmatched file, DEC-75) and the person holds `action` on its client."""
    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                select(
                    A.id,
                    A.thread_id,
                    A.message_id,
                    A.client_id,
                    A.file_name,
                    A.media_type,
                    A.size_bytes,
                    A.fingerprint,
                    A.storage_key,
                    A.storage_version_id,
                ).where(A.id == attachment_id, A.status != "withdrawn")
            )
        ).one_or_none()
    if row is None:
        raise NotFound("inbox_attachment")
    header = await readable_thread(ctx, row.thread_id)
    if header.client_id is None:
        raise NotFound("inbox_attachment")
    await authorise(ctx, action, Resource.client(ctx.tenant_id, header.client_id))
    return _File(*row)


@dataclass(frozen=True)
class Manifest:
    attachment_id: UUID
    page_count: int
    masked: bool
    page_refs: list[str]


async def viewer_manifest(ctx: AuthContext, attachment_id: UUID) -> Manifest:
    """`GET /v1/inbox/attachments/{id}/viewer`: the masked rendition's pages, never an unmasked
    one (none until AttachmentTriage made it); audited."""
    await _firm_and_flag(ctx)
    found = await _readable_file(ctx, attachment_id, READ_CONTENT)
    pages = await intake_masked_pages(ctx.tenant, found.id)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "inbox_attachment.viewed",
            target=Target("inbox_attachment", found.id),
            after=Ref(pages=pages or 0),
        )
    n = pages or 0
    return Manifest(
        found.id,
        n,
        pages is not None,
        [f"inbox-attachment:{found.id}:page:{p}" for p in range(1, n + 1)],
    )


@dataclass(frozen=True)
class Download:
    file_name: str
    media_type: str
    body: bytes


async def _bytes(ctx: AuthContext, f: _File) -> bytes:
    return await read_staged(
        ctx.tenant_id, f.storage_key, f.storage_version_id or "", f.fingerprint, f.size_bytes
    )


async def attachment_content(ctx: AuthContext, attachment_id: UUID) -> Download:
    """`GET /v1/inbox/attachments/{id}/content`: the original, audited."""
    await _firm_and_flag(ctx)
    found = await _readable_file(ctx, attachment_id, DOWNLOAD)
    body = await _bytes(ctx, found)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "inbox_attachment.downloaded",
            target=Target("inbox_attachment", found.id),
            after=Ref(sha256=found.fingerprint),
        )
    return Download(found.file_name, found.media_type, body)


async def message_zip(ctx: AuthContext, message_id: UUID) -> Download:
    """`GET /v1/inbox/messages/{id}/download`: every file of the message, one zip, audited."""
    await _firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        ids = (
            (
                await session.execute(
                    select(A.id)
                    .where(A.message_id == message_id, A.status != "withdrawn")
                    .order_by(A.created_at, A.id)
                )
            )
            .scalars()
            .all()
        )
    if not ids:
        raise NotFound("inbound_message")
    files = [await _readable_file(ctx, i, DOWNLOAD) for i in ids]
    buffer = io.BytesIO()
    used: set[str] = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for f in files:
            name = f.file_name
            if name in used:
                name = f"{f.id.hex[:8]}-{name}"
            used.add(name)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, await _bytes(ctx, f))
    zipped = buffer.getvalue()
    async with uow(ctx.tenant) as tx:
        tx.record(
            "inbound_message.downloaded",
            target=Target("inbox_thread", files[0].thread_id),
            after=Ref(files=len(files), sha256=hashlib.sha256(zipped).hexdigest()),
        )
    return Download("documents.zip", "application/zip", zipped)


# --- Actions -------------------------------------------------------------------------------------


async def match_client(
    ctx: AuthContext,
    thread_id: UUID,
    *,
    client_id: UUID,
    client_entity_id: UUID | None,
    remember_sender: bool,
    seen_version: int,
) -> None:
    """INB-01 b: a person matches the thread to a client; its New attachments become Waiting;
    with "Remember this sender", a rule on the sender address's HMAC (DEC-75)."""
    await _firm_and_flag(ctx)
    await readable_thread(ctx, thread_id)
    await readable_client(ctx, client_id)  # walled or unknown: 404
    await authorise(ctx, MATCH, Resource.client(ctx.tenant_id, client_id))
    now = system_now()
    async with uow(ctx.tenant) as tx:
        head = (
            await tx.session.execute(
                select(T.client_id, T.ignored_reason).where(T.id == thread_id).with_for_update()
            )
        ).one()
        if _version(head.client_id, head.ignored_reason) != seen_version:
            raise ThreadVersionChanged
        await tx.session.execute(
            text(
                "UPDATE inbox_threads SET client_id = :client, client_entity_id = :entity, "
                "match_method = 'staff_selected', matched_by = :user, matched_at = :now, "
                "ignored_reason = NULL WHERE id = :id"
            ),
            {
                "client": client_id,
                "entity": client_entity_id,
                "user": ctx.user_id,
                "now": now,
                "id": thread_id,
            },
        )
        matched = (
            await tx.session.execute(
                text(
                    "UPDATE inbox_attachments SET client_id = :client, status = CASE "
                    "WHEN status = 'new' THEN 'waiting' ELSE status END WHERE thread_id = :id "
                    "AND status IN ('new', 'waiting', 'ignored') "
                    "RETURNING id, classification_id"
                ),
                {"client": client_id, "id": thread_id},
            )
        ).all()
        # N-01-T22: the classified ones may now be matched to this client's destinations (one
        # not yet classified emits when AttachmentTriage classifies it).
        for attachment in matched:
            if attachment.classification_id is not None:
                tx.emit(InboxAttachmentMatchable(attachment_id=attachment.id, client_id=client_id))
        tx.record(
            "inbox_thread.client_matched",
            target=Target("inbox_thread", thread_id),
            after=Ref(client_id=client_id),
        )
        if remember_sender:
            address = (
                await tx.session.execute(
                    select(M.sender_address_hmac)
                    .where(M.thread_id == thread_id, M.sender_address_hmac.is_not(None))
                    .order_by(M.received_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if address is None:
                raise NoSenderAddress
            await tx.session.execute(
                text(
                    "UPDATE inbox_sender_rules SET revoked_at = :now "
                    "WHERE address_hmac = :address AND revoked_at IS NULL"
                ),
                {"now": now, "address": address},
            )
            rule = (
                await tx.session.execute(
                    text(
                        "INSERT INTO inbox_sender_rules (tenant_id, address_hmac, client_id, "
                        "created_by) VALUES (:tenant, :address, :client, :user) RETURNING id"
                    ),
                    {
                        "tenant": ctx.tenant_id,
                        "address": address,
                        "client": client_id,
                        "user": ctx.user_id,
                    },
                )
            ).scalar_one()
            tx.record(
                "inbox_sender_rule.created",
                target=Target("inbox_sender_rule", rule),
                after=Ref(client_id=client_id),
            )


async def ignore_thread(ctx: AuthContext, thread_id: UUID, reason_code: str) -> None:
    """An unmatched sender's thread, ignored with a reason; its New files become Ignored."""
    in_scope = await _firm_and_flag(ctx)
    header = await readable_thread(ctx, thread_id)
    if header.client_id is not None:
        raise ThreadAlreadyMatched
    if not in_scope:
        raise NotFound("inbox_thread")
    await authorise(ctx, TRIAGE, Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE inbox_threads SET ignored_reason = :reason "
                "WHERE id = :id AND client_id IS NULL"
            ),
            {"reason": reason_code, "id": thread_id},
        )
        await tx.session.execute(
            text(
                "UPDATE inbox_attachments SET status = 'ignored' "
                "WHERE thread_id = :id AND status = 'new'"
            ),
            {"id": thread_id},
        )
        tx.record("inbox_thread.ignored", target=Target("inbox_thread", thread_id))


# --- For other modules ---------------------------------------------------------------------------


async def waiting_for_work_item(tenant: TenantContext, work_item_id: UUID) -> int:
    """T-02: attachments waiting on the work item's client (a count; the caller authorised the
    work item)."""
    items = work_item_index()
    async with tenant_session(tenant) as session:
        client = (
            await session.execute(select(items.c.client_id).where(items.c.id == work_item_id))
        ).scalar_one_or_none()
        if client is None:
            return 0
        return int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(attachments)
                    .where(A.client_id == client, A.status == "waiting")
                )
            ).scalar_one()
        )


@dataclass(frozen=True)
class WaitingAttachment:
    """T-02-T18 (TAX-03's dock): one attachment waiting on a client, with its latest code flags
    and the message it came with. The caller authorised a work item of this client."""

    id: UUID
    thread_id: UUID
    file_name: str
    media_type: str
    size_bytes: int
    channel: str
    sender_display: str
    subject_display: str
    received_at: datetime
    flags: tuple[FlagView, ...]
    message_id: UUID


_WAITING = text(
    "SELECT a.id, a.thread_id, a.file_name, a.media_type, a.size_bytes, m.channel, "
    "m.sender_display, m.subject_display, m.received_at, a.message_id FROM inbox_attachments a "
    "JOIN inbound_messages m ON m.id = a.message_id "
    "WHERE a.client_id = :client AND a.status = 'waiting' "
    "ORDER BY m.received_at, a.created_at, a.id"
)
_LATEST_FLAGS = text(
    "SELECT f.attachment_id, f.kind, f.severity, f.ref_evidence_version_id, f.facts "
    "FROM inbox_attachment_flags f WHERE f.attachment_id = ANY(:ids) AND f.run_no = ("
    "SELECT max(g.run_no) FROM inbox_attachment_flags g WHERE g.attachment_id = f.attachment_id)"
)


async def waiting_for_client(tenant: TenantContext, client_id: UUID) -> list[WaitingAttachment]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_WAITING, {"client": client_id})).all()
        raised: Sequence[Row[Any]] = (  # Any: the flag columns, typed by the table
            (await session.execute(_LATEST_FLAGS, {"ids": [r.id for r in rows]})).all()
            if rows
            else []
        )
    return [
        WaitingAttachment(
            r.id,
            r.thread_id,
            r.file_name,
            r.media_type,
            int(r.size_bytes),
            r.channel,
            r.sender_display,
            r.subject_display,
            r.received_at,
            tuple(
                FlagView(f.kind, f.severity, f.ref_evidence_version_id, _facts(f.facts))
                for f in raised
                if f.attachment_id == r.id
            ),
            r.message_id,
        )
        for r in rows
    ]


async def inbox_waiting(viewer: object, office_id: UUID | None) -> HomeCount:
    """HOME-01's `inbox_waiting` pill: the summary's waiting count (I-01). Offices do not
    narrow intake: an unfiled attachment belongs to no office yet."""
    made = await summary(cast(AuthContext, viewer))
    return HomeCount(total=made.waiting, target_filter="status=waiting")
