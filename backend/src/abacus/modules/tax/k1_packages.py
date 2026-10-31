"""K-1 package core (T-02-T20; T-02 §3.6; TXP-12; DEC-78, DEC-88, DEC-52; DEC-1471). Amber.

**The K-1 set.** A person uploads the engine's K-1 set (`engine_import.create` kind `k1_set`, the
bridge's route; their upload is the human approval the plan names). The manifest is JSON, parsed
in the isolated child (ADR-052): the issuing form and year, draft or final, and per recipient the
engine's reference, name, kind, TIN last four (a full TIN refuses the file, DEC-52), address,
K-3 status, states, the documents by the engine PDF file names already imported on this return,
and the box lines when the engine carries them. Applying it, in one unit of work:

- each recipient is kept by the engine's reference (its details refreshed from the newest set);
- a recipient with no package gets version 1; one whose newest package is a draft gets a new
  version and the draft is superseded; one already released gets a new version naming it
  (`supersedes_package_id`, "Superseded (amended K-1)"): the new set needs its own release (T21);
- documents are the imported engine PDFs (write-once evidence), marked draft unless the set is
  final; drafts never reach the portal (DEC-78).

**Sharing internally** (`k1_package.share_internal`): a recipient's K-1 goes to another return's
intake: a hand-off (`draft_shared`), a copy of the K-1 PDF as an `internal_handoff` evidence
version in the receiving return's scope, fulfilling its K-1 request when exactly one open request
names a K-1 from this issuer, and a final-approval dependency (the `draft_k1` blocker in T-01's
slot) until the release replaces the draft (T21). The sharer must be able to read both returns;
a reader of the receiving return who cannot read the issuing one sees no link (DEC-88).

**Reads**: the return's packages with tiles by status and expanded rows (documents), a package
with its box lines (TRI, `tax_return.read`'s readers only), the release check (codes, never
prose; the release itself is T21's red `k1_release.py`), and the recipient's details changes.
**Resend** records the corrected contact and asks T21's workflow to send a new invitation.
**Details changes** are accepted or rejected by a person, once (0565's trigger); Accrued records
the decision for the firm to apply in CCH and stores no full TIN.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.classification import classified
from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.kernel.uow import DomainEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import work_item_facts
from abacus.modules.evidence.api import file_handoff_copy, stage_content
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    ScopeFacts,
    allowed_actions,
    authorise,
    engagement_resource,
    resolve_scope,
)
from abacus.modules.organisations.api import client_of_entity, contact_facts
from abacus.modules.requests.api import fulfil_by_rule, k1_request_for
from abacus.modules.tax import engine_repository as repo
from abacus.modules.tax.approval import Blocker

KIND: Final = "tax_return"
READ: Final = "k1_package.read"
SHARE: Final = "k1_package.share_internal"
RESEND: Final = "k1_package.resend"
REVIEW: Final = "k1_recipient.review_details"
CONTENT: Final = "tax_return.read"
RELEASED: Final = ("released", "viewed", "downloaded", "bounced")
_FORMS: Final = frozenset({"1065", "1120s", "1041"})
_RECIPIENT_KINDS: Final = frozenset({"gp", "lp", "shareholder", "beneficiary"})
_DOC_KINDS: Final = frozenset({"k1", "k3", "state_k1", "letter"})
_K3: Final = frozenset({"included", "not_required", "not_included"})
_FULL_TIN: Final = re.compile(r"(?<![0-9])[0-9]{3}-?[0-9]{2}-?[0-9]{4}(?![0-9])")
_STATE: Final = re.compile(r"[A-Z]{2}")
_LAST4: Final = re.compile(r"[0-9]{4}")
_APPROVED_STATUSES: Final = frozenset(
    {"approved", "ready", "awaiting_signature", "ready_to_file", "filed", "accepted"}
)


class K1SetRefused(DomainInvalid):
    """422: the K-1 set is not a valid engine manifest (`facts.reason`, never its content)."""

    code = "k1_set_invalid"


class K1DocumentMissing(DomainInvalid):
    """422: the set names an engine PDF this return has not imported."""

    code = "k1_document_missing"


class K1NotShareable(DomainConflict):
    """Only this return's own draft or released packages are shared, to another tax return."""

    code = "k1_not_shareable"


class K1NotReleased(DomainConflict):
    """Resend is for a released package."""

    code = "k1_not_released"


class DetailsChangeDecided(DomainConflict):
    code = "details_change_decided"


class K1SetImported(DomainEvent):
    """A person's K-1 set landed as packages on the issuing return."""

    event_type: ClassVar[str] = "schedule_k_set.imported"

    work_item_id: Annotated[UUID, classified("internal")]
    sync_event_id: Annotated[UUID, classified("internal")]
    packages: Annotated[int, classified("internal")]
    is_final: Annotated[bool, classified("internal")]


