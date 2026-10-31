"""POR-06's portal signing (N-02-T23; N-02 §3.4; SPEC-381 AC-10-AC-12; DF-11, DF-12; ADR-342;
DEC-1283). PROTECTED.

- **Only the named signer** (INV-4). A client person reaches an envelope only as one of its
  `contact` signers (their contacts: `contacts.user_id` or named by one of their grants), and
  only through `portal_envelopes.*` on the envelope's engagement and work item (`scope_only`).
  Anything else answers 404, so a spouse's envelope, signer or session looks like nothing.
  An envelope on the client alone (no engagement) has no portal scope yet and is refused.
- **The list** is the person's own signer rows: To sign (out for signature or declined, theirs
  not signed) and Signed. Rows the matrix refuses are dropped from the page.
- **ERSD before any session** (ESIGN Act). The firm's newest `esign_disclosures` version is
  accepted per signer and stored write-once in `esign_acceptances` (sealed address, browser
  family); a session needs that acceptance.
- **A signing session** is one row in `signing_sessions`, five minutes to start it, for the named
  signer's session only, refused 409 with a fixed code: `envelope_not_open` (completed, voided,
  expired), `declined`, `verification_failed`, `not_your_turn` (an earlier signer or routing
  group still to sign), `before_date_as_of` (the firm's date, in its zone), `mfa_required` (no
  second step on this session), `esign_consent_required`. DocuSeal refuses framing, so the view
  is a same-tab redirect to the signer's form; the link is a bearer link, fetched from the
  provider per session and never stored (the idempotent replay keeps the session id only).
  A new session abandons the signer's earlier issued ones.
- **The return** never trusts the provider's redirect or a query parameter: it polls the
  provider first (`envelope_poll`, the same truth EnvelopeWorkflow records), then answers. The
  session is `confirmed` once the signer is signed by that poll, else `returned`; the workflow
  is hinted so completion's evidence follows.
- **Decline** takes a reason (and a note) on an open envelope: the signer and the envelope are
  Declined, sessions abandoned, the workflow told. A decline made here may be withdrawn while the
  envelope is still Declined and neither voided nor resent; one the provider reported is final.
  Withdrawing restores the signer and the envelope and restarts the workflow, which re-reads the
  provider (its send is a no-op once the provider holds the envelope).
- **The signed copy** is the combined signed document with the provider's evidence pages after
  it, merged in an isolated child (ADR-110), once evidence is recorded; each download is audited
  `signed_copy.downloaded`.

Final verbs deny `agent` and `system` in the matrix (AC-16). Nothing here is an agent's.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import secrets
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Final, Protocol, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import RowMapping, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._flags import SIGNATURES_ENVELOPES, SIGNATURES_ESIGN_PROVIDER
from abacus.kernel.clock import system_now, today
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.isolation import run_isolated
from abacus.kernel.listing import Position, decode_cursor, query_hash
from abacus.kernel.request_context import current
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import contact_ids_of_user, get_ref
from abacus.modules.evidence.api import get_record, signer_page, version_titles
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    authorise,
    firm_time_zone,
    names_of,
    portal_scopes,
    scope_facts,
)
from abacus.modules.organisations.api import contact_facts
from abacus.modules.signatures import status_poll
from abacus.modules.signatures.activities import envelope_poll
from abacus.modules.signatures.events import EnvelopeDeclined
from abacus.modules.signatures.hub import seal_ip
from abacus.modules.signatures.imports import RECORD_TYPE
from abacus.modules.signatures.provider import ProviderUnavailable, provider_for
from abacus.modules.signatures.workflows import EnvelopeInput

READ: Final = "portal_envelopes.read"
SIGN: Final = "portal_envelopes.sign"
DECLINE: Final = "portal_envelopes.decline"
DOWNLOAD: Final = "portal_envelopes.download"
LIST_RESOURCE: Final = "portal_envelopes"
SESSION_SECONDS: Final = 300  # signing_sessions' CHECK: five minutes at most
OPEN: Final = ("sent", "viewed", "partially_signed")
TO_SIGN: Final = (*OPEN, "declined")


class SigningRefused(DomainConflict):
    code = "signing_refused"


class EnvelopeNotOpen(SigningRefused):
    code = "envelope_not_open"


class SignerDeclined(SigningRefused):
    code = "declined"


class VerificationFailed(SigningRefused):
    code = "verification_failed"


class NotYourTurn(SigningRefused):
    code = "not_your_turn"


class BeforeDateAsOf(SigningRefused):
    code = "before_date_as_of"


class MfaRequired(SigningRefused):
    code = "mfa_required"


class ConsentRequired(SigningRefused):
    code = "esign_consent_required"


class DisclosureOutdated(DomainConflict):
    """The accepted disclosure is not the firm's newest (or the firm has imported none)."""

    code = "disclosure_outdated"


