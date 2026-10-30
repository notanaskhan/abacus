"""C19 v1, the stub: the §7216 consent registry, the TRI gate and the tax-profile family (T-01-T01;
T-01 §3.1 to §3.6, §4.3). Contract: `docs/contracts/c19-consent-gate.md`.

A consent is one purpose per signed document (Treas. Reg. §301.7216-3; DF-31): `use`,
`ai_disclosure`, `offshore_disclosure`, `third_party_disclosure`, `other_services_use` or
`firm_defined`, for named tax years, a scope and recipients, from a counsel-approved template
version. Condition 6 of the AI gateway (T-01 §3.2): tax return information (TRI) never reaches a
model unless the taxpayer's `use` and `ai_disclosure` consents are signed and in force for the
year; `tri_consent_verdict` answers that, and `consent_7216` is the boundary's refusal reason.

Each route answers 404 for a client principal (INV-4), 403 for a principal the matrix refuses, 404
with its flag off (`consents.registry`; `clients.tax_profile` for the tax-profile family) and 501
`not_implemented` with it on, until its build task (T-01-T10 onward). Files arrive as upload
intents (`upload_ids`), never a multipart body. Every write is a person's: agent and system are
denied in the matrix (I-AGENT-NEVER).

Classification (ADR-031): consent rows are `confidential` (who consented to what); figures read
from returns and transcripts are TRI (`classified("restricted", tri=True)`); CAF numbers are
sealed and only their last four digits are served (the `caf` PII kind arrives with T-01-T07's
data-inventory rows). No TIN appears: the identity band carries the last four only (DEC-52).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import CLIENTS_TAX_PROFILE, CONSENTS_REGISTRY
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
    mask_tins_for,
)
from abacus.modules.organisations.consents import consent_rows
from abacus.modules.organisations.consents import decline as decline_consent
from abacus.modules.organisations.consents import revoke as revoke_consent
from abacus.modules.organisations.contract import MaskedTinOut
from abacus.modules.organisations.slots import ConsentCapture, consent_capture

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]

Purpose = Literal[
    "use",
    "ai_disclosure",
    "offshore_disclosure",
    "third_party_disclosure",
    "other_services_use",
    "firm_defined",
]
# C2 codes land with T-01-T06 (status-vocabulary rows); the contract names them now.
ConsentStatus = Literal["requested", "signed", "declined", "revoked", "superseded", "expired"]
ConsentSource = Literal["envelope", "record"]
SetKind = Literal["use_ai_disclosure", "single"]
AuthorizationForm = Literal["8821", "2848", "state"]
AuthorizationStatus = Literal["requested", "on_file", "expired", "revoked"]
TranscriptKind = Literal["wage_income", "account", "record_of_account"]
TaxYear = Annotated[int, Field(ge=2000, le=2100)]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- consents ------------------------------------------------------------------------------------


class ConsentRecipientOut(BaseModel):
    """Who a disclosure consent names (DF-16: from the register, never free text)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[
        Literal["firm", "provider", "offshore_preparer", "third_party"], classified("internal")
    ]
    name: Annotated[str, classified("confidential")]
    country: Annotated[str | None, classified("internal")]


class ConsentSignerOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    contact_id: Annotated[UUID | None, classified("internal")]
    name: Annotated[str, classified("confidential")]
    role: Annotated[
        Literal["taxpayer", "spouse", "officer", "fiduciary", "partner"], classified("internal")
    ]
    required: Annotated[bool, classified("internal")]
    signed_at: Annotated[datetime | None, classified("confidential")]
    method: Annotated[Literal["email_code", "kba", "wet", "record"] | None, classified("internal")]
    # T-01-T13 (additive): the line under the name ("trustee", "CEO", "for Ridgeline GP LLC").
    title: Annotated[str | None, classified("confidential")] = None