class K1ResendRequested(DomainEvent):
    """T21's workflow sends a new invitation to the corrected contact."""

    event_type: ClassVar[str] = "schedule_k_package.resend_requested"

    package_id: Annotated[UUID, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


# --- the manifest (parsed in the isolated child) ----------------------------------------------


@dataclass(frozen=True)
class SetDocument:
    kind: str
    jurisdiction: str | None
    file_name: str


@dataclass(frozen=True)
class SetLine:
    document_kind: str
    box_code: str
    description: str
    amount: Decimal
    is_total: bool


@dataclass(frozen=True)
class SetRecipient:
    ref: str
    name: str
    kind: str
    is_entity: bool
    tin_last4: str | None
    tin_kind: str | None
    address: dict[str, str] | None
    ownership_note: str | None
    k3_status: str
    states: tuple[str, ...]
    documents: tuple[SetDocument, ...]
    lines: tuple[SetLine, ...] = field(default_factory=tuple[SetLine, ...])


@dataclass(frozen=True)
class K1Set:
    engine_return_id: str
    version: int
    is_final: bool
    form: str
    tax_year: int
    period_start: date | None
    period_end: date | None
    recipients: tuple[SetRecipient, ...]


def _text(raw: object, limit: int, reason: str) -> str:
    if not isinstance(raw, str) or not 1 <= len(raw.strip()) <= limit:
        raise ValueError(reason)
    return raw.strip()


def _opt(raw: object, limit: int, reason: str) -> str | None:
    return None if raw is None else _text(raw, limit, reason)


def _day(raw: object) -> date | None:
    return None if raw is None else date.fromisoformat(_text(raw, 10, "bad_date"))


def parse_k1_set(content: bytes) -> K1Set:
    """The engine's K-1 set manifest; any doubt refuses (never echoes the content)."""
    if _FULL_TIN.search(content.decode("utf-8", errors="replace")):
        raise ValueError("full_tin")
    body = json.loads(content)
    if not isinstance(body, dict):
        raise ValueError("not_an_object")
    top = cast(dict[str, object], body)
    form = _text(top.get("form"), 5, "bad_form")
    if form not in _FORMS:
        raise ValueError("bad_form")
    recipients: list[SetRecipient] = []
    raw_recipients = top.get("recipients")
    if not isinstance(raw_recipients, list):
        raise ValueError("bad_recipients")
    listed = cast(list[object], raw_recipients)
    if not 1 <= len(listed) <= 2000:
        raise ValueError("bad_recipients")
    for raw in listed:
        if not isinstance(raw, dict):
            raise ValueError("bad_recipient")
        r = cast(dict[str, object], raw)
        kind = _text(r.get("kind"), 20, "bad_kind")
        if kind not in _RECIPIENT_KINDS:
            raise ValueError("bad_kind")
        last4 = _opt(r.get("tin_last4"), 4, "bad_tin")
        if last4 is not None and not _LAST4.fullmatch(last4):
            raise ValueError("bad_tin")
        tin_kind = _opt(r.get("tin_kind"), 4, "bad_tin_kind")
        if tin_kind not in (None, "ssn", "ein", "itin"):
            raise ValueError("bad_tin_kind")
        address = r.get("address")
        if address is not None and not (
            isinstance(address, dict)
            and all(
                isinstance(k, str) and isinstance(v, str) and len(v) <= 200
                for k, v in cast(dict[object, object], address).items()
            )
        ):
            raise ValueError("bad_address")
        k3 = _text(r.get("k3", "not_included"), 20, "bad_k3")
        if k3 not in _K3:
            raise ValueError("bad_k3")
        states = tuple(_text(s, 2, "bad_state") for s in cast(list[object], r.get("states") or []))
        if not all(_STATE.fullmatch(s) for s in states):
            raise ValueError("bad_state")
        documents: list[SetDocument] = []
        for d in cast(list[object], r.get("documents") or []):
            if not isinstance(d, dict):
                raise ValueError("bad_document")
            doc = cast(dict[str, object], d)
            doc_kind = _text(doc.get("kind"), 10, "bad_document")
            jurisdiction = _opt(doc.get("jurisdiction"), 2, "bad_document")
            if doc_kind not in _DOC_KINDS or (doc_kind == "state_k1") != (
                jurisdiction is not None
            ):
                raise ValueError("bad_document")
            documents.append(
                SetDocument(doc_kind, jurisdiction, _text(doc.get("file_name"), 255, "bad_name"))
            )
        lines: list[SetLine] = []
        for n in cast(list[object], r.get("box_lines") or []):
            if not isinstance(n, dict):
                raise ValueError("bad_line")
            line = cast(dict[str, object], n)
            doc_kind = _text(line.get("document_kind"), 10, "bad_line")
            if doc_kind not in ("k1", "k3", "state_k1"):
                raise ValueError("bad_line")
            try:
                amount = Decimal(_text(line.get("amount"), 24, "bad_amount"))
            except InvalidOperation:
                raise ValueError("bad_amount") from None
            lines.append(
                SetLine(
                    doc_kind,
                    _text(line.get("box_code"), 20, "bad_line"),
                    _text(line.get("description"), 200, "bad_line"),
                    amount,
                    bool(line.get("is_total", False)),
                )
            )
        recipients.append(
            SetRecipient(
                ref=_text(r.get("ref"), 100, "bad_ref"),
                name=_text(r.get("name"), 200, "bad_name"),
                kind=kind,
                is_entity=bool(r.get("is_entity", False)),
                tin_last4=last4,
                tin_kind=tin_kind,
                address=cast(dict[str, str] | None, address),
                ownership_note=_opt(r.get("ownership_note"), 200, "bad_note"),
                k3_status=k3,
                states=states,
                documents=tuple(documents),
                lines=tuple(lines),
            )
        )
    if len({r.ref for r in recipients}) != len(recipients):
        raise ValueError("duplicate_recipient")
    year = top.get("tax_year")
    version = top.get("version")
    if not isinstance(year, int) or not isinstance(version, int) or version < 1:
        raise ValueError("bad_header")
    return K1Set(
        engine_return_id=_text(top.get("engine_return_id"), 40, "bad_header"),
        version=version,
        is_final=bool(top.get("is_final", False)),
        form=form,
        tax_year=year,
        period_start=_day(top.get("period_start")),
        period_end=_day(top.get("period_end")),
        recipients=tuple(recipients),
    )


async def _parsed(content: bytes) -> K1Set:
    try:
        return await asyncio.to_thread(run_isolated, parse_k1_set, content)
    except IsolationFailed:
        raise K1SetRefused(facts={"reason": "unreadable"}) from None
    except ValueError as exc:
        reason = str(exc) if re.fullmatch(r"[a-z_]{1,30}", str(exc)) else "invalid"
        raise K1SetRefused(facts={"reason": reason}) from None


# --- applying a set ---------------------------------------------------------------------------


async def _engine_pdfs(session: AsyncSession, return_id: UUID) -> dict[str, UUID]:
    """The return's imported engine PDFs by file name (the newest copy of a name)."""
    rows = (
        await session.execute(
            text(
                "SELECT file_name, summary ->> 'evidence_version_id' AS version FROM "
                "engine_sync_events WHERE return_id = :r AND kind = 'pdfs' ORDER BY at"
            ),
            {"r": return_id},
        )
    ).all()
    return {str(r.file_name): UUID(str(r.version)) for r in rows if r.file_name and r.version}


async def _event(
    tx: UnitOfWork,
    tenant_id: UUID,
    package_id: UUID,
    kind: str,
    actor: UUID | None,
    facts: Mapping[str, object] | None = None,
) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO k1_package_events (tenant_id, package_id, kind, actor_kind, "
            "actor_user_id, facts) VALUES (:t, :p, :k, :ak, :u, CAST(:f AS jsonb))"
        ),
        {
            "t": tenant_id,
            "p": package_id,
            "k": kind,
            "ak": "human" if actor is not None else "system",
            "u": actor,
            "f": json.dumps(dict(facts or {}), sort_keys=True, default=str),
        },
    )


