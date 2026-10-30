"""SIG-02's builder service: drafts, edits, checks, Send and Undo (N-02-T20; N-02 §3.4; SPEC-381;
DEC-24, DEC-1178; P-35).

- **Draft.** `POST /v1/envelopes {source_kind, source_id}`: the registered source prefills the
  documents, signers, gate and retention record type (`sources.SourceDraft`); an unregistered
  kind is 409 `unknown_envelope_source`, a source that can't draft yet 409
  `source_cannot_draft`. The agent and the system may draft (the matrix's one verb for them);
  nothing else.
- **Edit.** `PUT` with `If-Match: <version>` (409 `stale_version` otherwise) on a draft no one has
  pressed Send on (409 `envelope_not_draft`). Signers are matched by party: a kept signer keeps
  its id and placed fields, a removed one loses both, a new one is added. A contact signer must be
  the envelope's client's (422 `signer_outside_client`); an identity method the policy does not
  allow is 422 `identity_method_not_allowed` (DF-11: never SMS, KBA for the e-file family only).
- **Checks** (`POST validate`), computed by code, never a model (INV-1): signers present, every
  signer's email on file, identity methods allowed, signer authority (a client's contact signs, a
  firm member countersigns or is the ERO), the ERO named for an e-file authorization, no SSN or
  ITIN on a signer-visible page (P-03's scan; unscanned is not clear), and the source's own checks
  (amounts match, the firm's e-file identifiers). Problems are identifiers
  (`signer_email_missing:<signer_id>`).
- **Send.** A person's own live session (never an agent, the platform or support), an
  `Idempotency-Key`, the checks passing (else 409 `validation_failed` with each check in
  `facts`), then an approval grant with `not_before = now + 10 s` bound to the held
  `envelope.send_approved` event. The envelope records who sent it and when; the outbox relay
  consumes the grant after the window and its subscriber starts EnvelopeWorkflow, the only
  caller of the provider (N-02-T18). **Undo** inside the window voids the grant, clears the send
  and writes `envelope.send_undone`: no provider call is ever made.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel import clock
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, audit_of_targets, event_sha256, uow
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import tin_exposure, viewer_page
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    contact_emails,
    issue_grant,
    void_grant,
)
from abacus.modules.organisations.api import signer_contacts
from abacus.modules.signatures.events import EnvelopeSendApproved
from abacus.modules.signatures.hub import firm_and_flag, resource_of, visible_head
from abacus.modules.signatures.sources import SourceDraft, envelope_source

DRAFT: Final = "envelope.draft"
SEND: Final = "envelope.send"
UNDO_WINDOW: Final = timedelta(seconds=10)
GRANT_LIFETIME: Final = timedelta(days=1)
# The provider a live envelope is meant for (ADR-342, which replaced DocuSign); the adapter in use
# is configured per environment (the fake in tests and demo) and W7 opens per firm (N-02-T18).
DRAFT_PROVIDER: Final = "docuseal"
# DF-11: who may verify how, by policy family, when the firm has no policy row for it.
_DEFAULT_METHODS: Final[dict[str, frozenset[str]]] = {
    "efile_authorization": frozenset({"kba", "in_person_id", "firm_sso"}),
    "engagement_letter": frozenset({"email_code", "in_person_id", "firm_sso"}),
    "consent": frozenset({"email_code", "in_person_id", "firm_sso"}),
    "general": frozenset({"email_code", "in_person_id", "firm_sso"}),
}
# A firm member signs through the firm's sign-in; a client never does.
_FIRM_ONLY: Final = frozenset({"firm_sso"})
_KBA_FAMILY: Final = "efile_authorization"
CHECK_ORDER: Final = (
    "signers_present",
    "emails_present",
    "identity_allowed",
    "signer_authority",
    "ero_present",
    "no_ssn_visible",
    "source_checks",
)


class SourceCannotDraft(DomainConflict):
    """The source is registered but drafts nothing yet (the letter until N-02-T32)."""

    code = "source_cannot_draft"


class EnvelopeNotDraft(DomainConflict):
    """Only a draft no one has pressed Send on is edited, checked for sending or sent."""

    code = "envelope_not_draft"


class StaleEnvelope(DomainConflict):
    """`If-Match` names an older version: someone else saved first."""

    code = "stale_version"


class ValidationFailed(DomainConflict):
    """A code-computed check failed; `facts` holds each check's result by its code."""

    code = "validation_failed"