class ConsentOut(BaseModel):
    """One consent: one purpose, its years, scope, recipients, template and signers."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    client_entity_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    consent_set_id: Annotated[UUID | None, classified("internal")]
    purpose: Annotated[Purpose, classified("internal")]
    tax_years: Annotated[list[int], classified("internal")]
    scope: Annotated[dict[str, str], classified("confidential")]
    recipients: Annotated[list[ConsentRecipientOut], classified("confidential")]
    provider_terms_version: Annotated[str, classified("internal")]
    template_version_id: Annotated[UUID, classified("internal")]
    source: Annotated[ConsentSource, classified("internal")]
    envelope_id: Annotated[UUID | None, classified("internal")]
    status: Annotated[ConsentStatus, classified("internal")]
    signed_count: Annotated[int, classified("internal")]
    signer_count: Annotated[int, classified("internal")]
    requested_at: Annotated[datetime, classified("confidential")]
    signed_at: Annotated[datetime | None, classified("confidential")]
    expires_at: Annotated[datetime | None, classified("confidential")]
    renewal_of_id: Annotated[UUID | None, classified("internal")]
    offshore: Annotated[bool, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    # T-01-T13 (additive): ADM-05's rows: when a decline or revocation was recorded, and who
    # signs ("Morgan ✓ Sep 9 · Kai ○"; the signer line under the client's name).
    declined_at: Annotated[datetime | None, classified("confidential")] = None
    revoked_at: Annotated[datetime | None, classified("confidential")] = None
    signers: Annotated[list[ConsentSignerOut], classified("confidential")] = Field(
        default_factory=list[ConsentSignerOut]
    )
    # T-01-T14 (additive): the counsel-approved template's name ("BH §7216 Consent to Use v2"),
    # database content, for CLI-05's per-document sub-rows.
    template_name: Annotated[str | None, classified("internal")] = None


class ConsentDocumentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    purpose: Annotated[Purpose, classified("internal")]
    text_sha256: Annotated[str, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]


class AgentReadOut(BaseModel):
    """An agent run that read the taxpayer's TRI under this consent (CLI-05d, ADM-05 drawer)."""

    model_config = ConfigDict(frozen=True)

    agent_run_id: Annotated[UUID, classified("internal")]
    read_at: Annotated[datetime, classified("confidential")]
    on_behalf_of_name: Annotated[str, classified("confidential")]


class ConsentDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    consent: Annotated[ConsentOut, classified("confidential")]
    signers: Annotated[list[ConsentSignerOut], classified("confidential")]
    documents: Annotated[list[ConsentDocumentOut], classified("internal")]
    agent_reads: Annotated[list[AgentReadOut], classified("confidential")]


class ConsentSummaryOut(BaseModel):
    """Counts for ADM-04 D, CLI-02 b and the BND-01 tag (no client names)."""

    model_config = ConfigDict(frozen=True)

    total: Annotated[int, classified("internal")]
    signed: Annotated[int, classified("internal")]
    requested: Annotated[int, classified("internal")]
    expiring: Annotated[int, classified("internal")]
    expired: Annotated[int, classified("internal")]
    declined: Annotated[int, classified("internal")]
    revoked: Annotated[int, classified("internal")]
    ai_use_signed: Annotated[int, classified("internal")]
    offshore: Annotated[int, classified("internal")]


class ConsentRequestIn(BaseModel):
    """Draft a C7 envelope with one document per purpose (422 `one_purpose_per_document`, 409
    `consent_declined` for a purpose the taxpayer declined)."""

    model_config = _frozen()

    client_entity_id: Annotated[UUID, classified("internal")]
    purposes: Annotated[list[Purpose], Field(min_length=1, max_length=6), classified("internal")]
    tax_years: Annotated[list[TaxYear], Field(min_length=1, max_length=5), classified("internal")]
    scope: Annotated[dict[str, str] | None, classified("confidential")] = None
    recipient_id: Annotated[UUID | None, classified("internal")] = None


class ConsentRenewalIn(BaseModel):
    model_config = _frozen()

    consent_ids: Annotated[list[UUID], Field(min_length=1, max_length=200), classified("internal")]