async def apply_k1_set(
    tx: UnitOfWork,
    ctx: AuthContext,
    return_id: UUID,
    found: K1Set,
    sync_event_id: UUID,
) -> int:
    """Write the set's recipients, packages, documents and lines; answers the packages made."""
    pdfs = await _engine_pdfs(tx.session, return_id)
    for r in found.recipients:
        for d in r.documents:
            if d.file_name not in pdfs:
                raise K1DocumentMissing(facts={"recipient": r.ref[:40]})
    made = 0
    for r in found.recipients:
        recipient = (
            await tx.session.execute(
                text(
                    "INSERT INTO k1_recipients (tenant_id, work_item_id, engine_ref, "
                    "display_name, recipient_kind, is_entity, tin_last4, tin_kind, address, "
                    "ownership_note) VALUES (:t, :w, :ref, :name, :kind, :entity, :last4, :tk, "
                    "CAST(:addr AS jsonb), :note) ON CONFLICT (tenant_id, work_item_id, "
                    "engine_ref) DO UPDATE SET display_name = EXCLUDED.display_name, "
                    "recipient_kind = EXCLUDED.recipient_kind, is_entity = EXCLUDED.is_entity, "
                    "tin_last4 = EXCLUDED.tin_last4, tin_kind = EXCLUDED.tin_kind, "
                    "address = EXCLUDED.address, ownership_note = EXCLUDED.ownership_note "
                    "RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "w": return_id,
                    "ref": r.ref,
                    "name": r.name,
                    "kind": r.kind,
                    "entity": r.is_entity,
                    "last4": r.tin_last4,
                    "tk": r.tin_kind,
                    "addr": json.dumps(r.address) if r.address is not None else None,
                    "note": r.ownership_note,
                },
            )
        ).scalar_one()
        latest = (
            await tx.session.execute(
                text(
                    "SELECT id, status, version_no FROM k1_packages WHERE recipient_id = :r "
                    "ORDER BY version_no DESC LIMIT 1 FOR UPDATE"
                ),
                {"r": recipient},
            )
        ).one_or_none()
        supersedes: UUID | None = None
        version_no = 1
        if latest is not None:
            version_no = int(latest.version_no) + 1
            if latest.status in RELEASED:
                supersedes = latest.id
            if latest.status != "superseded":
                await tx.session.execute(
                    text("UPDATE k1_packages SET status = 'superseded' WHERE id = :p"),
                    {"p": latest.id},
                )
                await _event(tx, ctx.tenant_id, latest.id, "superseded", ctx.user_id)
        package_id = uuid4()
        await tx.session.execute(
            text(
                "INSERT INTO k1_packages (id, tenant_id, recipient_id, work_item_id, form, "
                "tax_year, period_start, period_end, status, k3_status, state_codes, "
                "is_final_set, source_import_id, supersedes_package_id, version_no) VALUES "
                "(:id, :t, :r, :w, :form, :year, :ps, :pe, 'draft', :k3, :states, :final, "
                ":src, :sup, :n)"
            ),
            {
                "id": package_id,
                "t": ctx.tenant_id,
                "r": recipient,
                "w": return_id,
                "form": found.form,
                "year": found.tax_year,
                "ps": found.period_start,
                "pe": found.period_end,
                "k3": r.k3_status,
                "states": list(r.states),
                "final": found.is_final,
                "src": sync_event_id,
                "sup": supersedes,
                "n": version_no,
            },
        )
        for d in r.documents:
            await tx.session.execute(
                text(
                    "INSERT INTO k1_documents (tenant_id, package_id, kind, jurisdiction, "
                    "evidence_version_id, is_draft) VALUES (:t, :p, :k, :j, :v, :draft)"
                ),
                {
                    "t": ctx.tenant_id,
                    "p": package_id,
                    "k": d.kind,
                    "j": d.jurisdiction,
                    "v": pdfs[d.file_name],
                    "draft": not found.is_final,
                },
            )
        for position, line in enumerate(r.lines):
            await tx.session.execute(
                text(
                    "INSERT INTO k1_box_lines (tenant_id, package_id, document_kind, box_code, "
                    "description, amount, is_total, position) VALUES (:t, :p, :dk, :code, "
                    ":desc, :amount, :total, :pos)"
                ),
                {
                    "t": ctx.tenant_id,
                    "p": package_id,
                    "dk": line.document_kind,
                    "code": line.box_code,
                    "desc": line.description,
                    "amount": line.amount,
                    "total": line.is_total,
                    "pos": position,
                },
            )
        await _event(
            tx,
            ctx.tenant_id,
            package_id,
            "imported",
            ctx.user_id,
            {"version_no": version_no, "final": found.is_final},
        )
        made += 1
    tx.record(
        "schedule_k_set.imported",
        target=Target(KIND, return_id),
        after=Ref(event=sync_event_id, packages=made, final=int(found.is_final)),
    )
    tx.emit(
        K1SetImported(
            work_item_id=return_id,
            sync_event_id=sync_event_id,
            packages=made,
            is_final=found.is_final,
        )
    )
    return made