class IdentityMethodNotAllowed(DomainInvalid):
    """The policy does not allow this identity method for this signer (DF-11)."""

    code = "identity_method_not_allowed"


class SignerOutsideClient(DomainInvalid):
    """A contact signer must be the envelope's client's, and a party is named exactly once."""

    code = "signer_outside_client"


class DocumentOrderInvalid(DomainInvalid):
    """A new document order must name every document of the envelope exactly once."""

    code = "document_order_invalid"


class PreviewUnavailable(DomainConflict):
    """The document has no rendered preview to show yet (a generated document until P-11)."""

    code = "preview_unavailable"


class UndoWindowClosed(DomainConflict):
    """More than 10 seconds after Send, or not this person's send."""

    code = "undo_window_closed"


class EffectStarted(DomainConflict):
    """The send's grant was already used: the provider has the envelope."""

    code = "effect_started"


@dataclass(frozen=True)
class SignerEdit:
    order: int
    routing_group: int
    contact_id: UUID | None
    user_id: UUID | None
    role: str
    identity_method: str


@dataclass(frozen=True)
class FieldEdit:
    """N-02-T30: a placed field; `signer_index` names the edit's signer by position."""

    document_id: UUID
    signer_index: int
    kind: str
    page: int
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class DraftEdit:
    signers: tuple[SignerEdit, ...]
    signer_order: str
    message: str | None
    reminder_cadence: str | None
    expires_on: date | None
    date_as_of_mode: str
    date_as_of: date | None
    document_order: tuple[UUID, ...] | None
    fields: tuple[FieldEdit, ...] | None = None


@dataclass(frozen=True)
class Check:
    code: str
    ok: bool


@dataclass(frozen=True)
class CheckReport:
    ok: bool
    problems: tuple[str, ...]
    checks: tuple[Check, ...]


@dataclass(frozen=True)
class Sent:
    envelope_id: UUID
    grant_id: UUID
    not_before: datetime


def _drafter(ctx: AuthContext) -> tuple[str, UUID | None, UUID | None]:
    """Who drafts: a person, the agent (its run) or the system."""
    kind = ctx.tenant.actor_kind
    if kind == "human":
        return "human", ctx.user_id, None
    if kind == "agent":
        run = ctx.tenant.actor_id.rsplit(":", 1)[-1]  # `agent:<agent>:<run>`
        return "agent", None, UUID(run)
    return "system", None, None


def _human(ctx: AuthContext) -> None:
    """INV-1: Send and Undo are a person's own decision in a live session."""
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(SEND, "role")


async def _draft_resource(ctx: AuthContext, draft: SourceDraft) -> Resource:
    if draft.engagement_id is not None:
        return (await get_ref(ctx, draft.engagement_id)).resource()
    return Resource.client(ctx.tenant_id, draft.client_id)


async def _allowed_methods(session: AsyncSession, family: str, purpose: str) -> frozenset[str]:
    """The firm's policy for the purpose, else for the family, else DF-11's defaults."""
    found = (
        await session.execute(
            text(
                "SELECT allowed_identity_methods FROM envelope_policies "
                "WHERE policy_family = :family AND (purpose = :purpose OR purpose IS NULL) "
                "ORDER BY purpose NULLS LAST LIMIT 1"
            ),
            {"family": family, "purpose": purpose},
        )
    ).scalar_one_or_none()
    allowed = frozenset(found) if found else _DEFAULT_METHODS[family]
    if family != _KBA_FAMILY:
        allowed -= {"kba"}
    return allowed | _FIRM_ONLY


def _method_ok(allowed: frozenset[str], party_is_user: bool, method: str) -> bool:
    if party_is_user:
        return method in _FIRM_ONLY
    return method in allowed - _FIRM_ONLY


async def _number(tx: UnitOfWork, tenant_id: UUID) -> int:
    await tx.session.execute(
        text(
            "INSERT INTO envelope_numbers (tenant_id) VALUES (:tenant) "
            "ON CONFLICT (tenant_id) DO NOTHING"
        ),
        {"tenant": tenant_id},
    )
    return int(
        (
            await tx.session.execute(
                text(
                    "UPDATE envelope_numbers SET next_value = next_value + 1 "
                    "RETURNING next_value - 1"
                )
            )
        ).scalar_one()
    )


