"""SIG-01's read models and the drawer's actions (N-02-T13; N-02 §3.2, §3.3; SPEC-381 AC-4-AC-6;
DEC-20, DEC-33, DEC-43).

- **Who sees a row.** An envelope on an engagement is visible through `visible(envelope.read)` on
  that engagement; one on the client alone (a consent, a 2848) through
  `visible_scope(..., "client")` (DEC-33). Both leave walled clients out, so a walled row is in
  no list, no count and no tile (DEC-43). `client_service` reads envelopes firm-wide without
  opening other filed evidence (DEC-20): its `envelope.read` cell is `allow`.
- **Tabs.** To send = drafts; Out for signature = sent, viewed, partially signed and declined
  (a decline is shown in place until the firm voids or resends); Completed = completed in the
  last 30 days; Expired = expired. A voided envelope sits in no tab.
- **Counts.** The summary counts each tab, the Out tab's envelopes by type and those needing a
  handwritten signature; the Out list's `counts` carry its tiles (sent, viewed,
  partially_signed, due within 7 days) over the list's filters, so the tiles foot.
- **The drawer.** One envelope with its documents, signers, fields, masked evidence and the
  actions the person may take (`allowed_actions`, by status and the matrix).
- **Reveal.** `signer.reveal_ip` with a reason and a fresh second factor, onshore (the matrix's
  modifiers); the full address for 10 seconds, `no-store`, audited `signer.ip_revealed`.
- **Evidence package.** `envelope.evidence_download`: a zip of one JSON per signer, each stored
  package and document, and `manifest.sha256`; fixed entry times and order, so a second download
  is byte-identical. Audited `evidence.downloaded`.
- **Void.** `envelope.void` with a reason on an open envelope (draft, sent, viewed, partially
  signed): the envelope is voided by the person, issued signing sessions are abandoned, the
  evidence collected so far stays (insert-only, 0292). The provider-side void is W7's
  (N-02-T18); a record-mode envelope is completed and never open.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Date,
    DateTime,
    Integer,
    SmallInteger,
    String,
    Text,
    and_,
    case,
    func,
    literal,
    or_,
    select,
    text,
)
from sqlalchemy import column as col
from sqlalchemy import table as tbl
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import Uuid

from abacus.kernel._flags import SIGNATURES_ENVELOPES
from abacus.kernel.clock import system_now, today
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
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
from abacus.modules.engagements.api import get_ref, work_item_index
from abacus.modules.evidence.api import get_record, version_titles
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    allowed_actions,
    authorise,
    contact_emails,
    names_of,
    visible,
    visible_scope,
)
from abacus.modules.organisations.api import (
    SignerContact,
    client_name_column,
    contact_facts,
    signer_contacts,
)
from abacus.modules.signatures.imports import RECORD_TYPE
from abacus.modules.signatures.sources import UnknownEnvelopeSource, envelope_source

READ: Final = "envelope.read"
VOID: Final = "envelope.void"
REVEAL: Final = "signer.reveal_ip"
DOWNLOAD: Final = "envelope.evidence_download"
REVEAL_SECONDS: Final = 10
COMPLETED_DAYS: Final = 30
DUE_DAYS: Final = 7
LIST_RESOURCE: Final = "envelopes"

Tab = Literal["to_send", "out", "completed", "expired"]
TAB_STATUSES: Final[dict[str, tuple[str, ...]]] = {
    "to_send": ("draft",),
    "out": ("sent", "viewed", "partially_signed", "declined"),
    "completed": ("completed",),
    "expired": ("expired",),
}
OPEN: Final = frozenset({"draft", "sent", "viewed", "partially_signed"})
# What a row may offer, by status; `allowed_actions` keeps those the person holds.
_CANDIDATES: Final[dict[str, tuple[str, ...]]] = {
    "draft": ("envelope.draft", "envelope.send", VOID),
    "sent": ("envelope.remind", VOID),
    "viewed": ("envelope.remind", VOID),
    "partially_signed": ("envelope.remind", VOID, DOWNLOAD),
    "completed": (DOWNLOAD,),
    "declined": ("envelope.draft", DOWNLOAD),
    "expired": ("envelope.draft",),
    "voided": ("envelope.draft",),
}
# SIG-01's By type tile: e-file authorizations, letters, rep letters, §7216 consents, the rest.
BY_TYPE: Final = ("efile", "engagement_letter", "rep_letter", "consent_7216")
# Fixed zip entry times (the DOS epoch), so the same evidence zips to the same bytes.
_ZIP_TIME: Final = (1980, 1, 1, 0, 0, 0)

envelopes = tbl(
    "envelopes",
    col("id", Uuid()),
    col("number", Integer()),
    col("purpose", Text()),
    col("form_code", Text()),
    col("policy_family", Text()),
    col("source_kind", Text()),
    col("source_id", Uuid()),
    col("client_id", Uuid()),
    col("engagement_id", Uuid()),
    col("work_item_id", Uuid()),
    col("title", Text()),
    col("provider", Text()),
    col("provider_envelope_id", Text()),
    col("status", String()),
    col("signer_order", Text()),
    col("date_as_of_mode", Text()),
    col("date_as_of", Date()),
    col("due_on", Date()),
    col("expires_at", DateTime(timezone=True)),
    col("message", Text()),
    col("reminder_cadence", Text()),
    col("drafted_by_kind", Text()),
    col("drafted_by", Uuid()),
    col("sent_by", Uuid()),
    col("sent_at", DateTime(timezone=True)),
    col("void_reason", Text()),
    col("completed_at", DateTime(timezone=True)),
    col("superseded_at", DateTime(timezone=True)),
    col("version", Integer()),
)
signers = tbl(
    "envelope_signers",
    col("id", Uuid()),
    col("envelope_id", Uuid()),
    col("order", SmallInteger()),
    col("routing_group", SmallInteger()),
    col("contact_id", Uuid()),
    col("user_id", Uuid()),
    col("role", Text()),
    col("identity_method", Text()),
    col("status", Text()),
    col("kba_failures", SmallInteger()),
    col("viewed_at", DateTime(timezone=True)),
    col("signed_at", DateTime(timezone=True)),
    col("signature_method", Text()),
    col("decline_reason", Text()),
    col("provider_recipient_id", Text()),
)
documents = tbl(
    "envelope_documents",
    col("id", Uuid()),
    col("envelope_id", Uuid()),
    col("order", SmallInteger()),
    col("evidence_version_id", Uuid()),
    col("sha256", Text()),
    col("page_count", SmallInteger()),
    col("read_only", String()),
    col("tri", String()),
)
fields = tbl(
    "envelope_fields",
    col("id", Uuid()),
    col("envelope_document_id", Uuid()),
    col("signer_id", Uuid()),
    col("kind", Text()),
    col("page", SmallInteger()),
    col("x", String()),
    col("y", String()),
    col("w", String()),
    col("h", String()),
    col("anchor", Text()),
)
evidence = tbl(
    "signature_evidence",
    col("signer_id", Uuid()),
    col("envelope_id", Uuid()),
    col("signed_at", DateTime(timezone=True)),
    col("ip_sealed", BYTEA()),
    col("ip_masked", Text()),
    col("identity_result", Text()),
    col("signature_method", Text()),
    col("user_agent_family", Text()),
    col("device_label", Text()),
    col("document_sha256s", ARRAY(Text())),
    col("package_sha256", Text()),
)
E = envelopes.c
S = signers.c


class EnvelopeNotOpen(DomainConflict):
    """Only a draft or an envelope out for signature can be voided; a completed, declined,
    expired or voided one stays as it is."""

    code = "envelope_not_open"


class IpUnavailable(DomainConflict):
    """No sealed address was recorded for this signer (a record-mode import keeps none)."""

    code = "ip_unavailable"


# --- Rows ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Chip:
    name: str
    signed: bool


@dataclass(frozen=True)
class EnvelopeRow:
    id: UUID
    number: int
    purpose: str
    form_code: str | None
    title: str
    client_id: UUID
    client_name: str
    engagement_id: UUID | None
    work_item_id: UUID | None
    work_item_label: str | None
    provider: str
    status: str
    signed: int
    total: int
    sent_by_name: str | None
    sent_at: datetime | None
    viewed_at: datetime | None
    due_on: date | None
    needs_handwritten: bool
    allowed_actions: tuple[str, ...]
    signer_chips: tuple[Chip, ...]
    drafted_by_name: str | None
    outcome: str | None


@dataclass(frozen=True)
class Page:
    rows: list[EnvelopeRow]
    next_position: Position | None
    total: tuple[int, bool]
    counts: dict[str, int]
    query: str


@dataclass(frozen=True)
class Summary:
    to_send: int
    out: int
    completed: int
    expired: int
    needs_handwritten: int
    by_type: tuple[tuple[str, int], ...]


async def firm_and_flag(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("envelopes")
    if not await flag_enabled(ctx.tenant, SIGNATURES_ENVELOPES):
        raise NotFound(SIGNATURES_ENVELOPES.name)


def visible_envelopes(ctx: AuthContext) -> ColumnElement[bool]:
    """The rows `ctx` may read: by engagement, or by client when there is none (DEC-33)."""
    return or_(
        and_(E.engagement_id.is_not(None), visible(ctx, READ, E.engagement_id)),
        and_(E.engagement_id.is_(None), visible_scope(ctx, READ, "client", E.client_id)),
    )


def _completed_since(now: datetime) -> ColumnElement[bool]:
    return E.completed_at >= now - timedelta(days=COMPLETED_DAYS)


def _in_tab(tab: str, now: datetime) -> ColumnElement[bool]:
    clause = E.status.in_(TAB_STATUSES[tab])
    return and_(clause, _completed_since(now)) if tab == "completed" else clause


def _escaped(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _locked() -> ColumnElement[bool]:
    """A signer whose identity check locked (DF-11): the envelope needs a handwritten 8879."""
    return (
        select(literal(True))
        .select_from(signers)
        .where(S.envelope_id == E.id, S.status == "verification_failed")
        .exists()
    )


def _due_soon(day: date) -> ColumnElement[bool]:
    return and_(E.due_on >= day, E.due_on <= day + timedelta(days=DUE_DAYS))


def _filtered(
    ctx: AuthContext,
    *,
    tab: str | None,
    purpose: str | None,
    client_id: UUID | None,
    q: str | None,
    now: datetime,
) -> list[ColumnElement[bool]]:
    where: list[ColumnElement[bool]] = [visible_envelopes(ctx)]
    if tab is not None:
        where.append(_in_tab(tab, now))
    if purpose is not None:
        where.append(E.purpose == purpose)
    if client_id is not None:
        where.append(E.client_id == client_id)
    if q:
        pattern = _escaped(q.strip())
        where.append(
            or_(
                E.title.ilike(pattern, escape="\\"),
                client_name_column(E.client_id).ilike(pattern, escape="\\"),
                func.concat("E", E.number).ilike(pattern, escape="\\"),
            )
        )
    return where


def _sort(tab: str | None) -> tuple[ColumnElement[object], bool]:
    """Out for signature in due order (no due date last); the other tabs newest first."""
    if tab == "out":
        due = func.coalesce(E.due_on, literal(date(9999, 12, 31), type_=Date()))
        return cast(ColumnElement[object], due), False
    return cast(ColumnElement[object], E.number), True


async def list_envelopes(
    ctx: AuthContext,
    *,
    tab: str | None,
    purpose: str | None,
    status: str | None,
    client_id: UUID | None,
    q: str | None,
    cursor: str | None,
    limit: int,
) -> Page:
    """`GET /v1/envelopes` (SIG-01)."""
    await firm_and_flag(ctx)
    now = system_now()
    day = await today(ctx.tenant)
    query = query_hash(
        tab=tab, purpose=purpose, status=status, client_id=str(client_id), q=q or ""
    )
    after = (
        None
        if cursor is None
        else decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=LIST_RESOURCE, query=query)
    )
    where = _filtered(ctx, tab=tab, purpose=purpose, client_id=client_id, q=q, now=now)
    without_status = select(E.id).select_from(envelopes).where(*where)
    narrowed = without_status.where(E.status == status) if status is not None else without_status
    sort, descending = _sort(tab)
    page_stmt = keyset(
        narrowed.add_columns(sort.label("sort_key")),
        sort=sort,
        id_column=cast(ColumnElement[object], E.id),
        after=after,
        descending=descending,
        limit=limit,
    )
    async with tenant_session(ctx.tenant) as session:
        fetched = (await session.execute(page_stmt)).all()
        ids, last = page_of(fetched, limit=limit, key=lambda r: r.sort_key, id_of=lambda r: r.id)
        total = await capped_total(session, narrowed)
        counts = await status_counts(session, without_status, E.status)
        if tab == "out":
            due = select(func.count()).select_from(envelopes).where(*where, _due_soon(day))
            counts["due"] = int((await session.execute(due)).scalar_one())
        rows = await _rows(ctx, session, [r.id for r in ids])
    return Page(rows, last, total, counts, query)


async def summary(ctx: AuthContext) -> Summary:
    """`GET /v1/envelopes/summary`: every count over visible rows only (DEC-43)."""
    await firm_and_flag(ctx)
    now = system_now()
    seen = visible_envelopes(ctx)
    out = E.status.in_(TAB_STATUSES["out"])
    kind = case(
        (E.purpose.like("form_8879%"), "efile"),
        (E.purpose.in_(BY_TYPE), E.purpose),
        else_="other",
    )
    stmt = select(
        func.count().filter(_in_tab("to_send", now)),
        func.count().filter(out),
        func.count().filter(_in_tab("completed", now)),
        func.count().filter(_in_tab("expired", now)),
        func.count().filter(out, _locked()),
    ).where(seen)
    by_kind = (
        select(kind.label("kind"), func.count())
        .select_from(envelopes)
        .where(seen, out)
        .group_by(kind)
    )
    async with tenant_session(ctx.tenant) as session:
        to_send, n_out, completed, expired, handwritten = (
            await session.execute(stmt.select_from(envelopes))
        ).one()
        found = {str(k): int(n) for k, n in (await session.execute(by_kind)).tuples()}
    by_type = [(k, found.get(k, 0)) for k in BY_TYPE]
    if found.get("other"):
        by_type.append(("other", found["other"]))
    return Summary(
        int(to_send), int(n_out), int(completed), int(expired), int(handwritten), tuple(by_type)
    )


async def _names(
    session: AsyncSession, contacts: list[UUID], users: list[UUID]
) -> tuple[dict[UUID, str], dict[UUID, str]]:
    found = await contact_facts(session, contacts)
    return {k: v.display_name for k, v in found.items()}, await names_of(users)


def _resource(ctx: AuthContext, refs: dict[UUID, Resource], row: EnvelopeRow | _Head) -> Resource:
    if row.engagement_id is not None:
        return refs[row.engagement_id]
    return Resource.client(ctx.tenant_id, row.client_id)


@dataclass(frozen=True)
class _Head:
    id: UUID
    status: str
    client_id: UUID
    engagement_id: UUID | None


async def _actions(ctx: AuthContext, heads: Sequence[_Head]) -> dict[UUID, tuple[str, ...]]:
    """Per row, the status's candidate actions the person holds on its engagement or client;
    one probe per distinct resource and status."""
    refs: dict[UUID, Resource] = {}
    for engagement in {h.engagement_id for h in heads if h.engagement_id is not None}:
        refs[engagement] = (await get_ref(ctx, engagement)).resource()
    probed: dict[tuple[UUID, str], frozenset[str]] = {}
    out: dict[UUID, tuple[str, ...]] = {}
    for head in heads:
        key = (head.engagement_id or head.client_id, head.status)
        if key not in probed:
            candidates = _CANDIDATES.get(head.status, ())
            probed[key] = await allowed_actions(ctx, _resource(ctx, refs, head), candidates)
        out[head.id] = tuple(a for a in _CANDIDATES.get(head.status, ()) if a in probed[key])
    return out


def _outcome(source_kind: str | None, status: str) -> str | None:
    """What a completed envelope unblocked, in its source's words (N-02 never computes filing
    states); a source not registered here reads "Completed"."""
    if status != "completed":
        return None
    if source_kind is None:
        return "Completed"
    try:
        return envelope_source(source_kind).completed_label
    except UnknownEnvelopeSource:
        return "Completed"


async def _rows(ctx: AuthContext, session: AsyncSession, ids: list[UUID]) -> list[EnvelopeRow]:
    """The rows for `ids`, in that order; the caller already filtered them by `visible()`."""
    if not ids:
        return []
    items = work_item_index()
    heads = (
        await session.execute(
            select(
                E.id,
                E.number,
                E.purpose,
                E.form_code,
                E.title,
                E.client_id,
                client_name_column(E.client_id).label("client_name"),
                E.engagement_id,
                E.work_item_id,
                items.c.name.label("work_item_label"),
                E.provider,
                E.status,
                E.sent_by,
                E.sent_at,
                E.due_on,
                E.drafted_by_kind,
                E.drafted_by,
                E.source_kind,
            )
            .select_from(envelopes)
            .outerjoin(items, items.c.id == E.work_item_id)
            .where(E.id.in_(ids))
        )
    ).all()
    people = (
        await session.execute(
            select(S.envelope_id, S.contact_id, S.user_id, S.status, S.viewed_at, S.order)
            .where(S.envelope_id.in_(ids))
            .order_by(S.envelope_id, S.order)
        )
    ).all()
    contact_names, user_names = await _names(
        session,
        [p.contact_id for p in people if p.contact_id is not None],
        list(
            {p.user_id for p in people if p.user_id is not None}
            | {h.sent_by for h in heads if h.sent_by is not None}
            | {h.drafted_by for h in heads if h.drafted_by is not None}
        ),
    )
    by_envelope: dict[UUID, list[Any]] = {}  # Any: SQLAlchemy rows of the signer select
    for p in people:
        by_envelope.setdefault(p.envelope_id, []).append(p)
    actions = await _actions(
        ctx, [_Head(h.id, h.status, h.client_id, h.engagement_id) for h in heads]
    )
    built: dict[UUID, EnvelopeRow] = {}
    for h in heads:
        mine = by_envelope.get(h.id, [])
        chips = tuple(
            Chip(
                _first_name(
                    contact_names.get(p.contact_id)
                    if p.contact_id is not None
                    else user_names.get(p.user_id)
                    if p.user_id is not None
                    else None
                ),
                p.status == "signed",
            )
            for p in mine
        )
        viewed = [p.viewed_at for p in mine if p.viewed_at is not None]
        drafted = user_names.get(h.drafted_by) if h.drafted_by is not None else None
        if drafted is not None and h.drafted_by_kind == "agent":
            drafted = f"{drafted} via Agent"
        built[h.id] = EnvelopeRow(
            id=h.id,
            number=h.number,
            purpose=h.purpose,
            form_code=h.form_code,
            title=h.title,
            client_id=h.client_id,
            client_name=h.client_name,
            engagement_id=h.engagement_id,
            work_item_id=h.work_item_id,
            work_item_label=h.work_item_label,
            provider=h.provider,
            status=h.status,
            signed=sum(1 for p in mine if p.status == "signed"),
            total=len(mine),
            sent_by_name=user_names.get(h.sent_by) if h.sent_by is not None else None,
            sent_at=h.sent_at,
            viewed_at=min(viewed) if viewed else None,
            due_on=h.due_on,
            needs_handwritten=any(p.status == "verification_failed" for p in mine),
            allowed_actions=actions[h.id],
            signer_chips=chips,
            drafted_by_name=drafted,
            outcome=_outcome(h.source_kind, h.status),
        )
    return [built[i] for i in ids if i in built]


def _first_name(name: str | None) -> str:
    """SIG-01's chip names the signer by first name ("✓ Thomas")."""
    if not name:
        return "Signer"
    return name.split()[0]