async def import_k1_set(ctx: AuthContext, return_id: UUID, file_name: str, content: bytes) -> UUID:
    """The bridge's `k1_set` upload: parsed, stored write-once, applied; answers the sync event.
    The caller (`engine_import.import_file`) authorised `engine_import.create` on the return."""
    found = await _parsed(content)
    # T-02-T23 (DEC-1477): the manifest is JSON, which no upload type admits (DEC-58), so it is
    # not screened as a client upload. It was parsed in the isolated child above against the
    # strict schema (only its structured fields are kept, a full TIN refuses it); the bytes are
    # stored write-once and encrypted as the record of what the engine sent.
    stored = await stage_content(ctx.tenant_id, content)
    name = "".join(c for c in file_name.rsplit("/", 1)[-1] if c.isprintable())[:200] or "k1_set"
    async with uow(ctx.tenant) as tx:
        link = await repo.link_of(tx.session, return_id)
        if link is not None and link.engine_return_id != found.engine_return_id:
            from abacus.modules.tax.engine_import import EngineReturnMismatch

            raise EngineReturnMismatch(facts={"work_item_id": str(return_id)})
        event_id = await repo.insert_event(
            tx.session,
            {
                "tenant_id": ctx.tenant_id,
                "return_id": return_id,
                "engine_return_id": found.engine_return_id,
                "actor_user_id": ctx.user_id,
                "file_name": name,
                "file_key": stored.key,
                "file_version": stored.version_id,
                "file_size": stored.size,
                "payload_sha256": hashlib.sha256(content).hexdigest(),
                "kind": "k1_set",
                "version": found.version,
                "summary": {
                    "recipients": len(found.recipients),
                    "is_final": found.is_final,
                },
            },
        )
        await apply_k1_set(tx, ctx, return_id, found, event_id)
    return event_id


# --- reads ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Issuer:
    return_id: UUID
    engagement_id: UUID
    client_id: UUID
    client_name: str
    resource: Resource


async def _issuer(ctx: AuthContext, return_id: UUID, action: str) -> Issuer:
    if ctx.client:
        raise NotFound("k1_package")
    facts = next(
        (f for f in await work_item_facts(ctx, KIND) if f.work_item_id == return_id), None
    )
    if facts is None:
        raise NotFound(KIND)
    base = await engagement_resource(ctx.tenant, facts.engagement_id)
    resource = replace(base, work_item_id=return_id)
    await authorise(ctx, action, resource)
    return Issuer(return_id, facts.engagement_id, facts.client_id, facts.client_name, resource)


async def issuer_for(ctx: AuthContext, return_id: UUID, action: str) -> Issuer:
    """The issuing return as `_issuer` reads it, for T21's release (`tax/k1_release.py`)."""
    return await _issuer(ctx, return_id, action)


async def record_event(
    tx: UnitOfWork,
    tenant_id: UUID,
    package_id: UUID,
    kind: str,
    actor: UUID | None,
    facts: Mapping[str, object] | None = None,
) -> None:
    """A `k1_package_events` row (T21's release writes `released` as the system)."""
    await _event(tx, tenant_id, package_id, kind, actor, facts)


async def package_return_scope(tenant: TenantContext, return_id: UUID) -> ScopeFacts | None:
    """The issuing return inside its engagement and client (POR-13's access events)."""
    return await resolve_scope(tenant, "work_item", return_id)


async def package_scope(tenant: TenantContext, package_id: UUID) -> ScopeFacts | None:
    """A `k1_package` grant's scope (DEC-34): the issuing return inside its engagement and
    client. The grant reaches that one package only: the portal reads check the grant's own
    package (own-only, T-02-T26), never the return."""
    async with tenant_session(tenant) as session:
        work_item = await session.scalar(
            text("SELECT work_item_id FROM k1_packages WHERE id = :p"), {"p": package_id}
        )
    if work_item is None:
        return None
    return await resolve_scope(tenant, "work_item", cast(UUID, work_item))


@dataclass(frozen=True)
class DocumentView:
    id: UUID
    kind: str
    jurisdiction: str | None
    evidence_version_id: UUID
    is_draft: bool