class ConsentRecordIn(BaseModel):
    """Record mode: a consent signed outside Accrued, from scanned files (upload intents)."""

    model_config = _frozen()

    client_entity_id: Annotated[UUID, classified("internal")]
    purpose: Annotated[Purpose, classified("internal")]
    tax_years: Annotated[list[TaxYear], Field(min_length=1, max_length=5), classified("internal")]
    template_version_id: Annotated[UUID, classified("internal")]
    signed_on: Annotated[date, classified("confidential")]
    upload_ids: Annotated[list[UUID], Field(min_length=1, max_length=5), classified("internal")]
    attested: Annotated[Literal[True], classified("internal")]


class ConsentReasonIn(BaseModel):
    model_config = _frozen()

    reason: Annotated[str, Field(min_length=1, max_length=500), classified("confidential")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class ConsentExportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    export_id: Annotated[UUID, classified("internal")]
    # The async CSV's lifecycle (C19 `consent.exported`): the 202 answers `queued`.
    status: Annotated[Literal["queued", "ready", "failed"], classified("internal")]


class ConsentDraftsOut(BaseModel):
    """The drafted envelope and the consents it will carry."""

    model_config = ConfigDict(frozen=True)

    envelope_id: Annotated[UUID, classified("internal")]
    consents: Annotated[list[ConsentOut], classified("confidential")]


# --- consent templates (counsel-approved; database content) -------------------------------------


class ConsentTemplateImportIn(BaseModel):
    model_config = _frozen()

    upload_id: Annotated[UUID, classified("internal")]
    dry_run: Annotated[bool, classified("internal")] = True
    counsel_attestation: Annotated[Literal[True], classified("internal")]


class ConsentTemplateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    purpose: Annotated[Purpose, classified("internal")]
    version: Annotated[int, classified("internal")]
    status: Annotated[Literal["draft", "published", "retired"], classified("internal")]
    text_sha256: Annotated[str, classified("internal")]
    published_at: Annotated[datetime | None, classified("internal")]


# --- the tax-profile family (CLI-05) ------------------------------------------------------------


class TaxAuthorizationDesigneeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    caf_last4: Annotated[str | None, classified("confidential")]


class TaxAuthorizationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    form: Annotated[AuthorizationForm, classified("internal")]
    state_form_code: Annotated[str | None, classified("internal")]
    designees: Annotated[list[TaxAuthorizationDesigneeOut], classified("confidential")]
    tax_matters: Annotated[list[str], classified("confidential")]
    tax_years: Annotated[list[int], classified("internal")]
    received_on: Annotated[date | None, classified("confidential")]
    expires_on: Annotated[date | None, classified("confidential")]
    status: Annotated[AuthorizationStatus, classified("internal")]


class TaxElectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[str, classified("internal")]
    jurisdiction: Annotated[str | None, classified("internal")]
    tax_year: Annotated[int, classified("internal")]
    amount: Annotated[Decimal | None, classified("restricted", tri=True)]
    status_code: Annotated[str, classified("internal")]


class TaxProfileIdentityOut(BaseModel):
    """CLI-05's Identity band: who the profile is for, by masked TIN (last four; DEC-52)."""

    model_config = ConfigDict(frozen=True)

    role: Annotated[Literal["taxpayer", "spouse"], classified("internal")]
    client_entity_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    # Named for what it holds: C19 keeps a field called `tin` (or ssn, ein, itin) for plaintext.
    masked_tin: Annotated[MaskedTinOut | None, classified("restricted")] = None


class TaxProfileOut(BaseModel):
    """CLI-05's rail: consents in force, authorizations on file, elections, a masked identity band
    (last four only; DEC-52) and open notices (planned)."""

    model_config = ConfigDict(frozen=True)

    client_entity_id: Annotated[UUID, classified("internal")]
    taxpayer_tin: Annotated[MaskedTinOut | None, classified("restricted")] = None  # last four only
    consents: Annotated[list[ConsentOut], classified("confidential")]
    authorizations: Annotated[list[TaxAuthorizationOut], classified("confidential")]
    elections: Annotated[list[TaxElectionOut], classified("restricted", tri=True)]
    open_notices: Annotated[int | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    # T-01-T14 (additive): the subbar and the Identity band.
    client_name: Annotated[str, classified("confidential")] = ""
    client_kind: Annotated[str | None, classified("internal")] = None  # "Household"
    partner_name: Annotated[str | None, classified("confidential")] = None
    office_name: Annotated[str | None, classified("internal")] = None
    identity: Annotated[list[TaxProfileIdentityOut], classified("restricted")] = Field(
        default_factory=list[TaxProfileIdentityOut]
    )
    portal_user_name: Annotated[str | None, classified("confidential")] = None
    resident_state: Annotated[str | None, classified("internal")] = None


class TaxElectionIn(BaseModel):
    model_config = _frozen()

    jurisdiction: Annotated[str | None, Field(max_length=20), classified("internal")] = None
    tax_year: Annotated[TaxYear, classified("internal")]
    amount: Annotated[Decimal | None, classified("restricted", tri=True)] = None
    status_code: Annotated[str, Field(min_length=1, max_length=40), classified("internal")]
    seen_version: Annotated[int | None, Field(ge=1), classified("internal")] = None


class TaxAuthorizationIn(BaseModel):
    """An authorization already on file (with its scanned form as an upload intent)."""

    model_config = _frozen()

    form: Annotated[AuthorizationForm, classified("internal")]
    state_form_code: Annotated[str | None, Field(max_length=20), classified("internal")] = None
    designee_user_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=10), classified("internal")
    ]
    tax_matters: Annotated[
        list[str], Field(min_length=1, max_length=20), classified("confidential")
    ]
    tax_years: Annotated[list[TaxYear], Field(min_length=1, max_length=10), classified("internal")]
    received_on: Annotated[date, classified("confidential")]
    expires_on: Annotated[date | None, classified("confidential")] = None
    upload_id: Annotated[UUID, classified("internal")]