# --- The drawer ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class DocumentView:
    id: UUID
    order: int
    title: str
    page_count: int
    sha256: str
    read_only: bool
    tri: bool


@dataclass(frozen=True)
class SignerView:
    id: UUID
    order: int
    routing_group: int
    name: str
    role: str
    identity_method: str
    status: str
    kba_failures: int
    viewed_at: datetime | None
    signed_at: datetime | None
    signature_method: str | None
    decline_reason: str | None
    provider_recipient_id: str | None
    # N-02-T20 (DEC-1174): SIG-02's signer sub-line and the "Email required" check.
    title: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class FieldView:
    id: UUID
    document_id: UUID
    signer_id: UUID
    kind: str
    page: int
    x: float
    y: float
    w: float
    h: float
    anchor: str | None


@dataclass(frozen=True)
class EvidenceView:
    signer_id: UUID
    signed_at: datetime
    ip_masked: str
    identity_result: str
    signature_method: str
    user_agent_family: str | None
    device_label: str | None
    package_sha256: str | None


@dataclass(frozen=True)
class Drawer:
    row: EnvelopeRow
    policy_family: str
    source_kind: str
    source_id: UUID
    signer_order: str
    date_as_of_mode: str
    date_as_of: date | None
    expires_at: datetime | None
    message: str | None
    reminder_cadence: str | None
    documents: list[DocumentView]
    signers: list[SignerView]
    fields: list[FieldView]
    evidence: list[EvidenceView]
    provider_envelope_id: str | None
    superseded_at: datetime | None
    voided_reason: str | None
    version: int