@dataclass(frozen=True)
class LineView:
    document_kind: str
    box_code: str
    description: str
    amount: Decimal
    is_total: bool


@dataclass(frozen=True)
class HandoffView:
    """A row's internal hand-off (TXP-12's column); the target only for a reader of it
    (DEC-88)."""

    target_return_id: UUID | None
    target_name: str
    target_form: str | None
    status: str
    shared_at: object
    replaced_at: object


@dataclass(frozen=True)
class RelatedReturn:
    """A return of the recipient's own client for the same year, readable by the caller: a
    share target (TXP-12's Share draft internally…)."""

    return_id: UUID
    client_name: str
    form: str
    status: str


@dataclass(frozen=True)
class ChangeTag:
    """A pending recipient-details change, the row's second line (DV-10)."""

    id: UUID
    kind: str
    submitted_at: object


@dataclass(frozen=True)
class PackageView:
    id: UUID
    recipient_id: UUID
    recipient_name: str
    recipient_kind: str
    form: str
    tax_year: int
    status: str
    k3_status: str
    state_codes: tuple[str, ...]
    released_at: object
    version_no: int
    allowed_actions: tuple[str, ...]
    documents: tuple[DocumentView, ...] = ()
    lines: tuple[LineView, ...] = ()
    # T-02-T25 (additive; firm rows only, the portal leaves them empty): TXP-12's row lines.
    period_start: date | None = None
    period_end: date | None = None
    ownership_note: str | None = None
    locality: str | None = None
    delivery_contact_name: str | None = None
    supersedes_package_id: UUID | None = None
    handoffs: tuple[HandoffView, ...] = ()
    details_change: ChangeTag | None = None
    related_returns: tuple[RelatedReturn, ...] = ()
    tin_kind: str | None = None
    tin_last4: str | None = None


_PACKAGES = text(
    "SELECT p.id, p.recipient_id, r.display_name, r.recipient_kind, p.form, p.tax_year, "
    "p.status, p.k3_status, p.state_codes, p.released_at, p.version_no, p.period_start, "
    "p.period_end, r.ownership_note, r.address ->> 'city' AS city, "
    "r.address ->> 'state' AS state, coalesce(p.delivery_contact_id, r.contact_id) AS contact, "
    "p.supersedes_package_id, r.client_entity_id FROM k1_packages p "
    "JOIN k1_recipients r ON r.id = p.recipient_id "
    "WHERE p.work_item_id = :w ORDER BY r.display_name, p.version_no DESC"
)


def _locality(city: str | None, state: str | None) -> str | None:
    parts = [x for x in (city, state) if x]
    return ", ".join(parts) or None


async def _handoffs(
    ctx: AuthContext, session: AsyncSession, ids: Sequence[UUID]
) -> dict[UUID, list[HandoffView]]:
    """Each package's hand-offs to other returns; a target the reader cannot read is "Another
    return" with no link (DEC-88)."""
    if not ids:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT h.package_id, h.target_work_item_id, h.status, h.shared_at, "
                "h.replaced_at, t.form FROM k1_handoffs h LEFT JOIN tax_returns t "
                "ON t.work_item_id = h.target_work_item_id WHERE h.package_id = ANY(:ids) "
                "AND h.status <> 'withdrawn' ORDER BY h.shared_at, h.id"
            ),
            {"ids": list(ids)},
        )
    ).all()
    if not rows:
        return {}
    visible = {f.work_item_id: f.client_name for f in await work_item_facts(ctx, KIND)}
    out: dict[UUID, list[HandoffView]] = {}
    for r in rows:
        target = cast(UUID, r.target_work_item_id)
        seen = target in visible
        out.setdefault(r.package_id, []).append(
            HandoffView(
                target if seen else None,
                visible[target] if seen else "Another return",
                cast(str | None, r.form) if seen else None,
                r.status,
                r.shared_at,
                r.replaced_at,
            )
        )
    return out


async def _related(
    ctx: AuthContext,
    session: AsyncSession,
    return_id: UUID,
    tax_year: int,
    entities: Sequence[UUID],
) -> dict[UUID, list[RelatedReturn]]:
    """Each recipient entity's own returns for `tax_year` that the caller reads, the issuing
    return aside (DEC-88: a target is offered only to a reader of both)."""
    if not entities:
        return {}
    clients = {e: await client_of_entity(ctx.tenant, e) for e in entities}
    wanted = {c for c in clients.values() if c is not None}
    if not wanted:
        return {}
    facts = [
        f
        for f in await work_item_facts(ctx, KIND)
        if f.client_id in wanted and f.work_item_id != return_id
    ]
    if not facts:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT work_item_id, form, status FROM tax_returns "
                "WHERE work_item_id = ANY(:ids) AND tax_year = :y"
            ),
            {"ids": [f.work_item_id for f in facts], "y": tax_year},
        )
    ).all()
    found = {r.work_item_id: r for r in rows}
    out: dict[UUID, list[RelatedReturn]] = {}
    for entity, client in clients.items():
        for f in facts:
            row = found.get(f.work_item_id)
            if f.client_id == client and row is not None:
                out.setdefault(entity, []).append(
                    RelatedReturn(f.work_item_id, f.client_name, row.form, row.status)
                )
    return out