class TaxAuthorizationRequestIn(BaseModel):
    model_config = _frozen()

    form: Annotated[Literal["8821", "2848"], classified("internal")]


class TranscriptUploadIn(BaseModel):
    model_config = _frozen()

    kind: Annotated[TranscriptKind, classified("internal")]
    tax_year: Annotated[TaxYear, classified("internal")]
    authorization_id: Annotated[UUID, classified("internal")]
    upload_id: Annotated[UUID, classified("internal")]


class TranscriptOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[TranscriptKind, classified("internal")]
    tax_year: Annotated[int, classified("internal")]
    pulled_at: Annotated[datetime, classified("confidential")]
    parse_status: Annotated[Literal["queued", "parsed", "failed"], classified("internal")]


class TranscriptComparisonIn(BaseModel):
    model_config = _frozen()

    return_id: Annotated[UUID, classified("internal")]


class TranscriptLineDiffOut(BaseModel):
    """A transcript line against the return as filed (code computes; ADR-050)."""

    model_config = ConfigDict(frozen=True)

    form: Annotated[str, classified("internal")]
    payer_name: Annotated[str | None, classified("restricted", tri=True)]
    transcript_amount: Annotated[Decimal, classified("restricted", tri=True)]
    return_amount: Annotated[Decimal | None, classified("restricted", tri=True)]
    matched: Annotated[bool, classified("internal")]


class TranscriptComparisonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    transcript_id: Annotated[UUID, classified("internal")]
    return_id: Annotated[UUID, classified("internal")]
    lines: Annotated[list[TranscriptLineDiffOut], classified("restricted", tri=True)]


# --- routes --------------------------------------------------------------------------------------

consents_router = AbacusRouter(prefix="/v1", tags=["consents"])
ConsentId = Annotated[UUID, Path()]
EntityId = Annotated[UUID, Path()]


async def _stub(ctx: AuthContext, action: str, flag: Flag) -> NoReturn:
    """INV-4 (404 for a client principal), then the matrix (403), the flag (404), then 501."""
    if ctx.client:
        raise NotFound("consent")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)
    raise NotImplementedYet


async def _live(ctx: AuthContext, action: str) -> None:
    """T-01-T10: the stub's order of checks for a live route (client 404, matrix, flag)."""
    if ctx.client:
        raise NotFound("consent")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, CONSENTS_REGISTRY):
        raise NotFound(CONSENTS_REGISTRY.name)


def _capture() -> ConsentCapture:
    found = consent_capture()
    if found is None:
        raise NotImplementedYet  # the tax module registers capture at import
    return found