def _contact_title(contacts: dict[UUID, SignerContact], contact_id: UUID | None) -> str | None:
    found = contacts.get(contact_id) if contact_id is not None else None
    return found.title if found is not None else None


def _signer_email(
    contacts: dict[UUID, SignerContact],
    member_emails: dict[UUID, str],
    contact_id: UUID | None,
    user_id: UUID | None,
) -> str | None:
    """The address a signer is reached at: the contact's, or the member's sign-in email."""
    if contact_id is not None:
        found = contacts.get(contact_id)
        return found.email if found is not None else None
    return member_emails.get(user_id) if user_id is not None else None


async def visible_head(ctx: AuthContext, session: AsyncSession, envelope_id: UUID) -> _Head:
    """The envelope if `ctx` may read it; else 404 (the wall and other scopes answer alike)."""
    found = (
        await session.execute(
            select(E.id, E.status, E.client_id, E.engagement_id)
            .select_from(envelopes)
            .where(E.id == envelope_id, visible_envelopes(ctx))
        )
    ).one_or_none()
    if found is None:
        raise NotFound("envelope")
    return _Head(found.id, found.status, found.client_id, found.engagement_id)


async def resource_of(ctx: AuthContext, head: _Head) -> Resource:
    if head.engagement_id is not None:
        return (await get_ref(ctx, head.engagement_id)).resource()
    return Resource.client(ctx.tenant_id, head.client_id)