async def _pending_changes(
    session: AsyncSession, recipients: Sequence[UUID]
) -> dict[UUID, ChangeTag]:
    if not recipients:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT DISTINCT ON (recipient_id) id, recipient_id, kind, submitted_at "
                "FROM recipient_details_changes WHERE recipient_id = ANY(:ids) "
                "AND status = 'pending' ORDER BY recipient_id, submitted_at DESC, id"
            ),
            {"ids": list(recipients)},
        )
    ).all()
    return {r.recipient_id: ChangeTag(r.id, r.kind, r.submitted_at) for r in rows}


async def _documents(session: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, list[DocumentView]]:
    if not ids:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT id, package_id, kind, jurisdiction, evidence_version_id, is_draft "
                "FROM k1_documents WHERE package_id = ANY(:ids) ORDER BY created_at, id"
            ),
            {"ids": list(ids)},
        )
    ).all()
    out: dict[UUID, list[DocumentView]] = {}
    for r in rows:
        out.setdefault(r.package_id, []).append(
            DocumentView(r.id, r.kind, r.jurisdiction, r.evidence_version_id, r.is_draft)
        )
    return out


async def packages_of(
    ctx: AuthContext, return_id: UUID
) -> tuple[list[PackageView], dict[str, int]]:
    """TXP-12: the return's packages, newest version per recipient first in the list, with the
    tiles' counts by status and each row's documents (the expanded row)."""
    issuer = await _issuer(ctx, return_id, READ)
    may = await allowed_actions(ctx, issuer.resource, (SHARE, RESEND, REVIEW))
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                _PACKAGES,
                {"w": return_id},
            )
        ).all()
        docs = await _documents(session, [r.id for r in rows])
        handoffs = await _handoffs(ctx, session, [r.id for r in rows])
        changes = await _pending_changes(session, list({r.recipient_id for r in rows}))
        related = await _related(
            ctx,
            session,
            return_id,
            int(rows[0].tax_year) if rows else 0,
            list({cast(UUID, r.client_entity_id) for r in rows if r.client_entity_id}),
        )
        found = await contact_facts(
            session, list({cast(UUID, r.contact) for r in rows if r.contact is not None})
        )
    # A delivery contact is named only when its client is the issuer's or one the reader sees
    # (walls, INV-3): a walled client's contact leaves no name behind.
    seen = {f.client_id for f in await work_item_facts(ctx, KIND)} | {issuer.client_id}
    contacts = {cid: c for cid, c in found.items() if c.client_id in seen}
    out: list[PackageView] = []
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.status] = counts.get(r.status, 0) + 1
        mine = [a for a in may if a != RESEND or r.status in RELEASED]
        out.append(
            PackageView(
                r.id,
                r.recipient_id,
                r.display_name,
                r.recipient_kind,
                r.form,
                int(r.tax_year),
                r.status,
                r.k3_status,
                tuple(r.state_codes or ()),
                r.released_at,
                int(r.version_no),
                tuple(sorted(mine)),
                tuple(docs.get(r.id, [])),
                period_start=r.period_start,
                period_end=r.period_end,
                ownership_note=r.ownership_note,
                locality=_locality(r.city, r.state),
                delivery_contact_name=(
                    contacts[r.contact].display_name if r.contact in contacts else None
                ),
                supersedes_package_id=r.supersedes_package_id,
                handoffs=tuple(handoffs.get(r.id, [])),
                details_change=changes.get(r.recipient_id),
                related_returns=tuple(related.get(r.client_entity_id, ()))
                if r.client_entity_id
                else (),
            )
        )
    return out, counts


async def _package_return(ctx: AuthContext, package_id: UUID) -> UUID:
    if ctx.client:
        raise NotFound("k1_package")
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text("SELECT work_item_id FROM k1_packages WHERE id = :p"), {"p": package_id}
        )
    if found is None:
        raise NotFound("k1_package")
    return cast(UUID, found)


async def package(ctx: AuthContext, package_id: UUID) -> PackageView:
    """A package with its documents and, for readers of the return's content, its box lines."""
    return_id = await _package_return(ctx, package_id)
    issuer = await _issuer(ctx, return_id, READ)
    content = CONTENT in await allowed_actions(ctx, issuer.resource, (CONTENT,))
    rows, _ = await packages_of(ctx, return_id)
    found = next((p for p in rows if p.id == package_id), None)
    if found is None:
        raise NotFound("k1_package")
    async with tenant_session(ctx.tenant) as session:
        tin = (
            await session.execute(
                text("SELECT tin_kind, tin_last4 FROM k1_recipients WHERE id = :r"),
                {"r": found.recipient_id},
            )
        ).one()
    # The masked TIN is the recipient detail's, never a list row's (ADR-031).
    found = replace(found, tin_kind=tin.tin_kind, tin_last4=tin.tin_last4)
    if not content:
        return found
    async with tenant_session(ctx.tenant) as session:
        lines = (
            await session.execute(
                text(
                    "SELECT document_kind, box_code, description, amount, is_total "
                    "FROM k1_box_lines WHERE package_id = :p ORDER BY document_kind, position"
                ),
                {"p": package_id},
            )
        ).all()
    return replace(
        found,
        lines=tuple(
            LineView(r.document_kind, r.box_code, r.description, r.amount, r.is_total)
            for r in lines
        ),
    )


async def k1_document(ctx: AuthContext, package_id: UUID, document_id: UUID) -> DocumentView:
    found = await package(ctx, package_id)
    doc = next((d for d in found.documents if d.id == document_id), None)
    if doc is None:
        raise NotFound("k1_document")
    return doc


@dataclass(frozen=True)
class ReleaseCheck:
    eligible: bool
    failing: tuple[str, ...]
    package_ids: tuple[UUID, ...]


