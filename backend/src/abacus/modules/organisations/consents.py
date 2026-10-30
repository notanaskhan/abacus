"""C19 consents, the write half (T-01-T10; T-01 §3.1 Stories 1.1 to 1.5; SPEC-501 AC-32 to AC-38;
Treas. Reg. §301.7216-3; Rev. Proc. 2013-14).

organisations owns the consent rows (0402) and imports no module that renders or drafts, so
capture is split: the `tax` module renders each purpose's document from the published consent
template and drafts the C7 envelope, then calls in here to write the rows (the capture slot,
`register_consent_capture`, fronts the routes). Everything here is a person's action or a
consumer of one: agent and system principals are denied in the matrix and again here
(I-AGENT-NEVER).

- **Signers** (`filing_unit`): the contacts holding a signing role on the entity (or the client):
  `taxpayer` and `spouse` for a person, both required on a joint filing unit (`household_mfj`,
  422 `signers_missing` without a spouse); `owner`, `cfo` or `controller` as officer; `trustee`
  or `executor` as fiduciary.
- **Request** (`record_request`): one consent set and one consent per purpose (one purpose per
  document, I-7216), each naming its template version, the rendered text's SHA-256, the
  register's material-terms hash and the drafted envelope; every required signer; events and
  `consent.requested` in one unit of work. A purpose the taxpayer declined for the same years is
  409 `consent_declined`, as is a second open request (the 0402 partial index).
- **Signed** (`envelope_completed`): every consent on a completed envelope becomes `signed` with
  each signer's time and method, `expires_at` from the template's stated expiry or one year from
  signing (conflict C-17), the copy-delivered facts, `consent.signed`, and `access.changed` for
  each signer with a portal account, so the gate's next call reads the new rows.
- **Record mode** (`record_signed`): a consent signed outside Accrued, its PDF already in
  COMPLIANCE storage, `source = 'record'` (Story 1.3).
- **Decline and revoke** (`decline`, `revoke`): at the `row_version` read (409 `stale_version`),
  from `requested` or `signed` respectively; a decline blocks re-solicitation (Story 1.4).
- **Third-party scope** (`check_scope`): a third-party disclosure may name only return
  information that existed when signed (422 `scope_not_in_existence`, Story 1.5).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Final, Literal
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import (
    AccessChanged,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
)

SignerRole = Literal["taxpayer", "spouse", "officer", "fiduciary", "partner"]
Method = Literal["email_code", "kba", "wet", "record"]
REQUEST: Final = "consent.request"
RECORD: Final = "consent.record"
_ROLE_OF: Final[dict[str, SignerRole]] = {
    "taxpayer": "taxpayer",
    "spouse": "spouse",
    "owner": "officer",
    "cfo": "officer",
    "controller": "officer",
    "trustee": "fiduciary",
    "executor": "fiduciary",
}
_JOINT: Final = "household_mfj"
DEFAULT_EXPIRY: Final = timedelta(days=365)


class ConsentDeclined(DomainConflict):
    """The taxpayer declined this purpose for these years: no re-solicitation (Story 1.4)."""

    code = "consent_declined"


class ConsentOpen(DomainConflict):
    """A request for this purpose and these years is already open."""

    code = "consent_open"


class SignersMissing(DomainInvalid):
    """The entity has no signing contact, or a joint filing unit lacks one spouse."""

    code = "signers_missing"


class ScopeNotInExistence(DomainInvalid):
    """A third-party scope may name only return information that existed when signed."""

    code = "scope_not_in_existence"


class StaleVersion(DomainConflict):
    code = "stale_version"


class WrongStatus(DomainConflict):
    """Declines apply to an open request, revocations to a signed consent."""

    code = "consent_status_conflict"


@dataclass(frozen=True)
class Signer:
    contact_id: UUID
    role: SignerRole
    name: str
    user_id: UUID | None = None
    required: bool = True


@dataclass(frozen=True)
class FilingUnit:
    client_id: UUID
    entity_id: UUID
    entity_name: str
    entity_type: str | None
    signers: tuple[Signer, ...]

    @property
    def joint(self) -> bool:
        return self.entity_type == _JOINT


@dataclass(frozen=True)
class ConsentDraft:
    """One purpose's document, already rendered and stored by the capture."""

    purpose: str
    template_version_id: UUID
    text_sha256: str
    provider_terms_version: str
    recipients: list[dict[str, str | None]] = field(default_factory=list[dict[str, str | None]])
    scope: dict[str, str] = field(default_factory=dict[str, str])
    expiry_months: int | None = None
    renewal_of_id: UUID | None = None