class SessionNotOpen(DomainConflict):
    """The session was abandoned (voided, expired or replaced) or has expired before use."""

    code = "session_not_open"


class DeclineNotWithdrawable(DomainConflict):
    """Only the signer's own portal decline, on an envelope still Declined, can be withdrawn."""

    code = "decline_not_withdrawable"


class SignedCopyNotReady(DomainConflict):
    code = "signed_copy_not_ready"


# --- The named signer --------------------------------------------------------------------------


@dataclass(frozen=True)
class Mine:
    """One envelope as the signer sees it, with their own signer row."""

    envelope_id: UUID
    number: int
    title: str
    status: str
    client_id: UUID
    engagement_id: UUID | None
    work_item_id: UUID | None
    due_on: date | None
    date_as_of: date | None
    signer_order: str
    provider: str
    provider_envelope_id: str | None
    signer_id: UUID
    order: int
    routing_group: int
    signer_status: str
    viewed_at: datetime | None
    policy_family: str
    identity_method: str


_MINE = text(
    "SELECT e.id AS envelope_id, e.number, e.title, e.status, e.client_id, e.engagement_id, "
    "e.work_item_id, e.due_on, e.date_as_of, e.signer_order, e.provider, e.policy_family, "
    's.id AS signer_id, s."order", s.routing_group, s.status AS signer_status, s.viewed_at, '
    "s.identity_method, e.provider_envelope_id "
    "FROM envelopes e JOIN envelope_signers s ON s.envelope_id = e.id "
    "WHERE s.party_kind = 'contact' AND s.contact_id = ANY(:contacts) AND e.status <> 'draft' "
    "AND (CAST(:id AS uuid) IS NULL OR e.id = :id)"
)


def _mine(r: RowMapping) -> Mine:
    return Mine(
        envelope_id=cast(UUID, r["envelope_id"]),
        number=int(cast(int, r["number"])),
        title=str(r["title"]),
        status=str(r["status"]),
        client_id=cast(UUID, r["client_id"]),
        engagement_id=cast(UUID | None, r["engagement_id"]),
        work_item_id=cast(UUID | None, r["work_item_id"]),
        due_on=cast(date | None, r["due_on"]),
        date_as_of=cast(date | None, r["date_as_of"]),
        signer_order=str(r["signer_order"]),
        provider=str(r["provider"]),
        provider_envelope_id=cast(str | None, r["provider_envelope_id"]),
        signer_id=cast(UUID, r["signer_id"]),
        order=int(cast(int, r["order"])),
        routing_group=int(cast(int, r["routing_group"])),
        signer_status=str(r["signer_status"]),
        viewed_at=cast(datetime | None, r["viewed_at"]),
        policy_family=str(r["policy_family"]),
        identity_method=str(r["identity_method"]),
    )


async def _gate(ctx: AuthContext) -> None:
    """A firm principal never reaches portal signing; nor anyone with the module off."""
    if not ctx.client:
        raise NotFound("portal envelopes")
    if not await flag_enabled(ctx.tenant, SIGNATURES_ENVELOPES):
        raise NotFound(SIGNATURES_ENVELOPES.name)


async def _authorised(ctx: AuthContext, mine: Mine, action: str) -> None:
    """`action` on the envelope's engagement and work item (`scope_only`); any refusal is 404."""
    if mine.engagement_id is None:
        raise NotFound("envelope")  # no client-level portal scope yet (DEC-1283)
    try:
        engagement = await get_ref(ctx, mine.engagement_id)
        await authorise(
            ctx, action, replace(engagement.resource(), work_item_id=mine.work_item_id)
        )
    except (Forbidden, NotFound):
        raise NotFound("envelope") from None


async def signer_of(ctx: AuthContext, envelope_id: UUID, action: str) -> Mine:
    """The envelope with the person's own signer row, under `action`; else 404."""
    await _gate(ctx)
    contacts = sorted(await contact_ids_of_user(ctx.tenant, ctx.user_id))
    if not contacts:
        raise NotFound("envelope")
    async with tenant_session(ctx.tenant) as session:
        found = (
            (
                await session.execute(
                    text(f'{_MINE.text} ORDER BY s."order" LIMIT 1'),
                    {"contacts": contacts, "id": envelope_id},
                )
            )
            .mappings()
            .first()
        )
    if found is None:
        raise NotFound("envelope")
    mine = _mine(found)
    await _authorised(ctx, mine, action)
    return mine