async def _event(tx: UnitOfWork, tenant_id: UUID, envelope_id: UUID, kind: str) -> None:
    await tx.session.execute(
        text(
            "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, occurred_at) "
            "VALUES (:tenant, :id, :kind, 'firm', clock_timestamp())"
        ),
        {"tenant": tenant_id, "id": envelope_id, "kind": kind},
    )


# --- Draft ---------------------------------------------------------------------------------------


async def create_draft(ctx: AuthContext, source_kind: str, source_id: UUID) -> UUID:
    """`POST /v1/envelopes`: a draft prefilled by its registered source."""
    await firm_and_flag(ctx)
    source = envelope_source(source_kind)
    if source.draft is None:
        raise SourceCannotDraft(facts={"kind": source_kind})
    draft = await source.draft(ctx, source_id)
    await authorise(ctx, DRAFT, await _draft_resource(ctx, draft))
    kind, by, run = _drafter(ctx)
    envelope_id = uuid4()
    async with uow(ctx.tenant) as tx:
        allowed = await _allowed_methods(tx.session, draft.policy_family, draft.purpose)
        for signer in draft.signers:
            if not _method_ok(allowed, signer.user_id is not None, signer.identity_method):
                raise IdentityMethodNotAllowed(facts={"method": signer.identity_method})
        number = await _number(tx, ctx.tenant_id)
        await tx.session.execute(
            text(
                "INSERT INTO envelopes (id, tenant_id, number, purpose, form_code, "
                "policy_family, source_kind, source_id, client_id, engagement_id, work_item_id, "
                "title, provider, signer_order, retention_record_type, gate_kind, "
                "gate_target_ref, drafted_by_kind, drafted_by, drafted_via_run_id) VALUES (:id, "
                ":tenant, :number, :purpose, :form, :family, :source_kind, :source_id, :client, "
                ":engagement, :work_item, :title, :provider, :order, :record_type, :gate, "
                ":gate_target, :kind, :by, :run)"
            ),
            {
                "id": envelope_id,
                "tenant": ctx.tenant_id,
                "number": number,
                "purpose": draft.purpose,
                "form": draft.form_code,
                "family": draft.policy_family,
                "source_kind": source_kind,
                "source_id": source_id,
                "client": draft.client_id,
                "engagement": draft.engagement_id,
                "work_item": draft.work_item_id,
                "title": draft.title,
                "provider": DRAFT_PROVIDER,
                "order": draft.signer_order,
                "record_type": source.retention_record_type,
                "gate": source.gate,
                "gate_target": draft.engagement_id if source.gate else None,
                "kind": kind,
                "by": by,
                "run": run,
            },
        )
        for n, doc in enumerate(draft.documents, start=1):
            await tx.session.execute(
                text(
                    'INSERT INTO envelope_documents (tenant_id, envelope_id, "order", '
                    "evidence_version_id, generated_document_version_id, sha256, page_count, "
                    "signer_visible, read_only, watermark, source_ref, placement, tri) VALUES "
                    "(:tenant, :id, :n, :version, :generated, :sha, :pages, :visible, :read_only, "
                    ":watermark, :ref, :placement, :tri)"
                ),
                {
                    "tenant": ctx.tenant_id,
                    "id": envelope_id,
                    "n": n,
                    "version": doc.evidence_version_id,
                    "generated": doc.generated_document_version_id,
                    "sha": doc.sha256,
                    "pages": doc.page_count,
                    "visible": doc.signer_visible,
                    "read_only": doc.read_only,
                    "watermark": doc.watermark,
                    "ref": doc.source_ref,
                    "placement": doc.placement,
                    "tri": doc.tri,
                },
            )
        for n, signer in enumerate(draft.signers, start=1):
            await _insert_signer(
                tx,
                ctx.tenant_id,
                envelope_id,
                SignerEdit(
                    n,
                    signer.routing_group,
                    signer.contact_id,
                    signer.user_id,
                    signer.role,
                    signer.identity_method,
                ),
            )
        await _event(tx, ctx.tenant_id, envelope_id, "envelope.drafted")
        tx.record(
            "envelope.drafted",
            target=Target("envelope", envelope_id),
            after=Ref(number=number, documents=len(draft.documents), signers=len(draft.signers)),
        )
    return envelope_id