async def drawer(ctx: AuthContext, envelope_id: UUID) -> Drawer:
    """`GET /v1/envelopes/{id}` (SIG-01's drawer; SIG-02 reads it too)."""
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        await visible_head(ctx, session, envelope_id)
        rows = await _rows(ctx, session, [envelope_id])
        extra = (
            await session.execute(
                select(
                    E.policy_family,
                    E.source_kind,
                    E.source_id,
                    E.signer_order,
                    E.date_as_of_mode,
                    E.date_as_of,
                    E.expires_at,
                    E.message,
                    E.reminder_cadence,
                    E.provider_envelope_id,
                    E.superseded_at,
                    E.void_reason,
                    E.version,
                )
                .select_from(envelopes)
                .where(E.id == envelope_id)
            )
        ).one()
        docs = (
            await session.execute(
                select(documents)
                .where(documents.c.envelope_id == envelope_id)
                .order_by(documents.c.order)
            )
        ).all()
        people = (
            await session.execute(
                select(signers).where(S.envelope_id == envelope_id).order_by(S.order)
            )
        ).all()
        placed = (
            await session.execute(
                select(fields).where(fields.c.envelope_document_id.in_([d.id for d in docs]))
            )
        ).all()
        proofs = (
            await session.execute(select(evidence).where(evidence.c.envelope_id == envelope_id))
        ).all()
        titles = await version_titles(
            session, [d.evidence_version_id for d in docs if d.evidence_version_id is not None]
        )
        contact_names, user_names = await _names(
            session,
            [p.contact_id for p in people if p.contact_id is not None],
            [p.user_id for p in people if p.user_id is not None],
        )
    contacts = await signer_contacts(
        ctx.tenant, [p.contact_id for p in people if p.contact_id is not None]
    )
    member_emails = await contact_emails([p.user_id for p in people if p.user_id is not None])
    row = rows[0]
    order = {p.id: p.order for p in people}
    return Drawer(
        row=row,
        policy_family=extra.policy_family,
        source_kind=extra.source_kind or "",
        source_id=extra.source_id or envelope_id,
        signer_order=extra.signer_order,
        date_as_of_mode=extra.date_as_of_mode,
        date_as_of=extra.date_as_of,
        expires_at=extra.expires_at,
        message=extra.message,
        reminder_cadence=extra.reminder_cadence,
        documents=[
            DocumentView(
                d.id,
                d.order,
                titles.get(d.evidence_version_id, row.title)
                if d.evidence_version_id is not None
                else row.title,
                d.page_count or 1,
                d.sha256,
                bool(d.read_only),
                bool(d.tri),
            )
            for d in docs
        ],
        signers=[
            SignerView(
                p.id,
                p.order,
                p.routing_group,
                (
                    contact_names.get(p.contact_id)
                    if p.contact_id is not None
                    else user_names.get(p.user_id)
                    if p.user_id is not None
                    else None
                )
                or "Signer",
                p.role,
                p.identity_method,
                p.status,
                p.kba_failures,
                p.viewed_at,
                p.signed_at,
                p.signature_method,
                p.decline_reason,
                p.provider_recipient_id,
                _contact_title(contacts, p.contact_id),
                _signer_email(contacts, member_emails, p.contact_id, p.user_id),
            )
            for p in people
        ],
        fields=[
            FieldView(
                f.id,
                f.envelope_document_id,
                f.signer_id,
                f.kind,
                f.page or 1,
                float(f.x or 0),
                float(f.y or 0),
                float(f.w or 0),
                float(f.h or 0),
                f.anchor,
            )
            for f in placed
        ],
        evidence=sorted(
            (
                EvidenceView(
                    v.signer_id,
                    v.signed_at,
                    v.ip_masked or "Not recorded",
                    v.identity_result,
                    v.signature_method,
                    v.user_agent_family,
                    v.device_label,
                    v.package_sha256,
                )
                for v in proofs
            ),
            key=lambda v: order.get(v.signer_id, 0),
        ),
        provider_envelope_id=extra.provider_envelope_id,
        superseded_at=extra.superseded_at,
        voided_reason=extra.void_reason,
        version=extra.version,
    )