async def consent_outs(ctx: AuthContext, ids: list[UUID]) -> list[ConsentOut]:
    """C19's `ConsentOut` for consents just written (T-01-T10; the registry reads are T16's)."""
    rows = await consent_rows(ctx.tenant, ids)
    out: list[ConsentOut] = []
    for row in rows:
        v = row.values
        out.append(
            ConsentOut(
                id=v["id"],  # type: ignore[arg-type]  # columns typed by the SQL
                client_id=v["client_id"],  # type: ignore[arg-type]
                client_entity_id=v["client_entity_id"],  # type: ignore[arg-type]
                client_name=str(v["client_name"]),
                consent_set_id=v["consent_set_id"],  # type: ignore[arg-type]
                purpose=v["purpose"],  # type: ignore[arg-type]
                tax_years=list(v["tax_years"]),  # type: ignore[call-overload]
                scope=dict(v["scope"]),  # type: ignore[call-overload]
                recipients=[ConsentRecipientOut.model_validate(r) for r in v["recipients"]],  # type: ignore[attr-defined]
                provider_terms_version=str(v["provider_terms_version"]),
                template_version_id=v["template_version_id"],  # type: ignore[arg-type]
                source=v["source"],  # type: ignore[arg-type]
                envelope_id=v["envelope_id"],  # type: ignore[arg-type]
                status=v["status"],  # type: ignore[arg-type]
                signed_count=int(v["signed_count"]),  # type: ignore[call-overload]
                signer_count=int(v["signer_count"]),  # type: ignore[call-overload]
                requested_at=v["requested_at"],  # type: ignore[arg-type]
                signed_at=v["signed_at"],  # type: ignore[arg-type]
                expires_at=v["expires_at"],  # type: ignore[arg-type]
                renewal_of_id=v["renewal_of_id"],  # type: ignore[arg-type]
                offshore=v["purpose"] == "offshore_disclosure",
                allowed_actions=[],
                declined_at=v["declined_at"],  # type: ignore[arg-type]
                revoked_at=v["revoked_at"],  # type: ignore[arg-type]
                signers=[
                    ConsentSignerOut(
                        contact_id=s["contact_id"],  # type: ignore[arg-type]
                        name=str(s["display_name"]),
                        role=s["signer_role"],  # type: ignore[arg-type]
                        required=bool(s["required"]),
                        signed_at=s["signed_at"],  # type: ignore[arg-type]
                        method=s["method"],  # type: ignore[arg-type]
                    )
                    for s in row.signers
                ],
            )
        )
    return out