async def _human(ctx: AuthContext, action: str) -> None:
    """INV-4 for a client principal (404), I-AGENT-NEVER for anyone not a person (403)."""
    if ctx.client:
        raise NotFound("consent")
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))


_UNIT = text(
    "SELECT e.id, e.client_id, e.name, e.entity_type FROM client_entities e WHERE e.id = :entity"
)
_SIGNERS = text(
    "SELECT DISTINCT c.id, c.display_name, c.user_id, r.role FROM contact_roles r "
    "JOIN contacts c ON c.id = r.contact_id "
    "WHERE ((r.scope_kind = 'client_entity' AND r.scope_id = :entity) "
    "    OR (r.scope_kind = 'client' AND r.scope_id = :client)) "
    "AND r.role IN ('taxpayer', 'spouse', 'owner', 'cfo', 'controller', 'trustee', 'executor') "
    "ORDER BY r.role DESC, c.display_name"
)


async def filing_unit(ctx: AuthContext, entity_id: UUID) -> FilingUnit:
    """The entity and who signs for it (422 `signers_missing`)."""
    await _human(ctx, REQUEST)
    async with tenant_session(ctx.tenant) as session:
        unit = (await session.execute(_UNIT, {"entity": entity_id})).first()
        if unit is None:
            raise NotFound("client_entity")
        rows = (
            await session.execute(_SIGNERS, {"entity": entity_id, "client": unit.client_id})
        ).all()
    seen: set[UUID] = set()
    signers: list[Signer] = []
    for row in rows:
        if row.id in seen:
            continue
        seen.add(row.id)
        signers.append(Signer(row.id, _ROLE_OF[row.role], row.display_name, row.user_id))
    roles = {s.role for s in signers}
    joint = unit.entity_type == _JOINT
    if not signers or (joint and not {"taxpayer", "spouse"} <= roles):
        raise SignersMissing(facts={"client_entity_id": str(entity_id)})
    if joint:
        signers = [s for s in signers if s.role in ("taxpayer", "spouse")]
    else:
        signers = signers[:1]  # one signer for a single taxpayer or an entity
    return FilingUnit(unit.client_id, entity_id, unit.name, unit.entity_type, tuple(signers))


_DECLINED = text(
    "SELECT purpose FROM consents WHERE client_entity_id = :entity AND status = 'declined' "
    "AND tax_years && CAST(:years AS integer[])"
)
_OPEN = text(
    "SELECT purpose FROM consents WHERE client_entity_id = :entity AND status = 'requested' "
    "AND tax_years = CAST(:years AS integer[])"
)


async def refuse_declined(
    tenant: TenantContext, entity_id: UUID, purposes: Sequence[str], years: Sequence[int]
) -> None:
    """409 `consent_declined` for a declined purpose, `consent_open` for an open request."""
    async with tenant_session(tenant) as session:
        declined = set(
            (await session.execute(_DECLINED, {"entity": entity_id, "years": list(years)}))
            .scalars()
            .all()
        )
        opened = set(
            (await session.execute(_OPEN, {"entity": entity_id, "years": sorted(years)}))
            .scalars()
            .all()
        )
    for purpose in purposes:
        if purpose in declined:
            raise ConsentDeclined(facts={"client_entity_id": str(entity_id), "purpose": purpose})
        if purpose in opened:
            raise ConsentOpen(facts={"client_entity_id": str(entity_id), "purpose": purpose})