async def _insert_signer(
    tx: UnitOfWork, tenant_id: UUID, envelope_id: UUID, signer: SignerEdit
) -> None:
    await tx.session.execute(
        text(
            'INSERT INTO envelope_signers (tenant_id, envelope_id, "order", routing_group, '
            "party_kind, contact_id, user_id, role, identity_method) VALUES (:tenant, :id, "
            ":order, :group, :party, :contact, :user, :role, :method)"
        ),
        {
            "tenant": tenant_id,
            "id": envelope_id,
            "order": signer.order,
            "group": signer.routing_group,
            "party": "user" if signer.user_id is not None else "contact",
            "contact": signer.contact_id,
            "user": signer.user_id,
            "role": signer.role,
            "method": signer.identity_method,
        },
    )


# --- Edit ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Locked:
    status: str
    sent_at: datetime | None
    client_id: UUID
    policy_family: str
    purpose: str
    version: int


async def _lock(tx: UnitOfWork, envelope_id: UUID) -> _Locked:
    row = (
        await tx.session.execute(
            text(
                "SELECT status, sent_at, client_id, policy_family, purpose, version "
                "FROM envelopes WHERE id = :id FOR UPDATE"
            ),
            {"id": envelope_id},
        )
    ).one()
    return _Locked(
        row.status, row.sent_at, row.client_id, row.policy_family, row.purpose, row.version
    )


def _version_of(if_match: str) -> int | None:
    raw = if_match.strip().removeprefix("W/").strip('"')
    return int(raw) if raw.isdigit() else None


async def update_draft(
    ctx: AuthContext, envelope_id: UUID, edit: DraftEdit, if_match: str
) -> None:
    """`PUT /v1/envelopes/{id}`: SIG-02's edits to a draft, at the version the person saw."""
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
    await authorise(ctx, DRAFT, await resource_of(ctx, head))
    parties = [(s.contact_id, s.user_id) for s in edit.signers]
    if any((c is None) == (u is None) for c, u in parties) or len(set(parties)) != len(parties):
        raise SignerOutsideClient(facts={"reason": "party"})
    if edit.date_as_of_mode == "fixed_date" and edit.date_as_of is None:
        raise DomainInvalid(facts={"field": "date_as_of"})
    contacts = await signer_contacts(
        ctx.tenant, [s.contact_id for s in edit.signers if s.contact_id is not None]
    )
    async with uow(ctx.tenant) as tx:
        locked = await _lock(tx, envelope_id)
        if _version_of(if_match) != locked.version:
            raise StaleEnvelope(facts={"version": locked.version})
        if locked.status != "draft" or locked.sent_at is not None:
            raise EnvelopeNotDraft(facts={"status": locked.status})
        for signer in edit.signers:
            if signer.contact_id is not None and (
                signer.contact_id not in contacts
                or contacts[signer.contact_id].client_id != locked.client_id
            ):
                raise SignerOutsideClient(facts={"contact_id": str(signer.contact_id)})
        allowed = await _allowed_methods(tx.session, locked.policy_family, locked.purpose)
        for signer in edit.signers:
            if not _method_ok(allowed, signer.user_id is not None, signer.identity_method):
                raise IdentityMethodNotAllowed(facts={"method": signer.identity_method})
        await _replace_signers(tx, ctx.tenant_id, envelope_id, edit.signers)
        if edit.fields is not None:
            await _replace_fields(tx, ctx.tenant_id, envelope_id, edit)
        if edit.document_order is not None:
            await _reorder_documents(tx, envelope_id, edit.document_order)
        expires_at = (
            datetime.combine(edit.expires_on, time(23, 59, 59), UTC)
            if edit.expires_on is not None
            else None
        )
        version = (
            await tx.session.execute(
                text(
                    "UPDATE envelopes SET signer_order = :order, message = :message, "
                    "reminder_cadence = :cadence, expires_at = :expires, "
                    "date_as_of_mode = :mode, date_as_of = :as_of, version = version + 1, "
                    "updated_at = clock_timestamp() WHERE id = :id RETURNING version"
                ),
                {
                    "order": edit.signer_order,
                    "message": edit.message,
                    "cadence": edit.reminder_cadence,
                    "expires": expires_at,
                    "mode": edit.date_as_of_mode,
                    "as_of": edit.date_as_of if edit.date_as_of_mode == "fixed_date" else None,
                    "id": envelope_id,
                },
            )
        ).scalar_one()
        await _event(tx, ctx.tenant_id, envelope_id, "envelope.edited")
        tx.record(
            "envelope.draft_saved",
            target=Target("envelope", envelope_id),
            after=Ref(version=int(version), signers=len(edit.signers)),
        )