@consents_router.get(
    "/consents", action="consent.read", response_model=ListPage[ConsentOut], errors=(501,)
)
async def list_consents_route(
    ctx: Ctx,
    status: Annotated[ConsentStatus | None, Query()] = None,
    purpose: Annotated[Purpose | None, Query()] = None,
    tax_year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    offshore: Annotated[bool | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> ListPage[ConsentOut]:
    """ADM-05: the registry, needs-attention first, walls applied (no hidden counts)."""
    await _stub(ctx, "consent.read", CONSENTS_REGISTRY)


@consents_router.get(
    "/consents/summary", action="consent.read", response_model=ConsentSummaryOut, errors=(501,)
)
async def consent_summary_route(ctx: Ctx) -> ConsentSummaryOut:
    await _stub(ctx, "consent.read", CONSENTS_REGISTRY)


@consents_router.get(
    "/consents/{consent_id}", action="consent.read", response_model=ConsentDetailOut, errors=(501,)
)
async def consent_route(consent_id: ConsentId, ctx: Ctx) -> ConsentDetailOut:
    await _stub(ctx, "consent.read", CONSENTS_REGISTRY)


@consents_router.get(
    "/consents/{consent_id}/documents/{document_id}/evidence",
    action="consent.evidence_download",
    response_model=bytes,
    errors=(501,),
)
async def consent_evidence_route(
    consent_id: ConsentId, document_id: Annotated[UUID, Path()], ctx: Ctx
) -> bytes:
    """The signed document, audited (`consent.evidence_downloaded`)."""
    await _stub(ctx, "consent.evidence_download", CONSENTS_REGISTRY)


@consents_router.post(
    "/consents/requests",
    action="consent.request",
    response_model=ConsentDraftsOut,
    status_code=201,
    errors=(409, 501),
)
async def request_consents_route(
    body: ConsentRequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConsentDraftsOut:
    """T-01-T10: one document per purpose, one drafted envelope; sending stays SIG-02's."""
    await _live(ctx, "consent.request")
    return cast(ConsentDraftsOut, await _capture().request(ctx, body))


@consents_router.post(
    "/consents/renewals",
    action="consent.request",
    response_model=ConsentDraftsOut,
    status_code=201,
    errors=(409, 501),
)
async def renew_consents_route(
    body: ConsentRenewalIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConsentDraftsOut:
    """T-01-T10: renewals keep purpose, scope and years; 409 `consent_declined`."""
    await _live(ctx, "consent.request")
    return cast(ConsentDraftsOut, await _capture().renew(ctx, body))


@consents_router.post(
    "/consents/records",
    action="consent.record",
    response_model=ConsentOut,
    status_code=201,
    errors=(409, 501),
)
async def record_consent_route(
    body: ConsentRecordIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConsentOut:
    """T-01-T10 Story 1.3: record mode, the signed PDF into COMPLIANCE storage."""
    await _live(ctx, "consent.record")
    return cast(ConsentOut, await _capture().record(ctx, body))


@consents_router.post(
    "/consents/{consent_id}/declines",
    action="consent.record",
    response_model=ConsentOut,
    errors=(409, 501),
)
async def decline_consent_route(
    consent_id: ConsentId, body: ConsentReasonIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConsentOut:
    """T-01-T10 Story 1.4: a decline blocks re-solicitation for the same years."""
    await _live(ctx, "consent.record")
    await decline_consent(ctx, consent_id, body.seen_version)
    return (await consent_outs(ctx, [consent_id]))[0]


@consents_router.post(
    "/consents/{consent_id}/revocations",
    action="consent.record",
    response_model=ConsentOut,
    errors=(409, 501),
)
async def revoke_consent_route(
    consent_id: ConsentId, body: ConsentReasonIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConsentOut:
    """T-01-T10 Story 1.4: a revocation; the gate's next call is refused."""
    await _live(ctx, "consent.record")
    await revoke_consent(ctx, consent_id, body.seen_version)
    return (await consent_outs(ctx, [consent_id]))[0]


@consents_router.post(
    "/consents/exports",
    action="consent.export",
    response_model=ConsentExportOut,
    status_code=202,
    errors=(501,),
)
async def export_consents_route(ctx: Ctx, idempotency_key: IdempotencyKey) -> ConsentExportOut:
    await _stub(ctx, "consent.export", CONSENTS_REGISTRY)


@consents_router.get(
    "/client-entities/{client_entity_id}/consents",
    action="consent.read",
    response_model=list[ConsentOut],
    errors=(501,),
)
async def entity_consents_route(client_entity_id: EntityId, ctx: Ctx) -> list[ConsentOut]:
    await _stub(ctx, "consent.read", CONSENTS_REGISTRY)


@consents_router.post(
    "/consent-templates/imports",
    action="consent_template.manage",
    response_model=list[ConsentTemplateOut],
    status_code=201,
    errors=(501,),
)
async def import_consent_templates_route(
    body: ConsentTemplateImportIn, ctx: Ctx
) -> list[ConsentTemplateOut]:
    await _stub(ctx, "consent_template.manage", CONSENTS_REGISTRY)


@consents_router.post(
    "/consent-templates/{template_id}/publish",
    action="consent_template.publish",
    response_model=ConsentTemplateOut,
    errors=(409, 501),
)
async def publish_consent_template_route(
    template_id: Annotated[UUID, Path()], ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConsentTemplateOut:
    await _stub(ctx, "consent_template.publish", CONSENTS_REGISTRY)


@consents_router.get(
    "/client-entities/{client_entity_id}/tax-profile",
    action="tax_profile.read",
    response_model=TaxProfileOut,
    errors=(501,),
)
async def tax_profile_route(client_entity_id: EntityId, ctx: Ctx) -> TaxProfileOut:
    # The answer carries the masked TIN, so it goes out through the offshore mask (AC9.4).
    return await mask_tins_for(ctx, await _tax_profile(ctx, client_entity_id))


async def _tax_profile(ctx: AuthContext, client_entity_id: UUID) -> TaxProfileOut:
    """T-01-T42 reads the profile; until then the stub's order of checks, then 501."""
    del client_entity_id
    await _stub(ctx, "tax_profile.read", CLIENTS_TAX_PROFILE)


@consents_router.put(
    "/client-entities/{client_entity_id}/elections/{kind}",
    action="tax_election.manage",
    response_model=TaxElectionOut,
    errors=(409, 501),
)
async def put_election_route(
    client_entity_id: EntityId,
    kind: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{1,59}$")],
    body: TaxElectionIn,
    ctx: Ctx,
) -> TaxElectionOut:
    await _stub(ctx, "tax_election.manage", CLIENTS_TAX_PROFILE)


@consents_router.get(
    "/client-entities/{client_entity_id}/authorizations",
    action="tax_authorization.manage",
    response_model=list[TaxAuthorizationOut],
    errors=(501,),
)
async def list_authorizations_route(
    client_entity_id: EntityId, ctx: Ctx
) -> list[TaxAuthorizationOut]:
    await _stub(ctx, "tax_authorization.manage", CLIENTS_TAX_PROFILE)


@consents_router.post(
    "/client-entities/{client_entity_id}/authorizations",
    action="tax_authorization.manage",
    response_model=TaxAuthorizationOut,
    status_code=201,
    errors=(501,),
)
async def add_authorization_route(
    client_entity_id: EntityId, body: TaxAuthorizationIn, ctx: Ctx
) -> TaxAuthorizationOut:
    await _stub(ctx, "tax_authorization.manage", CLIENTS_TAX_PROFILE)


@consents_router.post(
    "/client-entities/{client_entity_id}/authorizations/requests",
    action="tax_authorization.manage",
    response_model=TaxAuthorizationOut,
    status_code=201,
    errors=(501,),
)
async def request_authorization_route(
    client_entity_id: EntityId, body: TaxAuthorizationRequestIn, ctx: Ctx
) -> TaxAuthorizationOut:
    """Draft an 8821 or 2848 through C7."""
    await _stub(ctx, "tax_authorization.manage", CLIENTS_TAX_PROFILE)


@consents_router.post(
    "/client-entities/{client_entity_id}/transcripts",
    action="transcript.upload",
    response_model=TranscriptOut,
    status_code=201,
    errors=(501,),
)
async def upload_transcript_route(
    client_entity_id: EntityId, body: TranscriptUploadIn, ctx: Ctx
) -> TranscriptOut:
    await _stub(ctx, "transcript.upload", CLIENTS_TAX_PROFILE)


@consents_router.post(
    "/transcripts/{transcript_id}/comparisons",
    action="transcript.compare",
    response_model=TranscriptComparisonOut,
    status_code=201,
    errors=(501,),
)
async def compare_transcript_route(
    transcript_id: Annotated[UUID, Path()], body: TranscriptComparisonIn, ctx: Ctx
) -> TranscriptComparisonOut:
    await _stub(ctx, "transcript.compare", CLIENTS_TAX_PROFILE)


# --- C19 module API (frozen with v1; `consent_gate.py` reads, T-01-T11; T-01-T10 captures) -----


@dataclass(frozen=True)
class ConsentState:
    """The consents in force for an entity, purpose and year."""

    client_entity_id: UUID
    purpose: str
    tax_year: int
    status: str
    consent_id: UUID | None
    expires_at: datetime | None


@dataclass(frozen=True)
class TriVerdict:
    """Condition 6: valid only when every subject has `use` and `ai_disclosure` signed and in
    force for the year; `missing` names (subject, purpose) pairs, never a reason text."""

    valid: bool
    missing: tuple[tuple[UUID, str], ...]