# --- The list ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class ListRow:
    id: UUID
    title: str
    status: str
    my_status: str
    due_on: date | None


@dataclass(frozen=True)
class Page:
    rows: list[ListRow]
    next_position: Position | None
    query: str


def _row(m: Mine) -> ListRow:
    return ListRow(m.envelope_id, m.title, m.status, m.signer_status, m.due_on)


async def _list_check(ctx: AuthContext) -> None:
    """The list's own check: `portal_envelopes.read` on an engagement one of the person's grants
    covers (`scope_only`); a person no grant covers has no list (404). Each row is then checked on
    its own engagement and work item."""
    for grant in (await portal_scopes(ctx)).scopes:
        facts = await scope_facts(ctx.tenant, grant.scope_kind, grant.scope_id)
        if facts is None or facts.engagement_id is None:
            continue
        try:
            engagement = await get_ref(ctx, facts.engagement_id)
            await authorise(ctx, READ, engagement.resource())
        except (Forbidden, NotFound):
            continue
        return
    raise NotFound("portal_scope")


async def list_mine(ctx: AuthContext, *, tab: str, cursor: str | None, limit: int) -> Page:
    """`GET /v1/portal/envelopes`: To sign or Signed, newest first, the person's rows only."""
    await _gate(ctx)
    await _list_check(ctx)
    query = query_hash(tab=tab)
    after = (
        None
        if cursor is None
        else decode_cursor(cursor, tenant_id=ctx.tenant_id, resource=LIST_RESOURCE, query=query)
    )
    contacts = sorted(await contact_ids_of_user(ctx.tenant, ctx.user_id))
    if not contacts:
        return Page([], None, query)
    where = (
        "AND e.status = ANY(:tab_statuses) AND s.status <> 'signed'"
        if tab == "to_sign"
        else "AND s.status = 'signed'"
    )
    keyed = "" if after is None else "AND (e.number < :after_number)"
    params: dict[str, object] = {
        "contacts": contacts,
        "id": None,
        "tab_statuses": list(TO_SIGN),
        "limit": limit + 1,
    }
    if after is not None:
        params["after_number"] = int(cast(int, after.key))
    async with tenant_session(ctx.tenant) as session:
        fetched = (
            (
                await session.execute(
                    text(f"{_MINE.text} {where} {keyed} ORDER BY e.number DESC LIMIT :limit"),
                    params,
                )
            )
            .mappings()
            .all()
        )
    more = len(fetched) > limit
    found = [_mine(r) for r in fetched[:limit]]
    rows: list[ListRow] = []
    for m in found:
        try:
            await _authorised(ctx, m, READ)
        except NotFound:
            continue
        rows.append(_row(m))
    last = Position(found[-1].number, str(found[-1].envelope_id)) if more and found else None
    return Page(rows, last, query)


# --- The view ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Document:
    id: UUID
    order: int
    title: str
    page_count: int
    sha256: str
    read_only: bool
    tri: bool


@dataclass(frozen=True)
class Field:
    id: UUID
    document_id: UUID
    kind: str
    page: int
    x: float
    y: float
    w: float
    h: float
    anchor: str | None


@dataclass(frozen=True)
class Session:
    id: UUID
    presentation: str
    url: str
    expires_at: datetime


@dataclass(frozen=True)
class View:
    row: ListRow
    signer_id: UUID
    documents: list[Document]
    my_fields: list[Field]
    signers_signed: int
    signers_total: int
    esign_consent_needed: bool
    disclosure_version_id: UUID | None
    date_as_of: date | None
    paper_form_follows: bool
    family: str
    identity_method: str
    signers: list[Signer]
    signing_opens_on: date | None
    signing_session: Session | None = None
    outcome: str | None = None


@dataclass(frozen=True)
class Signer:
    """One signer in the envelope's order (N-02-T29): the name the firm recorded, never contact
    detail."""

    id: UUID
    name: str
    role: str
    routing_group: int
    status: str
    signed_at: datetime | None


_SIGNERS = text(
    "SELECT id, contact_id, user_id, role, routing_group, status, signed_at FROM envelope_signers "
    'WHERE envelope_id = :id ORDER BY routing_group, "order"'
)


async def _signers(session: AsyncSession, envelope_id: UUID) -> list[Signer]:
    rows = (await session.execute(_SIGNERS, {"id": envelope_id})).all()
    contacts = await contact_facts(
        session, [r.contact_id for r in rows if r.contact_id is not None]
    )
    users = await names_of(list({r.user_id for r in rows if r.user_id is not None}))
    out: list[Signer] = []
    for r in rows:
        name = (
            contacts[r.contact_id].display_name
            if r.contact_id is not None and r.contact_id in contacts
            else users.get(r.user_id)
            if r.user_id is not None
            else None
        )
        out.append(
            Signer(
                r.id,
                name or "Signer",
                str(r.role),
                int(r.routing_group),
                str(r.status),
                cast(datetime | None, r.signed_at),
            )
        )
    return out