def check_scope(
    purpose: str, scope: dict[str, str] | None, years: Sequence[int], on: date
) -> None:
    """Story 1.5: a third-party scope may not name a tax year whose return could not exist when
    the consent is signed (a year that has not ended)."""
    if purpose != "third_party_disclosure" or not scope:
        return
    if any(year >= on.year for year in years):
        raise ScopeNotInExistence(facts={"purpose": purpose})


_INSERT_SET = text(
    "INSERT INTO consent_sets (id, tenant_id, client_id, filing_unit_entity_id, kind, "
    "tax_years, created_by) VALUES (:id, :tenant, :client, :entity, :kind, :years, :by)"
)
_INSERT_CONSENT = text(
    "INSERT INTO consents (id, tenant_id, client_id, client_entity_id, consent_set_id, purpose, "
    "tax_years, scope, recipients, provider_terms_version, template_version_id, text_sha256, "
    "source, envelope_id, status, renewal_of_id, created_by, signed_at, expires_at) VALUES "
    "(:id, :tenant, :client, :entity, :set, :purpose, :years, CAST(:scope AS jsonb), "
    "CAST(:recipients AS jsonb), :terms, :template, :sha, :source, :envelope, :status, "
    ":renewal, :by, :signed_at, :expires_at)"
)
_INSERT_SIGNER = text(
    "INSERT INTO consent_signers (id, tenant_id, consent_id, contact_id, signer_role, required) "
    "VALUES (:id, :tenant, :consent, :contact, :role, :required)"
)
_INSERT_EVENT = text(
    "INSERT INTO consent_events (tenant_id, consent_id, kind, actor_kind, actor_id, facts) "
    "VALUES (:tenant, :consent, :kind, :actor_kind, :actor, CAST(:facts AS jsonb))"
)


def _set_kind(purposes: Sequence[str]) -> str:
    return "use_ai_disclosure" if set(purposes) == {"use", "ai_disclosure"} else "single"


async def record_request(
    ctx: AuthContext,
    unit: FilingUnit,
    years: Sequence[int],
    drafts: Sequence[ConsentDraft],
    envelope_id: UUID,
    *,
    set_id: UUID | None = None,
) -> list[UUID]:
    """The consent set, one consent per drafted purpose and their signers (Story 1.1)."""
    await _human(ctx, REQUEST)
    set_id = set_id or uuid4()
    ids: list[UUID] = []
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _INSERT_SET,
            {
                "id": set_id,
                "tenant": ctx.tenant_id,
                "client": unit.client_id,
                "entity": unit.entity_id,
                "kind": _set_kind([d.purpose for d in drafts]),
                "years": sorted(years),
                "by": ctx.user_id,
            },
        )
        for draft in drafts:
            consent_id = uuid4()
            ids.append(consent_id)
            await tx.session.execute(
                _INSERT_CONSENT,
                {
                    "id": consent_id,
                    "tenant": ctx.tenant_id,
                    "client": unit.client_id,
                    "entity": unit.entity_id,
                    "set": set_id,
                    "purpose": draft.purpose,
                    "years": sorted(years),
                    "scope": json.dumps(draft.scope),
                    "recipients": json.dumps(draft.recipients),
                    "terms": draft.provider_terms_version,
                    "template": draft.template_version_id,
                    "sha": bytes.fromhex(draft.text_sha256),
                    "source": "envelope",
                    "envelope": envelope_id,
                    "status": "requested",
                    "renewal": draft.renewal_of_id,
                    "by": ctx.user_id,
                    "signed_at": None,
                    "expires_at": None,
                },
            )
            for signer in unit.signers:
                await tx.session.execute(
                    _INSERT_SIGNER,
                    {
                        "id": uuid4(),
                        "tenant": ctx.tenant_id,
                        "consent": consent_id,
                        "contact": signer.contact_id,
                        "role": signer.role,
                        "required": signer.required,
                    },
                )
            kind = "renewal_drafted" if draft.renewal_of_id else "requested"
            await tx.session.execute(
                _INSERT_EVENT,
                {
                    "tenant": ctx.tenant_id,
                    "consent": consent_id,
                    "kind": kind,
                    "actor_kind": "human",
                    "actor": str(ctx.user_id),
                    "facts": json.dumps({"envelope_id": str(envelope_id)}),
                },
            )
            tx.record(
                f"consent.{kind}",
                target=Target("consent", consent_id),
                after=Ref(purpose=draft.purpose, envelope=envelope_id, set=set_id),
            )
    return ids