async def release_check(ctx: AuthContext, return_id: UUID) -> ReleaseCheck:
    """The release check as codes: final approval recorded, a final set imported after it, and
    every current package a final, unreleased draft (codes: `not_final_approved`, `no_packages`,
    `final_k1s_missing`, `nothing_to_release`). T21 adds the firm's release condition."""
    await _issuer(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        status = await session.scalar(
            text("SELECT status FROM tax_returns WHERE work_item_id = :w"), {"w": return_id}
        )
        rows = (
            await session.execute(
                text(
                    "SELECT id, status, is_final_set FROM k1_packages WHERE work_item_id = :w "
                    "AND status <> 'superseded'"
                ),
                {"w": return_id},
            )
        ).all()
    failing: list[str] = []
    if status not in _APPROVED_STATUSES:
        failing.append("not_final_approved")
    if not rows:
        failing.append("no_packages")
    elif any(not r.is_final_set for r in rows):
        failing.append("final_k1s_missing")
    ready = tuple(r.id for r in rows if r.status == "draft" and r.is_final_set)
    if rows and not ready:
        failing.append("nothing_to_release")
    return ReleaseCheck(not failing, tuple(failing), ready)


# --- sharing internally -----------------------------------------------------------------------


async def share_internal(
    ctx: AuthContext, return_id: UUID, package_ids: Sequence[UUID], target_ids: Sequence[UUID]
) -> int:
    """Share this return's K-1s to other returns' intake (DEC-88); answers the hand-offs made."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(SHARE, "role")
    issuer = await _issuer(ctx, return_id, SHARE)
    targets: dict[UUID, Issuer] = {}
    for target in dict.fromkeys(target_ids):
        if target == return_id:
            raise K1NotShareable(facts={"reason": "same_return"})
        try:
            # DEC-88: the sharer reads both returns; a wall on either side hides the target.
            targets[target] = await _issuer(ctx, target, CONTENT)
        except (Forbidden, NotFound):
            raise NotFound(KIND) from None
    shared = 0
    async with uow(ctx.tenant) as tx:
        rows = (
            await tx.session.execute(
                text(
                    "SELECT p.id, p.status, r.display_name FROM k1_packages p JOIN "
                    "k1_recipients r ON r.id = p.recipient_id WHERE p.id = ANY(:ids) "
                    "AND p.work_item_id = :w FOR UPDATE OF p"
                ),
                {"ids": list(package_ids), "w": return_id},
            )
        ).all()
        if len(rows) != len(set(package_ids)):
            raise NotFound("k1_package")
        for row in rows:
            if row.status not in ("draft", *RELEASED):
                raise K1NotShareable(facts={"status": row.status})
            k1 = await tx.session.scalar(
                text(
                    "SELECT evidence_version_id FROM k1_documents WHERE package_id = :p "
                    "AND kind = 'k1' ORDER BY created_at DESC LIMIT 1"
                ),
                {"p": row.id},
            )
            for target_id, target in targets.items():
                added = await tx.session.scalar(
                    text(
                        "INSERT INTO k1_handoffs (tenant_id, package_id, target_work_item_id, "
                        "shared_by) VALUES (:t, :p, :w, :by) ON CONFLICT (tenant_id, "
                        "package_id, target_work_item_id) DO NOTHING RETURNING id"
                    ),
                    {"t": ctx.tenant_id, "p": row.id, "w": target_id, "by": ctx.user_id},
                )
                if added is None:
                    continue
                copy: UUID | None = None
                request: UUID | None = None
                if k1 is not None:
                    copy = await file_handoff_copy(
                        tx,
                        source_version_id=cast(UUID, k1),
                        tenant_id=ctx.tenant_id,
                        client_id=target.client_id,
                        engagement_id=target.engagement_id,
                        work_item_id=target_id,
                        title=f"Schedule K-1 · {issuer.client_name}",
                        actor_id=str(ctx.user_id),
                    )
                    request = await k1_request_for(ctx.tenant, target_id, issuer.client_name)
                    if request is not None:
                        await fulfil_by_rule(
                            tx, ctx, request_item_id=request, evidence_version_id=copy
                        )
                await tx.session.execute(
                    text(
                        "UPDATE k1_handoffs SET target_evidence_version_id = :v, "
                        "target_request_item_id = :q WHERE id = :h"
                    ),
                    {"v": copy, "q": request, "h": added},
                )
                await _event(
                    tx, ctx.tenant_id, row.id, "shared_internal", ctx.user_id, {"handoff": added}
                )
                tx.record(
                    "schedule_k_package.shared_internal",
                    target=Target(KIND, return_id),
                    after=Ref(package=row.id, handoff=cast(UUID, added), target=target_id),
                )
                shared += 1
    return shared


# --- the final-approval dependency (T-01's blocker slot) -------------------------------------


async def draft_k1_blockers(tenant: TenantContext, return_id: UUID) -> list[Blocker]:
    """A K-1 shared to this return as a draft blocks its final approval until released (DV-4)."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT package_id FROM k1_handoffs WHERE target_work_item_id = :w "
                    "AND status = 'draft_shared' ORDER BY shared_at"
                ),
                {"w": return_id},
            )
        ).scalars()
        return [Blocker("draft_k1", ref_id=r) for r in rows]


@dataclass(frozen=True)
class Dependency:
    source_return_id: UUID | None  # None when the reader cannot read the issuing return
    issuer_name: str
    status: Literal["awaiting", "received"]
    blocking: bool