async def _opens_on(ctx: AuthContext, mine: Mine) -> date | None:
    """The `before_date_as_of` check, read ahead: the date while the firm's today is before it."""
    if mine.date_as_of is None:
        return None
    zone = ZoneInfo(await firm_time_zone(ctx.tenant))
    return mine.date_as_of if await today(ctx.tenant, zone) < mine.date_as_of else None


_NEWEST_DISCLOSURE = text("SELECT id FROM esign_disclosures ORDER BY version_no DESC LIMIT 1")


async def _newest_disclosure(session: AsyncSession) -> UUID | None:
    return cast(UUID | None, (await session.execute(_NEWEST_DISCLOSURE)).scalar_one_or_none())


async def _accepted(session: AsyncSession, signer_id: UUID, disclosure: UUID | None) -> bool:
    if disclosure is None:
        return False
    found = await session.execute(
        text(
            "SELECT 1 FROM esign_acceptances WHERE signer_id = :signer "
            "AND disclosure_version_id = :disclosure"
        ),
        {"signer": signer_id, "disclosure": disclosure},
    )
    return found.first() is not None


async def _view(ctx: AuthContext, mine: Mine, *, outcome: str | None = None) -> View:
    async with tenant_session(ctx.tenant) as session:
        docs = (
            await session.execute(
                text(
                    'SELECT id, "order", evidence_version_id, sha256, page_count, read_only, '
                    "tri FROM envelope_documents WHERE envelope_id = :id AND signer_visible "
                    'ORDER BY "order"'
                ),
                {"id": mine.envelope_id},
            )
        ).all()
        placed = (
            await session.execute(
                text(
                    "SELECT id, envelope_document_id, kind, page, x, y, w, h, anchor "
                    "FROM envelope_fields WHERE signer_id = :signer "
                    "AND envelope_document_id = ANY(:docs)"
                ),
                {"signer": mine.signer_id, "docs": [d.id for d in docs]},
            )
        ).all()
        counts = (
            await session.execute(
                text(
                    "SELECT count(*) FILTER (WHERE status = 'signed') AS signed, "
                    "count(*) AS total FROM envelope_signers WHERE envelope_id = :id"
                ),
                {"id": mine.envelope_id},
            )
        ).one()
        disclosure = await _newest_disclosure(session)
        accepted = await _accepted(session, mine.signer_id, disclosure)
        titles = await version_titles(
            session, [d.evidence_version_id for d in docs if d.evidence_version_id is not None]
        )
        signers = await _signers(session, mine.envelope_id)
    opens_on = await _opens_on(ctx, mine)
    return View(
        row=_row(mine),
        signer_id=mine.signer_id,
        documents=[
            Document(
                d.id,
                int(d.order),
                titles.get(d.evidence_version_id, mine.title)
                if d.evidence_version_id is not None
                else mine.title,
                int(d.page_count or 1),
                str(d.sha256),
                bool(d.read_only),
                bool(d.tri),
            )
            for d in docs
        ],
        my_fields=[
            Field(
                f.id,
                f.envelope_document_id,
                str(f.kind),
                int(f.page or 1),
                float(f.x or 0),
                float(f.y or 0),
                float(f.w or 0),
                float(f.h or 0),
                f.anchor,
            )
            for f in placed
        ],
        signers_signed=int(counts.signed),
        signers_total=int(counts.total),
        esign_consent_needed=not accepted,
        disclosure_version_id=disclosure,
        date_as_of=mine.date_as_of,
        paper_form_follows=mine.signer_status == "verification_failed",
        family=mine.policy_family,
        identity_method=mine.identity_method,
        signers=signers,
        signing_opens_on=opens_on,
        outcome=outcome,
    )


async def view(ctx: AuthContext, envelope_id: UUID) -> View:
    """`GET /v1/portal/envelopes/{id}`."""
    return await _view(ctx, await signer_of(ctx, envelope_id, READ))


async def page(ctx: AuthContext, envelope_id: UUID, document_id: UUID, page_no: int) -> bytes:
    """One masked page of a document the signer sees (evidence's `signer_page`, read logged)."""
    mine = await signer_of(ctx, envelope_id, READ)
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text(
                    "SELECT evidence_version_id FROM envelope_documents WHERE id = :doc "
                    "AND envelope_id = :id AND signer_visible"
                ),
                {"doc": document_id, "id": mine.envelope_id},
            )
        ).one_or_none()
    if found is None or found[0] is None:
        raise NotFound("envelope_document")
    return await signer_page(ctx, found[0], page_no)