_ON_ENVELOPE = text(
    "SELECT c.id, c.client_entity_id, c.renewal_of_id FROM consents c "
    "WHERE c.envelope_id = :envelope AND c.status = 'requested'"
)
_SIGN = text(
    "UPDATE consents SET status = 'signed', signed_at = :at, expires_at = :expires, "
    "copy_delivered_at = :at, copy_delivered_channel = :channel, row_version = row_version + 1 "
    "WHERE id = :id AND status = 'requested'"
)
_SIGN_SIGNERS = text(
    "UPDATE consent_signers SET signed_at = :at, method = :method "
    "WHERE consent_id = :id AND signed_at IS NULL RETURNING contact_id"
)
_SUPERSEDE = text(
    "UPDATE consents SET status = 'superseded', row_version = row_version + 1 "
    "WHERE id = :id AND status = 'signed'"
)
_PORTAL_USERS = text("SELECT user_id FROM contacts WHERE id = ANY(:ids) AND user_id IS NOT NULL")


def expiry(signed_at: datetime, months: int | None) -> datetime:
    """Conflict C-17: the template's stated expiry wins, else one year from signing."""
    if months is None:
        return signed_at + DEFAULT_EXPIRY
    year, month = divmod(signed_at.month - 1 + months, 12)
    day = min(signed_at.day, 28)
    return signed_at.replace(year=signed_at.year + year, month=month + 1, day=day)


async def envelope_completed(
    tenant: TenantContext,
    envelope_id: UUID,
    *,
    method: Method,
    expiry_months: dict[UUID, int | None],
) -> list[UUID]:
    """C7 `envelope.completed` (Story 1.2): every requested consent on the envelope is signed by
    each of its signers; a renewal supersedes the consent it renews. Idempotent: a consent
    already signed is left alone. `expiry_months` maps a consent to its template's stated
    expiry (from the capture, which reads the template)."""
    at = await now(tenant)
    signed: list[UUID] = []
    contacts: set[UUID] = set()
    async with uow(tenant) as tx:
        rows = (await tx.session.execute(_ON_ENVELOPE, {"envelope": envelope_id})).all()
        for row in rows:
            moved = await tx.session.execute(
                _SIGN,
                {
                    "id": row.id,
                    "at": at,
                    "expires": expiry(at, expiry_months.get(row.id)),
                    "channel": "portal" if method != "record" else "paper",
                },
            )
            if not moved.rowcount:  # pyright: ignore[reportAttributeAccessIssue] -- CursorResult
                continue
            signed.append(row.id)
            contacts.update(
                (
                    await tx.session.execute(
                        _SIGN_SIGNERS, {"id": row.id, "at": at, "method": method}
                    )
                )
                .scalars()
                .all()
            )
            if row.renewal_of_id is not None:
                await tx.session.execute(_SUPERSEDE, {"id": row.renewal_of_id})
            for kind in ("signed", "copy_delivered"):
                await tx.session.execute(
                    _INSERT_EVENT,
                    {
                        "tenant": tenant.tenant_id,
                        "consent": row.id,
                        "kind": kind,
                        "actor_kind": "system",
                        "actor": f"envelope:{envelope_id}",
                        "facts": json.dumps({"envelope_id": str(envelope_id)}),
                    },
                )
            tx.record(
                "consent.signed",
                target=Target("consent", row.id),
                after=Ref(envelope=envelope_id, method=method),
            )
        if contacts:
            users = (
                (await tx.session.execute(_PORTAL_USERS, {"ids": list(contacts)})).scalars().all()
            )
            for user_id in users:
                tx.emit(AccessChanged(user_id=user_id))
    return signed