async def _replace_fields(
    tx: UnitOfWork, tenant_id: UUID, envelope_id: UUID, edit: DraftEdit
) -> None:
    """N-02-T30: the draft's placed fields become exactly the ones sent. A field names one of
    the envelope's documents and one of the edit's signers (by position), else 422."""
    documents = set(
        (
            await tx.session.execute(
                text("SELECT id FROM envelope_documents WHERE envelope_id = :id"),
                {"id": envelope_id},
            )
        ).scalars()
    )
    signer_ids = list(
        (
            await tx.session.execute(
                text('SELECT id FROM envelope_signers WHERE envelope_id = :id ORDER BY "order"'),
                {"id": envelope_id},
            )
        ).scalars()
    )
    for f in edit.fields or ():
        if f.document_id not in documents or not 0 <= f.signer_index < len(signer_ids):
            raise DomainInvalid(facts={"field": "fields"})
    await tx.session.execute(
        text(
            "DELETE FROM envelope_fields WHERE envelope_document_id IN "
            "(SELECT id FROM envelope_documents WHERE envelope_id = :id)"
        ),
        {"id": envelope_id},
    )
    for f in edit.fields or ():
        await tx.session.execute(
            text(
                "INSERT INTO envelope_fields (tenant_id, envelope_document_id, signer_id, kind, "
                "page, x, y, w, h) VALUES (:t, :d, :s, :k, :p, :x, :y, :w, :h)"
            ),
            {
                "t": tenant_id,
                "d": f.document_id,
                "s": signer_ids[f.signer_index],
                "k": f.kind,
                "p": f.page,
                "x": f.x,
                "y": f.y,
                "w": f.w,
                "h": f.h,
            },
        )


async def _replace_signers(
    tx: UnitOfWork, tenant_id: UUID, envelope_id: UUID, wanted: Sequence[SignerEdit]
) -> None:
    """Kept parties keep their row (and fields); removed ones go with their fields; new ones
    join. The order unique is checked at commit (0405), so positions may swap."""
    rows = (
        await tx.session.execute(
            text("SELECT id, contact_id, user_id FROM envelope_signers WHERE envelope_id = :id"),
            {"id": envelope_id},
        )
    ).all()
    current = {(r.contact_id, r.user_id): r.id for r in rows}
    keep = {(s.contact_id, s.user_id) for s in wanted}
    gone = [signer_id for party, signer_id in current.items() if party not in keep]
    if gone:
        await tx.session.execute(
            text("DELETE FROM envelope_fields WHERE signer_id = ANY(:ids)"), {"ids": gone}
        )
        await tx.session.execute(
            text("DELETE FROM envelope_signers WHERE id = ANY(:ids)"), {"ids": gone}
        )
    for signer in wanted:
        signer_id = current.get((signer.contact_id, signer.user_id))
        if signer_id is None:
            await _insert_signer(tx, tenant_id, envelope_id, signer)
            continue
        await tx.session.execute(
            text(
                'UPDATE envelope_signers SET "order" = :order, routing_group = :group, '
                "role = :role, identity_method = :method WHERE id = :id"
            ),
            {
                "order": signer.order,
                "group": signer.routing_group,
                "role": signer.role,
                "method": signer.identity_method,
                "id": signer_id,
            },
        )


async def _reorder_documents(tx: UnitOfWork, envelope_id: UUID, order: Sequence[UUID]) -> None:
    ids = set(
        (
            await tx.session.execute(
                text("SELECT id FROM envelope_documents WHERE envelope_id = :id"),
                {"id": envelope_id},
            )
        ).scalars()
    )
    if len(order) != len(ids) or set(order) != ids:
        raise DocumentOrderInvalid
    for n, document_id in enumerate(order, start=1):
        await tx.session.execute(
            text('UPDATE envelope_documents SET "order" = :n WHERE id = :id'),
            {"n": n, "id": document_id},
        )


# --- Checks --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _SignerRow:
    id: UUID
    contact_id: UUID | None
    user_id: UUID | None
    role: str
    identity_method: str