_EVENT = text(
    "INSERT INTO envelope_events (tenant_id, envelope_id, signer_id, kind, source, occurred_at) "
    "VALUES (:tenant, :envelope, :signer, :kind, 'portal', :at)"
)


async def viewed(ctx: AuthContext, envelope_id: UUID) -> ListRow:
    """`POST …/viewed`: the signer's first view, once; an envelope out for signature moves to
    Viewed. Nothing changes on a closed envelope or a signer who already viewed."""
    mine = await signer_of(ctx, envelope_id, READ)
    if mine.status not in OPEN or mine.viewed_at is not None:
        return _row(mine)
    now = system_now()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE envelope_signers SET viewed_at = COALESCE(viewed_at, :now), status = "
                "CASE WHEN status = 'pending' THEN 'viewed' ELSE status END WHERE id = :id"
            ),
            {"now": now, "id": mine.signer_id},
        )
        await tx.session.execute(
            text(
                "UPDATE envelopes SET status = 'viewed', version = version + 1, updated_at = :now "
                "WHERE id = :id AND status = 'sent'"
            ),
            {"now": now, "id": mine.envelope_id},
        )
        await tx.session.execute(
            _EVENT,
            {
                "tenant": ctx.tenant_id,
                "envelope": mine.envelope_id,
                "signer": mine.signer_id,
                "kind": "signer.viewed",
                "at": now,
            },
        )
        tx.record("envelope.viewed", target=Target("envelope", mine.envelope_id))
    return _row(await signer_of(ctx, envelope_id, READ))


async def progress(ctx: AuthContext, envelope_id: UUID, last_page_seen: int) -> ListRow:
    """`POST …/progress`: the furthest page the signer has seen (it never goes back)."""
    mine = await signer_of(ctx, envelope_id, READ)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE envelope_signers SET last_page_seen = GREATEST(COALESCE(last_page_seen, "
                "0), :page) WHERE id = :id"
            ),
            {"page": last_page_seen, "id": mine.signer_id},
        )
        tx.record(
            "signer.progress",
            target=Target("envelope", mine.envelope_id),
            after=Ref(last_page_seen=last_page_seen),
        )
    return _row(mine)


# --- ERSD consent ------------------------------------------------------------------------------


async def consent(ctx: AuthContext, envelope_id: UUID, disclosure_version_id: UUID) -> View:
    """`POST …/esign-consent`: the firm's newest disclosure, accepted once per signer."""
    mine = await signer_of(ctx, envelope_id, SIGN)
    if mine.status not in OPEN:
        raise EnvelopeNotOpen(facts={"status": mine.status})
    async with tenant_session(ctx.tenant) as session:
        newest = await _newest_disclosure(session)
    if newest is None or newest != disclosure_version_id:
        raise DisclosureOutdated
    request = current()
    ip = request.ip if request is not None else None
    sealed = await seal_ip(ctx.tenant_id, mine.signer_id, ip) if ip else None
    async with uow(ctx.tenant) as tx:
        added = (
            await tx.session.execute(
                text(
                    "INSERT INTO esign_acceptances (tenant_id, signer_id, disclosure_version_id, "
                    "ip_sealed, user_agent_family) VALUES (:tenant, :signer, :disclosure, "
                    ":sealed, :agent) ON CONFLICT (tenant_id, signer_id, disclosure_version_id) "
                    "DO NOTHING RETURNING id"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "signer": mine.signer_id,
                    "disclosure": disclosure_version_id,
                    "sealed": sealed,
                    "agent": request.user_agent_family if request is not None else None,
                },
            )
        ).first() is not None
        if added:
            await tx.session.execute(
                _EVENT,
                {
                    "tenant": ctx.tenant_id,
                    "envelope": mine.envelope_id,
                    "signer": mine.signer_id,
                    "kind": "signer.esign_consent_accepted",
                    "at": system_now(),
                },
            )
        tx.record(
            "signer.esign_consent_accepted",
            target=Target("envelope", mine.envelope_id),
            after=Ref(disclosure_version_id=disclosure_version_id, repeat=0 if added else 1),
        )
    return await _view(ctx, mine)


# --- Signing sessions --------------------------------------------------------------------------