async def record_signed(
    ctx: AuthContext,
    unit: FilingUnit,
    years: Sequence[int],
    draft: ConsentDraft,
    signed_on: date,
) -> UUID:
    """Record mode (Story 1.3): a consent signed elsewhere, its PDF already stored."""
    await _human(ctx, RECORD)
    consent_id = uuid4()
    tz_at = datetime.combine(signed_on, time(12), tzinfo=UTC)  # noon UTC on the signing day
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _INSERT_CONSENT,
            {
                "id": consent_id,
                "tenant": ctx.tenant_id,
                "client": unit.client_id,
                "entity": unit.entity_id,
                "set": None,
                "purpose": draft.purpose,
                "years": sorted(years),
                "scope": json.dumps(draft.scope),
                "recipients": json.dumps(draft.recipients),
                "terms": draft.provider_terms_version,
                "template": draft.template_version_id,
                "sha": bytes.fromhex(draft.text_sha256),
                "source": "record",
                "envelope": None,
                "status": "signed",
                "renewal": None,
                "by": ctx.user_id,
                "signed_at": tz_at,
                "expires_at": expiry(tz_at, draft.expiry_months),
            },
        )
        for signer in unit.signers:
            sid = uuid4()
            await tx.session.execute(
                _INSERT_SIGNER,
                {
                    "id": sid,
                    "tenant": ctx.tenant_id,
                    "consent": consent_id,
                    "contact": signer.contact_id,
                    "role": signer.role,
                    "required": signer.required,
                },
            )
        await tx.session.execute(
            _SIGN_SIGNERS, {"id": consent_id, "at": tz_at, "method": "record"}
        )
        await tx.session.execute(
            _INSERT_EVENT,
            {
                "tenant": ctx.tenant_id,
                "consent": consent_id,
                "kind": "recorded",
                "actor_kind": "human",
                "actor": str(ctx.user_id),
                "facts": json.dumps({"text_sha256": draft.text_sha256}),
            },
        )
        tx.record(
            "consent.recorded",
            target=Target("consent", consent_id),
            after=Ref(purpose=draft.purpose, text_sha256=draft.text_sha256),
        )
    return consent_id


_ONE = text("SELECT status, row_version FROM consents WHERE id = :id FOR UPDATE")
_DECLINE = text(
    "UPDATE consents SET status = 'declined', declined_at = :at, row_version = row_version + 1 "
    "WHERE id = :id"
)
_REVOKE = text(
    "UPDATE consents SET status = 'revoked', revoked_at = :at, row_version = row_version + 1 "
    "WHERE id = :id"
)


async def _transition(
    ctx: AuthContext, consent_id: UUID, seen_version: int, *, revoke: bool
) -> None:
    await _human(ctx, RECORD)
    at = await now(ctx.tenant)
    kind = "revoked" if revoke else "declined"
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_ONE, {"id": consent_id})).first()
        if row is None:
            raise NotFound("consent")
        if row.row_version != seen_version:
            raise StaleVersion(facts={"consent_id": str(consent_id)})
        if row.status != ("signed" if revoke else "requested"):
            raise WrongStatus(facts={"consent_id": str(consent_id), "status": row.status})
        await tx.session.execute(_REVOKE if revoke else _DECLINE, {"id": consent_id, "at": at})
        await tx.session.execute(
            _INSERT_EVENT,
            {
                "tenant": ctx.tenant_id,
                "consent": consent_id,
                "kind": kind,
                "actor_kind": "human",
                "actor": str(ctx.user_id),
                "facts": "{}",
            },
        )
        tx.record(f"consent.{kind}", target=Target("consent", consent_id))