async def _checks(ctx: AuthContext, envelope_id: UUID) -> CheckReport:
    async with tenant_session(ctx.tenant) as session:
        env = (
            await session.execute(
                text(
                    "SELECT client_id, policy_family, purpose, source_kind, source_id "
                    "FROM envelopes WHERE id = :id"
                ),
                {"id": envelope_id},
            )
        ).one()
        found = [
            _SignerRow(r.id, r.contact_id, r.user_id, r.role, r.identity_method)
            for r in (
                await session.execute(
                    text(
                        "SELECT id, contact_id, user_id, role, identity_method "
                        'FROM envelope_signers WHERE envelope_id = :id ORDER BY "order"'
                    ),
                    {"id": envelope_id},
                )
            ).all()
        ]
        visible_versions = list(
            (
                await session.execute(
                    text(
                        "SELECT evidence_version_id FROM envelope_documents WHERE envelope_id = "
                        ":id AND signer_visible AND evidence_version_id IS NOT NULL"
                    ),
                    {"id": envelope_id},
                )
            ).scalars()
        )
        allowed = await _allowed_methods(session, env.policy_family, env.purpose)
    contacts = await signer_contacts(
        ctx.tenant, [s.contact_id for s in found if s.contact_id is not None]
    )
    member_emails = await contact_emails([s.user_id for s in found if s.user_id is not None])
    problems: list[str] = []
    results: dict[str, bool] = {}

    def fail(check: str, problem: str) -> None:
        results[check] = False
        problems.append(problem)

    if not any(s.role == "signer" for s in found):
        fail("signers_present", "signer_missing")
    for s in found:
        email = (
            contacts[s.contact_id].email
            if s.contact_id is not None and s.contact_id in contacts
            else member_emails.get(s.user_id)
            if s.user_id is not None
            else None
        )
        if not email:
            fail("emails_present", f"signer_email_missing:{s.id}")
        if not _method_ok(allowed, s.user_id is not None, s.identity_method):
            fail("identity_allowed", f"identity_method_not_allowed:{s.id}")
        client_signer = (
            s.contact_id is not None
            and s.contact_id in contacts
            and contacts[s.contact_id].client_id == env.client_id
            and s.role == "signer"
        )
        firm_signer = s.user_id is not None and s.role in ("countersigner", "ero")
        if not (client_signer or firm_signer):
            fail("signer_authority", f"signer_authority:{s.id}")
    if env.policy_family == _KBA_FAMILY and not any(s.role == "ero" for s in found):
        fail("ero_present", "ero_missing")
    for version, exposure in (await tin_exposure(ctx.tenant, visible_versions)).items():
        if exposure == "tin_found":
            fail("no_ssn_visible", f"ssn_visible:{version}")
        elif exposure == "unchecked":
            fail("no_ssn_visible", f"pii_unchecked:{version}")
    if env.source_kind is not None:
        for check in envelope_source(env.source_kind).checks:
            for problem in await check(ctx, env.source_id):
                fail("source_checks", problem)
    checks = tuple(
        Check(code, results.get(code, True))
        for code in CHECK_ORDER
        if code != "ero_present" or env.policy_family == _KBA_FAMILY
    )
    return CheckReport(not problems, tuple(problems), checks)


async def validate(ctx: AuthContext, envelope_id: UUID) -> CheckReport:
    """`POST /v1/envelopes/{id}/validate`: the checks, for a person editing the draft."""
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
    await authorise(ctx, DRAFT, await resource_of(ctx, head))
    return await _checks(ctx, envelope_id)


# --- Send and Undo -------------------------------------------------------------------------------


async def check_send(ctx: AuthContext, envelope_id: UUID) -> None:
    """Who may send, before an idempotent replay answers (a replay runs nothing else)."""
    _human(ctx)
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
    await authorise(ctx, SEND, await resource_of(ctx, head))