_EARLIER_BY_ORDER = text(
    'SELECT 1 FROM envelope_signers WHERE envelope_id = :id AND "order" < :mark '
    "AND status <> 'signed' LIMIT 1"
)
_EARLIER_BY_GROUP = text(
    "SELECT 1 FROM envelope_signers WHERE envelope_id = :id AND routing_group < :mark "
    "AND status <> 'signed' LIMIT 1"
)


async def _earlier_unsigned(ctx: AuthContext, mine: Mine) -> bool:
    """Whether a signer before this one (by order, or by routing group in parallel) has not
    signed yet: the provider would refuse them too."""
    sequential = mine.signer_order == "sequential"
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(
            _EARLIER_BY_ORDER if sequential else _EARLIER_BY_GROUP,
            {"id": mine.envelope_id, "mark": mine.order if sequential else mine.routing_group},
        )
        return found.first() is not None


async def check_session(ctx: AuthContext, envelope_id: UUID) -> Mine:
    """Every refusal before a session is issued, in the contract's order."""
    mine = await signer_of(ctx, envelope_id, SIGN)
    if mine.signer_status == "declined":
        raise SignerDeclined
    if mine.status not in OPEN:
        raise EnvelopeNotOpen(facts={"status": mine.status})
    if mine.signer_status == "verification_failed":
        raise VerificationFailed
    if mine.signer_status == "signed":
        raise EnvelopeNotOpen(facts={"status": "signed"})
    if mine.provider_envelope_id is None or mine.provider == "record":
        raise EnvelopeNotOpen(facts={"status": "not_at_provider"})
    if ctx.mfa_at is None and not ctx.portal_second_step:
        raise MfaRequired
    if await _earlier_unsigned(ctx, mine):
        raise NotYourTurn
    if mine.date_as_of is not None:
        zone = ZoneInfo(await firm_time_zone(ctx.tenant))
        if await today(ctx.tenant, zone) < mine.date_as_of:
            raise BeforeDateAsOf(facts={"date_as_of": mine.date_as_of.isoformat()})
    async with tenant_session(ctx.tenant) as session:
        if not await _accepted(session, mine.signer_id, await _newest_disclosure(session)):
            raise ConsentRequired
    if not await flag_enabled(ctx.tenant, SIGNATURES_ESIGN_PROVIDER):
        raise ProviderUnavailable
    return mine


async def issue_session(ctx: AuthContext, mine: Mine) -> UUID:
    """A new session for the signer; their earlier issued ones are abandoned."""
    now = system_now()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE signing_sessions SET state = 'abandoned' WHERE signer_id = :signer "
                "AND state = 'issued'"
            ),
            {"signer": mine.signer_id},
        )
        made = (
            await tx.session.execute(
                text(
                    "INSERT INTO signing_sessions (tenant_id, envelope_id, signer_id, "
                    "principal_id, presentation, expires_at, return_token_hash) VALUES "
                    "(:tenant, :envelope, :signer, :principal, 'redirect', :expires, :token) "
                    "RETURNING id"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "envelope": mine.envelope_id,
                    "signer": mine.signer_id,
                    "principal": ctx.user_id,
                    # issued_at is the row's clock; stay inside its five-minute CHECK
                    "expires": now + timedelta(seconds=SESSION_SECONDS - 5),
                    "token": hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
                },
            )
        ).scalar_one()
        tx.record(
            "signer.signing_session_issued",
            target=Target("envelope", mine.envelope_id),
            after=Ref(session_id=cast(UUID, made)),
        )
    return cast(UUID, made)


async def open_session(ctx: AuthContext, mine: Mine, session_id: UUID) -> Session:
    """The session's provider view, for its own principal while it is issued and unexpired. The
    link is read from the provider now and returned once; it is never stored."""
    async with tenant_session(ctx.tenant) as session:
        found = (
            await session.execute(
                text(
                    "SELECT presentation, expires_at, state FROM signing_sessions WHERE id = :id "
                    "AND signer_id = :signer AND principal_id = :principal"
                ),
                {"id": session_id, "signer": mine.signer_id, "principal": ctx.user_id},
            )
        ).one_or_none()
    if found is None:
        raise NotFound("signing_session")
    if found.state != "issued" or found.expires_at <= system_now():
        raise SessionNotOpen
    adapter = await provider_for(ctx.tenant_id)
    url = await adapter.signing_url(cast(str, mine.provider_envelope_id), str(mine.signer_id))
    return Session(session_id, str(found.presentation), url, found.expires_at)