# --- Reveal --------------------------------------------------------------------------------------


def ip_fingerprint(signer_id: UUID) -> str:
    """What a signer's sealed address is bound to: opened only for that signer's row."""
    return f"signature_evidence.ip:{signer_id}"


async def seal_ip(tenant_id: UUID, signer_id: UUID, ip: str) -> bytes:
    """The sealed form EnvelopeWorkflow stores in `signature_evidence.ip_sealed` (N-02-T14)."""
    return await seal(tenant_id, ip.encode(), ip_fingerprint(signer_id))


@dataclass(frozen=True)
class Revealed:
    ip: str
    expires_at: datetime


async def reveal_ip(ctx: AuthContext, envelope_id: UUID, signer_id: UUID, reason: str) -> Revealed:
    """`POST .../signers/{sid}/reveal-ip`: the full address for 10 seconds, audited."""
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
        sealed = (
            await session.execute(
                select(evidence.c.ip_sealed)
                .select_from(evidence.join(signers, signers.c.id == evidence.c.signer_id))
                .where(evidence.c.envelope_id == envelope_id, evidence.c.signer_id == signer_id)
            )
        ).one_or_none()
    # Fresh MFA, onshore, a reason: the matrix's modifiers, checked by `authorise`.
    await authorise(ctx, REVEAL, await resource_of(ctx, head), reason=reason)
    if sealed is None:
        raise NotFound("signer")
    if sealed.ip_sealed is None:
        raise IpUnavailable
    ip = (await open_sealed(ctx.tenant_id, sealed.ip_sealed, ip_fingerprint(signer_id))).decode()
    async with uow(ctx.tenant) as tx:
        tx.record(
            "signer.ip_revealed",
            target=Target("envelope", envelope_id),
            after=Ref(signer_id=signer_id),
        )
    return Revealed(ip, system_now() + timedelta(seconds=REVEAL_SECONDS))