async def decline(ctx: AuthContext, consent_id: UUID, seen_version: int) -> None:
    """Story 1.4: the taxpayer declined an open request; no re-solicitation for those years."""
    await _transition(ctx, consent_id, seen_version, revoke=False)


async def revoke(ctx: AuthContext, consent_id: UUID, seen_version: int) -> None:
    """Story 1.4: a revocation in writing; the gate's next call is refused."""
    await _transition(ctx, consent_id, seen_version, revoke=True)


_RENEWAL = text(
    "SELECT id, client_entity_id, purpose, tax_years, scope, status FROM consents "
    "WHERE id = ANY(:ids)"
)


@dataclass(frozen=True)
class RenewalBasis:
    consent_id: UUID
    entity_id: UUID
    purpose: str
    tax_years: tuple[int, ...]
    scope: dict[str, str]


async def renewal_basis(ctx: AuthContext, consent_ids: Sequence[UUID]) -> list[RenewalBasis]:
    """What a renewal keeps: purpose, scope and years (T-01-T10); a decline stands (409)."""
    await _human(ctx, REQUEST)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_RENEWAL, {"ids": list(consent_ids)})).all()
    if len(rows) != len(set(consent_ids)):
        raise NotFound("consent")
    out: list[RenewalBasis] = []
    for row in rows:
        if row.status == "declined":
            raise ConsentDeclined(facts={"consent_id": str(row.id), "purpose": row.purpose})
        out.append(
            RenewalBasis(
                row.id, row.client_entity_id, row.purpose, tuple(row.tax_years), row.scope
            )
        )
    return out


_CONSENT_ROW = text(
    "SELECT c.id, c.client_id, c.client_entity_id, cl.name AS client_name, c.consent_set_id, "
    "c.purpose, c.tax_years, c.scope, c.recipients, c.provider_terms_version, "
    "c.template_version_id, c.source, c.envelope_id, c.status, c.requested_at, c.signed_at, "
    "c.expires_at, c.renewal_of_id, c.declined_at, c.revoked_at, c.row_version, "
    "(SELECT count(*) FROM consent_signers s WHERE s.consent_id = c.id AND s.signed_at IS NOT NULL) "
    "AS signed_count, "
    "(SELECT count(*) FROM consent_signers s WHERE s.consent_id = c.id) AS signer_count "
    "FROM consents c JOIN clients cl ON cl.id = c.client_id WHERE c.id = ANY(:ids) "
    "ORDER BY c.purpose"
)
_SIGNER_ROWS = text(
    "SELECT s.consent_id, s.contact_id, ct.display_name, s.signer_role, s.required, s.signed_at, "
    "s.method FROM consent_signers s JOIN contacts ct ON ct.id = s.contact_id "
    "WHERE s.consent_id = ANY(:ids) ORDER BY s.signer_role DESC, ct.display_name"
)


@dataclass(frozen=True)
class ConsentRow:
    """One consent as C19's `ConsentOut` needs it (the routes map it)."""

    values: dict[str, object]
    signers: list[dict[str, object]]


async def consent_rows(tenant: TenantContext, ids: Sequence[UUID]) -> list[ConsentRow]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_CONSENT_ROW, {"ids": list(ids)})).mappings().all()
        signers = (await session.execute(_SIGNER_ROWS, {"ids": list(ids)})).mappings().all()
    by: dict[UUID, list[dict[str, object]]] = {}
    for s in signers:
        by.setdefault(s["consent_id"], []).append(dict(s))
    return [ConsentRow(dict(r), by.get(r["id"], [])) for r in rows]


_TEMPLATES_ON = text(
    "SELECT id, template_version_id FROM consents "
    "WHERE envelope_id = :envelope AND status = 'requested'"
)


async def consent_template_versions_on(
    tenant: TenantContext, envelope_id: UUID
) -> dict[UUID, UUID]:
    """The open consents an envelope carries and each one's template version (the signing
    consumer reads the template's stated expiry from methodology)."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_TEMPLATES_ON, {"envelope": envelope_id})).all()
    return {r.id: r.template_version_id for r in rows}