async def signing_return(ctx: AuthContext, envelope_id: UUID, session_id: UUID) -> View:
    """`GET …/signing-session/{sid}/return`: poll the provider, then answer from our rows."""
    mine = await signer_of(ctx, envelope_id, SIGN)
    async with tenant_session(ctx.tenant) as session:
        state = (
            await session.execute(
                text(
                    "SELECT state FROM signing_sessions WHERE id = :id AND signer_id = :signer "
                    "AND principal_id = :principal AND envelope_id = :envelope"
                ),
                {
                    "id": session_id,
                    "signer": mine.signer_id,
                    "principal": ctx.user_id,
                    "envelope": mine.envelope_id,
                },
            )
        ).scalar_one_or_none()
    if state is None:
        raise NotFound("signing_session")
    given = EnvelopeInput(str(ctx.tenant_id), str(mine.envelope_id))
    # The provider's truth, recorded before anything is shown; only for a session still waiting
    # on its outcome, so a settled or abandoned session's page never calls the provider again.
    if state in ("issued", "returned") and mine.status in OPEN and mine.provider_envelope_id:
        await envelope_poll(given)
    mine = await signer_of(ctx, envelope_id, SIGN)
    outcome: str | None = None
    if mine.signer_status == "signed":
        outcome, settled = "signed", "confirmed"
    elif mine.signer_status == "declined":
        outcome, settled = "declined", "returned"
    else:
        settled = "returned"  # pending confirmation: the page asks again
    if state in ("issued", "returned") and settled != state:
        async with uow(ctx.tenant) as tx:
            await tx.session.execute(
                text("UPDATE signing_sessions SET state = :state WHERE id = :id"),
                {"state": settled, "id": session_id},
            )
            tx.record(
                "signer.signing_session_confirmed"
                if settled == "confirmed"
                else "signer.signing_session_returned",
                target=Target("envelope", mine.envelope_id),
                after=Ref(session_id=session_id),
            )
    if mine.provider_envelope_id is not None:
        await status_poll.hint_envelope(ctx.tenant_id, mine.envelope_id)
    if state == "abandoned" and outcome is None:
        outcome = "abandoned"
    return await _view(ctx, mine, outcome=outcome)


# --- Decline and withdraw ----------------------------------------------------------------------


async def decline(ctx: AuthContext, envelope_id: UUID, reason: str, note: str | None) -> View:
    """`POST …/decline`: the signer and the envelope Declined; sessions abandoned."""
    mine = await signer_of(ctx, envelope_id, DECLINE)
    if mine.status not in OPEN or mine.signer_status in ("signed", "declined"):
        raise EnvelopeNotOpen(facts={"status": mine.status})
    now = system_now()
    async with tenant_session(ctx.tenant) as session:
        sent_by = await session.scalar(
            text("SELECT sent_by FROM envelopes WHERE id = :id"), {"id": mine.envelope_id}
        )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE envelope_signers SET status = 'declined', decline_reason = :reason, "
                "decline_note = :note WHERE id = :id"
            ),
            {"reason": reason, "note": note, "id": mine.signer_id},
        )
        await tx.session.execute(
            text(
                "UPDATE envelopes SET status = 'declined', version = version + 1, "
                "updated_at = :now WHERE id = :id AND status = ANY(:open)"
            ),
            {"now": now, "id": mine.envelope_id, "open": list(OPEN)},
        )
        await tx.session.execute(
            text(
                "UPDATE signing_sessions SET state = 'abandoned' WHERE envelope_id = :id "
                "AND state = 'issued'"
            ),
            {"id": mine.envelope_id},
        )
        for kind, signer in (("signer.declined", mine.signer_id), ("envelope.declined", None)):
            await tx.session.execute(
                _EVENT,
                {
                    "tenant": ctx.tenant_id,
                    "envelope": mine.envelope_id,
                    "signer": signer,
                    "kind": kind,
                    "at": now,
                },
            )
        tx.record("envelope.declined", target=Target("envelope", mine.envelope_id))
        tx.emit(  # N-02-T24: the sender is told, as for a decline the poll reads
            EnvelopeDeclined(
                envelope_id=mine.envelope_id,
                client_id=mine.client_id,
                engagement_id=mine.engagement_id,
                sent_by=sent_by,
            )
        )
    if mine.provider_envelope_id is not None:
        # the workflow sees Declined and ends
        await status_poll.hint_envelope(ctx.tenant_id, mine.envelope_id)
    return await _view(ctx, await signer_of(ctx, envelope_id, DECLINE), outcome="declined")