# --- The evidence package ------------------------------------------------------------------------


@dataclass(frozen=True)
class Package:
    file_name: str
    body: bytes
    sha256: str


def _entry(archive: zipfile.ZipFile, name: str, body: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, body)


async def evidence_package(ctx: AuthContext, envelope_id: UUID) -> Package:
    """`GET /v1/envelopes/{id}/evidence.zip`: per-signer packages, each stored package and
    document, and `manifest.sha256`; the same evidence always zips to the same bytes."""
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
        number = (
            await session.execute(
                select(E.number).select_from(envelopes).where(E.id == envelope_id)
            )
        ).scalar_one()
        proofs = (
            await session.execute(
                select(evidence, S.order)
                .select_from(evidence.join(signers, signers.c.id == evidence.c.signer_id))
                .where(evidence.c.envelope_id == envelope_id)
                .order_by(S.order)
            )
        ).all()
    await authorise(ctx, DOWNLOAD, await resource_of(ctx, head))
    if not proofs:
        raise NotFound("evidence")
    files: dict[str, bytes] = {}
    for p in proofs:
        files[f"signers/{p.order:02d}-{p.signer_id}.json"] = json.dumps(
            {
                "signer_id": str(p.signer_id),
                "signed_at": p.signed_at.isoformat(),
                "ip_masked": p.ip_masked,
                "identity_result": p.identity_result,
                "signature_method": p.signature_method,
                "user_agent_family": p.user_agent_family,
                "device_label": p.device_label,
                "document_sha256s": list(p.document_sha256s),
                "package_sha256": p.package_sha256,
            },
            sort_keys=True,
            indent=2,
        ).encode()
    digests = sorted({d for p in proofs for d in p.document_sha256s})
    packages = sorted({p.package_sha256 for p in proofs if p.package_sha256 is not None})
    for folder, wanted in (("documents", digests), ("packages", packages)):
        for digest in wanted:
            body = await get_record(ctx.tenant_id, RECORD_TYPE, digest)
            if body is not None:
                files[f"{folder}/{digest}"] = body
    manifest = "".join(
        f"{hashlib.sha256(body).hexdigest()}  {name}\n" for name, body in sorted(files.items())
    ).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, body in sorted(files.items()):
            _entry(archive, name, body)
        _entry(archive, "manifest.sha256", manifest)
    zipped = buffer.getvalue()
    digest = hashlib.sha256(zipped).hexdigest()
    async with uow(ctx.tenant) as tx:
        tx.record(
            "evidence.downloaded",
            target=Target("envelope", envelope_id),
            after=Ref(sha256=digest, files=len(files)),
        )
    return Package(f"E{number}-evidence.zip", zipped, digest)