async def send(ctx: AuthContext, envelope_id: UUID) -> Sent:
    """`POST /v1/envelopes/{id}/send`: the checks, then a grant that matures in 10 seconds."""
    _human(ctx)
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
    resource = await resource_of(ctx, head)
    await authorise(ctx, SEND, resource)
    checked = await _checks(ctx, envelope_id)
    if not checked.ok:
        raise ValidationFailed(facts={c.code: c.ok for c in checked.checks})
    async with uow(ctx.tenant) as tx:
        locked = await _lock(tx, envelope_id)
        if locked.status != "draft" or locked.sent_at is not None:
            raise EnvelopeNotDraft(facts={"status": locked.status})
        now = await clock.now(ctx.tenant)
        not_before = now + UNDO_WINDOW
        event = EnvelopeSendApproved(
            envelope_id=envelope_id,
            client_id=locked.client_id,
            engagement_id=head.engagement_id,
            sent_by=ctx.user_id,
            version=locked.version,
        )
        grant = await issue_grant(
            tx,
            ctx,
            action=SEND,
            resource=resource,
            subject=Target("envelope", envelope_id),
            payload_sha256=event_sha256(event),
            not_before=not_before,
            expires_at=not_before + GRANT_LIFETIME,
        )
        # The relay delivers this only after the window and only by consuming the grant; its
        # subscriber starts EnvelopeWorkflow (the provider's first call).
        tx.emit(event, not_before=not_before, grant_id=grant)
        await tx.session.execute(
            text(
                "UPDATE envelopes SET sent_by = :user, sent_at = :now, updated_at = :now "
                "WHERE id = :id"
            ),
            {"user": ctx.user_id, "now": now, "id": envelope_id},
        )
        await _event(tx, ctx.tenant_id, envelope_id, "envelope.send_requested")
        tx.record(
            "envelope.send_requested",
            target=Target("envelope", envelope_id),
            after=Ref(grant=grant, version=locked.version),
        )
    return Sent(envelope_id, grant, not_before)


async def undo_send(ctx: AuthContext, envelope_id: UUID) -> None:
    """`POST /v1/envelopes/{id}/send/undo`: inside 10 seconds, the sender's own send is undone
    and no provider call is made; later 409 `undo_window_closed`; once the grant was used 409
    `effect_started`."""
    _human(ctx)
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        head = await visible_head(ctx, session, envelope_id)
    await authorise(ctx, SEND, await resource_of(ctx, head))
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text("SELECT status, sent_by, sent_at FROM envelopes WHERE id = :id FOR UPDATE"),
                {"id": envelope_id},
            )
        ).one()
        now = await clock.now(ctx.tenant)
        if (
            row.status != "draft"
            or row.sent_at is None
            or row.sent_by != ctx.user_id
            or now >= row.sent_at + UNDO_WINDOW
        ):
            raise UndoWindowClosed
        sent = await audit_of_targets(
            tx.session, [("envelope", envelope_id)], None, 1, action="envelope.send_requested"
        )
        raw = sent[0].after_ref.get("grant") if sent and sent[0].after_ref else None
        grant = UUID(str(raw)) if raw else None
        if grant is None or not await void_grant(tx, grant):
            raise EffectStarted
        await tx.session.execute(
            text(
                "UPDATE envelopes SET sent_by = NULL, sent_at = NULL, updated_at = :now "
                "WHERE id = :id"
            ),
            {"now": now, "id": envelope_id},
        )
        await _event(tx, ctx.tenant_id, envelope_id, "envelope.send_undone")
        tx.record(
            "envelope.send_undone",
            target=Target("envelope", envelope_id),
            after=Ref(grant=grant),
        )


# --- Page previews -------------------------------------------------------------------------------


async def document_page(
    ctx: AuthContext, envelope_id: UUID, document_id: UUID, page_no: int
) -> bytes:
    """`GET /v1/envelopes/{id}/documents/{doc}/pages/{n}`: the document's masked page image, as
    the evidence viewer renders it (no SSN or account number shows; the read is logged as a
    content read). The person reads the envelope and, through the viewer, the evidence: one who
    may read envelopes but not that evidence gets 403 from the viewer. A document of another
    envelope answers 404; a generated document (P-11) has no preview yet: 409
    `preview_unavailable`."""
    await firm_and_flag(ctx)
    async with tenant_session(ctx.tenant) as session:
        await visible_head(ctx, session, envelope_id)
        version_id = (
            await session.execute(
                text(
                    "SELECT evidence_version_id FROM envelope_documents "
                    "WHERE id = :doc AND envelope_id = :id"
                ),
                {"doc": document_id, "id": envelope_id},
            )
        ).one_or_none()
    if version_id is None:
        raise NotFound("envelope_document")
    if version_id[0] is None:
        raise PreviewUnavailable
    return await viewer_page(ctx, version_id[0], page_no)