async def dependencies(ctx: AuthContext, return_id: UUID) -> list[Dependency]:
    """TAX-02's and TAX-03's K-1 dependency rows; the source link only for a reader of both
    returns (DEC-88)."""
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT h.status, p.work_item_id FROM k1_handoffs h JOIN k1_packages p "
                    "ON p.id = h.package_id WHERE h.target_work_item_id = :w "
                    "AND h.status <> 'withdrawn' ORDER BY h.shared_at"
                ),
                {"w": return_id},
            )
        ).all()
    if not rows:
        return []
    visible = {f.work_item_id: f.client_name for f in await work_item_facts(ctx, KIND)}
    out: list[Dependency] = []
    for r in rows:
        source = cast(UUID, r.work_item_id)
        seen = source in visible
        out.append(
            Dependency(
                source if seen else None,
                visible[source] if seen else "Another return",
                "received" if r.status == "final_replaced" else "awaiting",
                r.status == "draft_shared",
            )
        )
    return out


# --- resend and details changes ---------------------------------------------------------------


async def resend(ctx: AuthContext, package_id: UUID, contact_id: UUID) -> None:
    """Record the corrected contact and ask T21's workflow for a new invitation."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(RESEND, "role")
    return_id = await _package_return(ctx, package_id)
    await _issuer(ctx, return_id, RESEND)
    async with uow(ctx.tenant) as tx:
        status = await tx.session.scalar(
            text("SELECT status FROM k1_packages WHERE id = :p FOR UPDATE"), {"p": package_id}
        )
        if status not in RELEASED:
            raise K1NotReleased(facts={"status": str(status)})
        await tx.session.execute(
            text("UPDATE k1_packages SET delivery_contact_id = :c WHERE id = :p"),
            {"c": contact_id, "p": package_id},
        )
        await _event(tx, ctx.tenant_id, package_id, "resend_requested", ctx.user_id)
        tx.record(
            "schedule_k_package.resend_requested",
            target=Target(KIND, return_id),
            after=Ref(package=package_id, contact_id=contact_id),
        )
        tx.emit(
            K1ResendRequested(package_id=package_id, contact_id=contact_id, by_user=ctx.user_id)
        )


@dataclass(frozen=True)
class DetailsChange:
    id: UUID
    recipient_id: UUID
    kind: str
    status: str
    submitted_at: object
    evidence_version_id: UUID | None


async def _recipient_return(ctx: AuthContext, recipient_id: UUID) -> UUID:
    if ctx.client:
        raise NotFound("k1_recipient")
    async with tenant_session(ctx.tenant) as session:
        found = await session.scalar(
            text("SELECT work_item_id FROM k1_recipients WHERE id = :r"), {"r": recipient_id}
        )
    if found is None:
        raise NotFound("k1_recipient")
    return cast(UUID, found)


async def details_changes(ctx: AuthContext, recipient_id: UUID) -> list[DetailsChange]:
    await _issuer(ctx, await _recipient_return(ctx, recipient_id), REVIEW)
    return await details_changes_of(ctx.tenant, recipient_id)


async def details_changes_of(tenant: TenantContext, recipient_id: UUID) -> list[DetailsChange]:
    """A recipient's details changes, newest first, for a caller that checked its own access
    (the firm's review above; the recipient's own package in POR-13, T-02-T26)."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, recipient_id, kind, status, submitted_at, evidence_version_id "
                    "FROM recipient_details_changes WHERE recipient_id = :r "
                    "ORDER BY submitted_at DESC"
                ),
                {"r": recipient_id},
            )
        ).all()
    return [DetailsChange(*r) for r in rows]


async def decide_details_change(
    ctx: AuthContext, change_id: UUID, accept: bool, reason: str | None
) -> DetailsChange:
    """DV-10: a person accepts or rejects, once; the firm applies an accepted change in CCH."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(REVIEW, "role")
    async with tenant_session(ctx.tenant) as session:
        recipient = await session.scalar(
            text("SELECT recipient_id FROM recipient_details_changes WHERE id = :c"),
            {"c": change_id},
        )
    if recipient is None or ctx.client:
        raise NotFound("recipient_details_change")
    issuing = await _recipient_return(ctx, cast(UUID, recipient))
    await _issuer(ctx, issuing, REVIEW)
    async with uow(ctx.tenant) as tx:
        changed = await tx.session.scalar(
            text(
                "UPDATE recipient_details_changes SET status = :s, decided_by = :by, "
                "decided_at = :at, reason = :reason WHERE id = :c AND status = 'pending' "
                "RETURNING id"
            ),
            {
                "s": "accepted" if accept else "rejected",
                "by": ctx.user_id,
                "at": await now(ctx.tenant),
                "reason": reason,
                "c": change_id,
            },
        )
        if changed is None:
            raise DetailsChangeDecided(facts={"change_id": str(change_id)})
        tx.record(
            "recipient_details_change.accepted" if accept else "recipient_details_change.rejected",
            target=Target(KIND, issuing),
            after=Ref(recipient=cast(UUID, recipient), change=change_id),
        )
    found = next(c for c in await details_changes(ctx, cast(UUID, recipient)) if c.id == change_id)
    return found


__all__ = [
    "Dependency",
    "DetailsChange",
    "K1Set",
    "PackageView",
    "ReleaseCheck",
    "apply_k1_set",
    "decide_details_change",
    "dependencies",
    "details_changes",
    "draft_k1_blockers",
    "import_k1_set",
    "k1_document",
    "package",
    "packages_of",
    "parse_k1_set",
    "release_check",
    "resend",
    "share_internal",
]