async def withdraw_decline(ctx: AuthContext, envelope_id: UUID) -> View:
    """`POST …/decline/withdraw`: the signer's own portal decline, while still Declined."""
    mine = await signer_of(ctx, envelope_id, DECLINE)
    if mine.status != "declined" or mine.signer_status != "declined":
        raise DeclineNotWithdrawable
    async with tenant_session(ctx.tenant) as session:
        source = (
            await session.execute(
                text(
                    "SELECT source FROM envelope_events WHERE envelope_id = :id AND signer_id = "
                    ":signer AND kind = 'signer.declined' ORDER BY recorded_at DESC LIMIT 1"
                ),
                {"id": mine.envelope_id, "signer": mine.signer_id},
            )
        ).scalar_one_or_none()
        others = (
            await session.execute(
                text("SELECT status FROM envelope_signers WHERE envelope_id = :id AND id <> :me"),
                {"id": mine.envelope_id, "me": mine.signer_id},
            )
        ).scalars()
        other_statuses = [str(s) for s in others]
    if source != "portal" or "declined" in other_statuses:
        raise DeclineNotWithdrawable  # the provider's decline is final; another signer's stands
    mine_now = "viewed" if mine.viewed_at is not None else "pending"
    statuses = [mine_now, *other_statuses]
    restored = (
        "partially_signed"
        if "signed" in statuses
        else "viewed"
        if "viewed" in statuses or "verification_failed" in statuses
        else "sent"
    )
    now = system_now()
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE envelope_signers SET status = :status, decline_reason = NULL, "
                "decline_note = NULL WHERE id = :id AND status = 'declined'"
            ),
            {"status": mine_now, "id": mine.signer_id},
        )
        changed = await tx.session.execute(
            text(
                "UPDATE envelopes SET status = :status, version = version + 1, updated_at = :now "
                "WHERE id = :id AND status = 'declined' RETURNING id"
            ),
            {"status": restored, "now": now, "id": mine.envelope_id},
        )
        if changed.first() is None:
            raise DeclineNotWithdrawable  # voided or resent meanwhile
        await tx.session.execute(
            _EVENT,
            {
                "tenant": ctx.tenant_id,
                "envelope": mine.envelope_id,
                "signer": mine.signer_id,
                "kind": "envelope.decline_withdrawn",
                "at": now,
            },
        )
        tx.record("envelope.decline_withdrawn", target=Target("envelope", mine.envelope_id))
    if mine.provider_envelope_id is not None:
        await status_poll.hint_envelope(ctx.tenant_id, mine.envelope_id)  # restarts the workflow
    return await _view(ctx, await signer_of(ctx, envelope_id, DECLINE))


# --- The signed copy ---------------------------------------------------------------------------


class _Pdf(Protocol):  # what pypdfium2's untyped document offers
    def import_pages(self, pdf: object) -> None: ...
    def save(self, dest: io.BytesIO) -> None: ...
    def close(self) -> None: ...


def merged_pdf(document: bytes, certificate: bytes) -> bytes:
    """The signed document with the evidence pages after it; runs in the isolated child only."""
    import pypdfium2 as pdfium

    out = cast(_Pdf, pdfium.PdfDocument(document))
    evidence = pdfium.PdfDocument(certificate)
    try:
        out.import_pages(evidence)
        buffer = io.BytesIO()
        out.save(buffer)
        return buffer.getvalue()
    finally:
        evidence.close()
        out.close()


@dataclass(frozen=True)
class SignedCopy:
    file_name: str
    body: bytes
    sha256: str


async def signed_copy(ctx: AuthContext, envelope_id: UUID) -> SignedCopy:
    """`GET …/download`: once evidence is recorded; audited `signed_copy.downloaded`."""
    mine = await signer_of(ctx, envelope_id, DOWNLOAD)
    if mine.status != "completed":
        raise SignedCopyNotReady
    async with tenant_session(ctx.tenant) as session:
        hashes = (
            await session.execute(
                text(
                    "SELECT document_sha256s FROM signature_evidence WHERE envelope_id = :id "
                    "AND signer_id = :signer"
                ),
                {"id": mine.envelope_id, "signer": mine.signer_id},
            )
        ).scalar_one_or_none()
    if not hashes or len(hashes) < 2:
        raise SignedCopyNotReady
    document = await get_record(ctx.tenant_id, RECORD_TYPE, str(hashes[0]))
    certificate = await get_record(ctx.tenant_id, RECORD_TYPE, str(hashes[1]))
    if document is None or certificate is None:
        raise SignedCopyNotReady
    body = await asyncio.to_thread(run_isolated, merged_pdf, document, certificate)
    digest = hashlib.sha256(body).hexdigest()
    async with uow(ctx.tenant) as tx:
        tx.record(
            "signed_copy.downloaded",
            target=Target("envelope", mine.envelope_id),
            after=Ref(sha256=digest),
        )
    return SignedCopy(f"E{mine.number}-signed.pdf", body, digest)