# --- Void ----------------------------------------------------------------------------------------


async def void(ctx: AuthContext, envelope_id: UUID, reason: str) -> None:
    """`POST /v1/envelopes/{id}/void`: an open envelope, voided by the person; evidence kept."""
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
    await authorise(ctx, VOID, await resource_of(ctx, head))
    if head.status not in OPEN:
        raise EnvelopeNotOpen(facts={"status": head.status})
    now = system_now()
    async with uow(ctx.tenant) as tx:
        changed = await tx.session.execute(
            text(
                "UPDATE envelopes SET status = 'voided', void_reason = :reason, "
                "voided_by = :user, voided_at = :now, version = version + 1, updated_at = :now "
                "WHERE id = :id AND status = ANY(:open) RETURNING version"
            ),
            {
                "reason": reason,
                "user": ctx.user_id,
                "now": now,
                "id": envelope_id,
                "open": sorted(OPEN),
            },
        )
        version = changed.scalar_one_or_none()
        if version is None:
            raise EnvelopeNotOpen(facts={"status": "changed"})
        await tx.session.execute(
            text(
                "UPDATE signing_sessions SET state = 'abandoned' "
                "WHERE envelope_id = :id AND state = 'issued'"
            ),
            {"id": envelope_id},
        )
        await tx.session.execute(
            text(
                "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, occurred_at) "
                "VALUES (:tenant, :id, 'envelope.voided', 'firm', :now)"
            ),
            {"tenant": ctx.tenant_id, "id": envelope_id, "now": now},
        )
        tx.record(
            "envelope.voided",
            target=Target("envelope", envelope_id),
            after=Ref(version=int(version)),
        )
