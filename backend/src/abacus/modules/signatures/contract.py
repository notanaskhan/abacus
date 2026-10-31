"""C7 envelope service v1, the stubs (N-02-T03; N-02 §4.3; ADR-149; SPEC-381).
Contract: `docs/contracts/c7-envelopes.md`.

Every route answers 404 with `signatures.envelopes` off and 501 `not_implemented` with it on
until its task lands: record-mode import N-02-T08; the hub, drawer, evidence and reminders
T11-T15; drafts, edits, validate, send, Undo and page previews T20; resend T28; portal
signing T23 (N-02-T23, DEC-1283); policies T13.

Rules the shapes carry:
- **Record mode first** (ADR-149, ADR-342): `provider` is `record`, `docuseal` or `fake`
  (`docusign` stays readable for drafts made before ADR-342); a record-mode
  envelope never has provider fields or a signing session.
- **People send** (AC-16): drafting is the only verb the agent and the system hold.
- **No SMS for the 8879 family** (AC-8): `IdentityMethod` has no `sms_code`.
- **Masked by default**: a signer's IP is `ip_masked` only; the reveal is its own audited route.
  No SSN or TIN field exists on any shape.
- **Reserved**: `provider_envelope_id`, `provider_recipient_id`, `signing_session` and
  `outcome` are null until `signatures.esign_provider` (N-02-T18 onward).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel import listing
from abacus.kernel._flags import SIGNATURES_ENVELOPES
from abacus.kernel._statuses import EnvelopeSignerStatus, EnvelopeStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
    current_member,
)
from abacus.modules.signatures import builder, countersign, fallback, hub, imports, portal

Ctx = Annotated[AuthContext, Depends(current_context)]
Member = Annotated[AuthContext, Depends(current_member)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=64)]

Purpose = Literal[
    "engagement_letter",
    "consent_7216",
    "form_8879",
    "form_8879_pe",
    "form_8879_f",
    "form_2848",
    "form_8821",
    "rep_letter",
    "governance_letter",
    "notice_response",
    "confirmation_authorization",
    "system_description_approval",
    "other",
]
Provider = Literal["docuseal", "docusign", "record", "fake"]
PolicyFamily = Literal["efile_authorization", "engagement_letter", "consent", "general"]
IdentityMethod = Literal["kba", "email_code", "in_person_id", "firm_sso"]
SignerRole = Literal["signer", "countersigner", "ero"]
SignatureMethod = Literal["typed", "drawn", "provider_adopted", "handwritten"]
DeclineReason = Literal["have_questions", "something_wrong", "someone_else_should_sign", "other"]
FieldKind = Literal["signature", "date", "pin", "initial", "title_prefill"]
HubTab = Literal["to_send", "out", "completed", "expired"]
SignerOrder = Literal["sequential", "parallel"]
DateAsOfMode = Literal["none", "fixed_date", "report_date"]
VoidReason = Literal["wrong_document", "wrong_signer", "replaced", "client_request", "other"]


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    """A client principal never reaches the firm routes: 404. Then the action at the firm, then
    the flag, then 501."""
    if ctx.client:
        raise NotFound("envelopes")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, SIGNATURES_ENVELOPES):
        raise NotFound(SIGNATURES_ENVELOPES.name)
    raise NotImplementedYet


# --- Shapes ----------------------------------------------------------------------------------


class SignerOut(BaseModel):
    """One signer, with masked evidence only."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    order: Annotated[int, classified("internal")]
    routing_group: Annotated[int, classified("internal")]
    name: Annotated[str, classified("confidential")]
    role: Annotated[SignerRole, classified("internal")]
    identity_method: Annotated[IdentityMethod, classified("internal")]
    status: Annotated[EnvelopeSignerStatus, classified("internal")]
    kba_failures: Annotated[int, classified("internal")]
    viewed_at: Annotated[datetime | None, classified("internal")]
    signed_at: Annotated[datetime | None, classified("internal")]
    signature_method: Annotated[SignatureMethod | None, classified("internal")]
    decline_reason: Annotated[DeclineReason | None, classified("internal")]
    provider_recipient_id: Annotated[str | None, classified("internal")]
    # N-02-T21 (DEC-1174): SIG-02's signer sub-line and the "Email required" check. None until the
    # builder service fills them (N-02-T20); a signer with no email on file blocks Send.
    title: Annotated[str | None, Field(max_length=200), classified("confidential")] = None
    email: Annotated[str | None, Field(max_length=320), classified("confidential")] = None


class FieldOut(BaseModel):
    """One placed field, in PDF points."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    document_id: Annotated[UUID, classified("internal")]
    signer_id: Annotated[UUID, classified("internal")]
    kind: Annotated[FieldKind, classified("internal")]
    page: Annotated[int, classified("internal")]
    x: Annotated[float, classified("internal")]
    y: Annotated[float, classified("internal")]
    w: Annotated[float, classified("internal")]
    h: Annotated[float, classified("internal")]
    anchor: Annotated[str | None, classified("internal")]


class EnvelopeDocumentOut(BaseModel):
    """One document of the envelope."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    order: Annotated[int, classified("internal")]
    title: Annotated[str, classified("confidential")]
    page_count: Annotated[int, classified("internal")]
    sha256: Annotated[str | None, classified("internal")]
    read_only: Annotated[bool, classified("internal")]
    tri: Annotated[bool, classified("internal")]


class EvidenceItem(BaseModel):
    """One signer's evidence row in the drawer (AC-5): IP masked; reveal is its own route."""

    model_config = ConfigDict(frozen=True)

    signer_id: Annotated[UUID, classified("internal")]
    signed_at: Annotated[datetime, classified("internal")]
    ip_masked: Annotated[str, classified("confidential")]
    identity_result: Annotated[str, classified("internal")]
    signature_method: Annotated[SignatureMethod, classified("internal")]
    user_agent_family: Annotated[str | None, classified("internal")]
    device_label: Annotated[str | None, classified("internal")]
    package_sha256: Annotated[str | None, classified("internal")]


class SignerChip(BaseModel):
    """One signer as SIG-01's chip draws them ("✓ Thomas" · "○ Irene")."""

    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("confidential")]
    signed: Annotated[bool, classified("internal")]
    # N-02-T27 (additive): the signer, and whether their identity checks closed remote signing.
    signer_id: Annotated[UUID | None, classified("internal")] = None
    locked: Annotated[bool, classified("internal")] = False


class EnvelopeListRow(BaseModel):
    """One SIG-01 row."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    number: Annotated[str, classified("internal")]
    purpose: Annotated[Purpose, classified("internal")]
    form_code: Annotated[str | None, classified("internal")]
    title: Annotated[str, classified("confidential")]
    client_id: Annotated[UUID, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    work_item_id: Annotated[UUID | None, classified("internal")]
    provider: Annotated[Provider, classified("internal")]
    status: Annotated[EnvelopeStatus, classified("internal")]
    signed: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    sent_by_name: Annotated[str | None, classified("internal")]
    sent_at: Annotated[datetime | None, classified("internal")]
    due_on: Annotated[date | None, classified("internal")]
    needs_handwritten: Annotated[bool, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    # N-02-T10 (DEC-826, additive): what SIG-01's table draws beyond the counts.
    signer_chips: Annotated[list[SignerChip], classified("confidential")] = Field(
        default_factory=list[SignerChip]
    )
    viewed_at: Annotated[datetime | None, classified("internal")] = None
    work_item_label: Annotated[str | None, classified("confidential")] = None
    note: Annotated[str | None, classified("confidential")] = None
    drafted_by_name: Annotated[str | None, classified("internal")] = None
    outcome: Annotated[str | None, classified("internal")] = None


class EnvelopeOut(BaseModel):
    """The drawer and builder projection."""

    model_config = ConfigDict(frozen=True)

    row: Annotated[EnvelopeListRow, classified("internal")]
    policy_family: Annotated[PolicyFamily, classified("internal")]
    source_kind: Annotated[str, classified("internal")]
    source_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    signer_order: Annotated[SignerOrder, classified("internal")]
    date_as_of_mode: Annotated[DateAsOfMode, classified("internal")]
    date_as_of: Annotated[date | None, classified("internal")]
    expires_at: Annotated[datetime | None, classified("internal")]
    message: Annotated[str | None, classified("confidential")]
    reminder_cadence: Annotated[str | None, classified("internal")]
    documents: Annotated[list[EnvelopeDocumentOut], classified("internal")]
    signers: Annotated[list[SignerOut], classified("internal")]
    fields: Annotated[list[FieldOut], classified("internal")]
    evidence: Annotated[list[EvidenceItem], classified("internal")]
    provider_envelope_id: Annotated[str | None, classified("internal")]
    superseded_at: Annotated[datetime | None, classified("internal")]
    voided_reason: Annotated[VoidReason | None, classified("internal")]
    version: Annotated[int, classified("internal")]


class TileCount(BaseModel):
    """One SIG-01 tile or by-type count, over visible rows only."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    n: Annotated[int, classified("internal")]


class EnvelopeSummary(BaseModel):
    """`GET /v1/envelopes/summary`: tiles, by-type and gate counts (wall-safe, DEC-43)."""

    model_config = ConfigDict(frozen=True)

    to_send: Annotated[int, classified("internal")]
    out: Annotated[int, classified("internal")]
    completed: Annotated[int, classified("internal")]
    expired: Annotated[int, classified("internal")]
    needs_handwritten: Annotated[int, classified("internal")]
    by_type: Annotated[list[TileCount], classified("internal")]


class DraftIn(BaseModel):
    """`POST /v1/envelopes`: a draft prefilled by its registered source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_kind: Annotated[str, Field(min_length=1, max_length=60), classified("internal")]
    source_id: Annotated[UUID, classified("internal")]


class SignerIn(BaseModel):
    """A signer in a draft edit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    order: Annotated[int, Field(ge=1, le=20), classified("internal")]
    routing_group: Annotated[int, Field(ge=1, le=20), classified("internal")] = 1
    contact_id: Annotated[UUID | None, classified("internal")] = None
    user_id: Annotated[UUID | None, classified("internal")] = None
    role: Annotated[SignerRole, classified("internal")] = "signer"
    identity_method: Annotated[IdentityMethod, classified("internal")]


class FieldPlacementIn(BaseModel):
    """N-02-T30 (additive): a field placed on a document's page for one signer, in PDF points
    (origin top-left). `signer_index` is the signer's position in this request's `signers`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: Annotated[UUID, classified("internal")]
    signer_index: Annotated[int, Field(ge=0, lt=20), classified("internal")]
    kind: Annotated[Literal["signature", "date", "pin", "initial"], classified("internal")]
    page: Annotated[int, Field(ge=1, le=500), classified("internal")]
    x: Annotated[float, Field(ge=0, le=2000), classified("internal")]
    y: Annotated[float, Field(ge=0, le=2000), classified("internal")]
    w: Annotated[float, Field(gt=0, le=1000), classified("internal")]
    h: Annotated[float, Field(gt=0, le=1000), classified("internal")]


class DraftUpdateIn(BaseModel):
    """`PUT /v1/envelopes/{id}` (If-Match)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    signers: Annotated[list[SignerIn], Field(max_length=20), classified("internal")]
    signer_order: Annotated[SignerOrder, classified("internal")] = "sequential"
    message: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None
    reminder_cadence: Annotated[str | None, Field(max_length=40), classified("internal")] = None
    expires_on: Annotated[date | None, classified("internal")] = None
    date_as_of_mode: Annotated[DateAsOfMode, classified("internal")] = "none"
    date_as_of: Annotated[date | None, classified("internal")] = None
    # N-02-T21 (DEC-1174): SIG-02's document order after a drag or keyboard move; None keeps it.
    # N-02-T30 (additive): the placed fields; None leaves the draft's fields as they are.
    fields: Annotated[
        list[FieldPlacementIn] | None, Field(max_length=200), classified("internal")
    ] = None
    document_order: Annotated[list[UUID] | None, Field(max_length=20), classified("internal")] = (
        None
    )


class ValidationCheck(BaseModel):
    """One code-computed check SIG-02's Checks band lists (N-02-T21, DEC-1174): an identifier
    the screen words (`amounts_match`, `ero_efin`, `no_ssn_visible`), never prose."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[
        str, Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=60), classified("internal")
    ]
    ok: Annotated[bool, classified("internal")]


class ValidationOut(BaseModel):
    """Code-computed checks before send. `problems` are identifiers
    (`signer_email_missing:<signer_id>`)."""

    model_config = ConfigDict(frozen=True)

    ok: Annotated[bool, classified("internal")]
    problems: Annotated[list[str], classified("internal")]
    checks: Annotated[list[ValidationCheck], classified("internal")] = []


class SendOut(BaseModel):
    """A send waiting its Undo window (ADR-161)."""

    model_config = ConfigDict(frozen=True)

    envelope_id: Annotated[UUID, classified("internal")]
    grant_id: Annotated[UUID, classified("internal")]
    not_before: Annotated[datetime, classified("internal")]


class VoidIn(BaseModel):
    """`POST /v1/envelopes/{id}/void`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[VoidReason, classified("internal")]
    note: Annotated[str | None, Field(max_length=1000), classified("confidential")] = None


class RemindIn(BaseModel):
    """`POST /v1/envelopes/remind/preview` and `/remind/send`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    envelope_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=100), classified("internal")
    ]
    # N-02-T15 (DEC-1057, additive): POR-20 numbers a template's published versions and exposes
    # no version id, so a person's preview names the `signature_reminder` version it showed;
    # N-02-T28 refuses a stale one. The id stays for callers that hold it.
    template_version_id: Annotated[UUID | None, classified("internal")] = None
    template_version: Annotated[int | None, Field(ge=1), classified("internal")] = None


class RemindOut(BaseModel):
    """How many reminders would go, or went; no amounts, no model text."""

    model_config = ConfigDict(frozen=True)

    count: Annotated[int, classified("internal")]
    skipped: Annotated[list[UUID], classified("internal")]


class RevealIn(BaseModel):
    """A reveal's reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[str, Field(min_length=3, max_length=500), classified("confidential")]


class RevealOut(BaseModel):
    """The full IP for 10 seconds."""

    model_config = ConfigDict(frozen=True)

    ip: Annotated[str, classified("restricted")]
    expires_at: Annotated[datetime, classified("internal")]


class ImportSignerIn(BaseModel):
    """One signer's facts in a record-mode import."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contact_id: Annotated[UUID | None, classified("internal")] = None
    user_id: Annotated[UUID | None, classified("internal")] = None
    role: Annotated[SignerRole, classified("internal")] = "signer"
    signed_on: Annotated[date, classified("internal")]
    identity_method: Annotated[IdentityMethod, classified("internal")]


class ImportRecordIn(BaseModel):
    """`POST /v1/envelopes/import`: record mode (SIG-01 r). Files arrive as upload intents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    purpose: Annotated[Purpose, classified("internal")]
    form_code: Annotated[str | None, Field(max_length=20), classified("internal")] = None
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")] = None
    work_item_id: Annotated[UUID | None, classified("internal")] = None
    title: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    provider_name: Annotated[str, Field(min_length=1, max_length=100), classified("internal")]
    signers: Annotated[
        list[ImportSignerIn], Field(min_length=1, max_length=20), classified("internal")
    ]
    upload_ids: Annotated[list[UUID], Field(min_length=1, max_length=10), classified("internal")]
    attested: Annotated[Literal[True], classified("internal")]


class ImportFileOut(BaseModel):
    """`POST /v1/envelopes/import/files`: one scanned, stored file an import names by `id`."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    media_type: Annotated[str, classified("internal")]
    size_bytes: Annotated[int, classified("internal")]
    sha256: Annotated[str, classified("internal")]


class InPersonIdIn(BaseModel):
    """N-02-T27: the ID a person checked across the desk (type only; never its number)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id_type: Annotated[
        Literal["drivers_license", "passport", "state_id", "military_id", "other"],
        classified("internal"),
    ]
    checked_by_user_id: Annotated[UUID, classified("internal")]


class WetSignatureIn(BaseModel):
    """DF-11: the hand-signed form, uploaded and attested (the scan staged through
    `POST /v1/envelopes/import/files`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    upload_id: Annotated[UUID, classified("internal")]
    signed_on: Annotated[date, classified("internal")]
    attested: Annotated[Literal[True], classified("internal")]
    # N-02-T27 additions (optional): when the paper form arrived, and an in-person ID check.
    received_on: Annotated[date | None, classified("internal")] = None
    in_person_id: Annotated[InPersonIdIn | None, classified("internal")] = None


class SigningSessionOut(BaseModel):
    """A one-time, short-lived provider view (reserved until `signatures.esign_provider`)."""

    model_config = ConfigDict(frozen=True)

    session_id: Annotated[UUID, classified("internal")]
    presentation: Annotated[Literal["iframe", "redirect"], classified("internal")]
    url: Annotated[str, classified("restricted")]
    expires_at: Annotated[datetime, classified("internal")]


class EnvelopePolicyOut(BaseModel):
    """One family's policy; data, not code."""

    model_config = ConfigDict(frozen=True)

    policy_family: Annotated[PolicyFamily, classified("internal")]
    allowed_identity_methods: Annotated[list[IdentityMethod], classified("internal")]
    default_identity_method: Annotated[IdentityMethod, classified("internal")]
    kba_max_attempts: Annotated[int, classified("internal")]
    failure_path: Annotated[Literal["wet_signature"], classified("internal")]
    reminder_cadences: Annotated[list[str], classified("internal")]
    max_reminders: Annotated[int, classified("internal")]
    default_expiry_days: Annotated[int, classified("internal")]
    countersign_required: Annotated[bool, classified("internal")]
    version: Annotated[int, classified("internal")]


class EnvelopePolicyIn(BaseModel):
    """A stricter-only update (AC-9)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed_identity_methods: Annotated[
        list[IdentityMethod], Field(min_length=1), classified("internal")
    ]
    default_identity_method: Annotated[IdentityMethod, classified("internal")]
    kba_max_attempts: Annotated[int, Field(ge=1, le=3), classified("internal")]
    max_reminders: Annotated[int, Field(ge=0, le=10), classified("internal")]
    default_expiry_days: Annotated[int, Field(ge=1, le=120), classified("internal")]
    countersign_required: Annotated[bool, classified("internal")]
    version: Annotated[int, classified("internal")]


# --- Firm routes -------------------------------------------------------------------------------

router = AbacusRouter(prefix="/v1/envelopes", tags=["signatures"])
policies_router = AbacusRouter(prefix="/v1/envelope-policies", tags=["signatures"])
EnvelopeId = UUID


def _row_out(row: hub.EnvelopeRow) -> EnvelopeListRow:
    return EnvelopeListRow(
        id=row.id,
        number=f"E{row.number}",
        purpose=cast(Purpose, row.purpose),
        form_code=row.form_code,
        title=row.title,
        client_id=row.client_id,
        client_name=row.client_name,
        work_item_id=row.work_item_id,
        provider=cast(Provider, row.provider),
        status=cast(EnvelopeStatus, row.status),
        signed=row.signed,
        total=row.total,
        sent_by_name=row.sent_by_name,
        sent_at=row.sent_at,
        due_on=row.due_on,
        needs_handwritten=row.needs_handwritten,
        allowed_actions=list(row.allowed_actions),
        signer_chips=[
            SignerChip(name=c.name, signed=c.signed, signer_id=c.signer_id, locked=c.locked)
            for c in row.signer_chips
        ],
        viewed_at=row.viewed_at,
        work_item_label=row.work_item_label,
        drafted_by_name=row.drafted_by_name,
        outcome=row.outcome,
    )


def _drawer_out(d: hub.Drawer) -> EnvelopeOut:
    return EnvelopeOut(
        row=_row_out(d.row),
        policy_family=cast(PolicyFamily, d.policy_family),
        source_kind=d.source_kind,
        source_id=d.source_id,
        engagement_id=d.row.engagement_id,
        signer_order=cast(SignerOrder, d.signer_order),
        date_as_of_mode=cast(DateAsOfMode, d.date_as_of_mode),
        date_as_of=d.date_as_of,
        expires_at=d.expires_at,
        message=d.message,
        reminder_cadence=d.reminder_cadence,
        documents=[
            EnvelopeDocumentOut(
                id=x.id,
                order=x.order,
                title=x.title,
                page_count=x.page_count,
                sha256=x.sha256,
                read_only=x.read_only,
                tri=x.tri,
            )
            for x in d.documents
        ],
        signers=[
            SignerOut(
                id=x.id,
                order=x.order,
                routing_group=x.routing_group,
                name=x.name,
                role=cast(SignerRole, x.role),
                identity_method=cast(IdentityMethod, x.identity_method),
                status=cast(EnvelopeSignerStatus, x.status),
                kba_failures=x.kba_failures,
                viewed_at=x.viewed_at,
                signed_at=x.signed_at,
                signature_method=cast(SignatureMethod | None, x.signature_method),
                decline_reason=cast(DeclineReason | None, x.decline_reason),
                provider_recipient_id=x.provider_recipient_id,
                title=x.title,
                email=x.email,
            )
            for x in d.signers
        ],
        fields=[
            FieldOut(
                id=x.id,
                document_id=x.document_id,
                signer_id=x.signer_id,
                kind=cast(FieldKind, x.kind),
                page=x.page,
                x=x.x,
                y=x.y,
                w=x.w,
                h=x.h,
                anchor=x.anchor,
            )
            for x in d.fields
        ],
        evidence=[
            EvidenceItem(
                signer_id=x.signer_id,
                signed_at=x.signed_at,
                ip_masked=x.ip_masked,
                identity_result=x.identity_result,
                signature_method=cast(SignatureMethod, x.signature_method),
                user_agent_family=x.user_agent_family,
                device_label=x.device_label,
                package_sha256=x.package_sha256,
            )
            for x in d.evidence
        ],
        provider_envelope_id=d.provider_envelope_id,
        superseded_at=d.superseded_at,
        voided_reason=cast(VoidReason | None, d.voided_reason),
        version=d.version,
    )


@router.get("", action="envelope.read", response_model=ListPage[EnvelopeListRow])
async def list_envelopes_route(
    ctx: Ctx,
    tab: HubTab | None = None,
    purpose: Purpose | None = None,
    status: EnvelopeStatus | None = None,
    client_id: UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListPage[EnvelopeListRow]:
    """SIG-01 list (N-02-T13): wall-safe rows and counts; the Out tab's counts are its tiles."""
    page = await hub.list_envelopes(
        ctx,
        tab=tab,
        purpose=purpose,
        status=status,
        client_id=client_id,
        q=q,
        cursor=cursor,
        limit=limit,
    )
    return listing.envelope(
        [_row_out(r) for r in page.rows],
        next_position=page.next_position,
        tenant_id=ctx.tenant_id,
        resource=hub.LIST_RESOURCE,
        query=page.query,
        total=page.total,
        counts=page.counts,
    )


@router.get("/summary", action="envelope.read", response_model=EnvelopeSummary)
async def envelope_summary_route(ctx: Ctx) -> EnvelopeSummary:
    """SIG-01 tabs and the By type tile (N-02-T13), over visible rows only."""
    made = await hub.summary(ctx)
    return EnvelopeSummary(
        to_send=made.to_send,
        out=made.out,
        completed=made.completed,
        expired=made.expired,
        needs_handwritten=made.needs_handwritten,
        by_type=[TileCount(key=k, n=n) for k, n in made.by_type],
    )


@router.post(
    "/import",
    action="envelope.import_record",
    response_model=EnvelopeOut,
    status_code=201,
    errors=(409,),
)
async def import_envelope_record_route(
    body: ImportRecordIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EnvelopeOut:
    """Record mode (SIG-01 r; N-02-T08): the signed package lands Completed with its evidence."""
    request = imports.ImportRequest(
        purpose=body.purpose,
        form_code=body.form_code,
        client_id=body.client_id,
        engagement_id=body.engagement_id,
        work_item_id=body.work_item_id,
        title=body.title,
        provider_name=body.provider_name,
        signers=tuple(
            imports.SignerFacts(s.contact_id, s.user_id, s.role, s.signed_on, s.identity_method)
            for s in body.signers
        ),
        upload_ids=tuple(body.upload_ids),
    )
    await imports.check_import(ctx, request)

    async def run() -> tuple[int, dict[str, object]]:
        made = await imports.import_record(ctx, request)
        return 201, _imported_out(body, made).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="envelope.import_record",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        run=run,
    )
    return EnvelopeOut.model_validate(stored.body)


@router.post(
    "/import/files",
    action="envelope.import_record",
    response_model=ImportFileOut,
    status_code=201,
    errors=(413, 503),
)
async def stage_envelope_import_file_route(
    request: Request,
    ctx: Ctx,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    client_id: UUID,
    engagement_id: UUID | None = None,
) -> ImportFileOut:
    """One file for a record-mode import into this client (and engagement) (the completed document
    or the certificate), the raw bytes as the body: authorised as the import is, scanned before
    storage, refused closed (N-02-T08; DEC-818)."""
    staged = await imports.stage_file(
        ctx,
        client_id=client_id,
        engagement_id=engagement_id,
        file_name=filename,
        content=await request.body(),
    )
    return ImportFileOut(
        id=staged.id,
        file_name=staged.file_name,
        media_type=staged.media_type,
        size_bytes=staged.size_bytes,
        sha256=staged.sha256,
    )


def _imported_out(body: ImportRecordIn, made: imports.Imported) -> EnvelopeOut:
    signers = [
        SignerOut(
            id=signer_id,
            order=order,
            routing_group=1,
            name=name,
            role=given.role,
            identity_method=given.identity_method,
            status=EnvelopeSignerStatus("signed"),
            kba_failures=0,
            viewed_at=None,
            signed_at=None,
            signature_method="provider_adopted",
            decline_reason=None,
            provider_recipient_id=None,
        )
        for order, (signer_id, name, given) in enumerate(
            zip(made.signer_ids, made.signer_names, body.signers, strict=True), start=1
        )
    ]
    return EnvelopeOut(
        row=EnvelopeListRow(
            id=made.envelope_id,
            number=f"E{made.number}",
            purpose=body.purpose,
            form_code=body.form_code,
            title=body.title,
            client_id=body.client_id,
            client_name=made.client_name,
            work_item_id=body.work_item_id,
            provider="record",
            status=EnvelopeStatus("completed"),
            signed=len(signers),
            total=len(signers),
            sent_by_name=None,
            sent_at=None,
            due_on=None,
            needs_handwritten=False,
            allowed_actions=[],
        ),
        policy_family=imports.policy_family(body.purpose),
        source_kind=imports.SOURCE_KIND,
        source_id=made.envelope_id,
        engagement_id=made.engagement_id,
        signer_order="sequential",
        date_as_of_mode="none",
        date_as_of=None,
        expires_at=None,
        message=None,
        reminder_cadence=None,
        documents=[
            EnvelopeDocumentOut(
                id=made.document_id,
                order=1,
                title=body.title,
                page_count=0,
                sha256=made.document_sha256,
                read_only=True,
                tri=body.purpose in imports.EFILE_PURPOSES,
            )
        ],
        signers=signers,
        fields=[],
        evidence=[],
        provider_envelope_id=None,
        superseded_at=None,
        voided_reason=None,
        version=1,
    )


@router.post("/remind/preview", action="envelope.remind", response_model=RemindOut)
async def remind_envelopes_preview_route(body: RemindIn, ctx: Ctx) -> RemindOut:
    """Who would get a reminder now, under each policy's cap; nothing sent (N-02-T28)."""
    plan = await countersign.remind_preview(ctx, body.envelope_ids)
    return RemindOut(count=plan.count, skipped=list(plan.skipped))


@router.post("/remind/send", action="envelope.remind", response_model=RemindOut, errors=(409,))
async def remind_envelopes_send_route(
    body: RemindIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RemindOut:
    """A person sends the previewed `signature_reminder` version (DEC-74; N-02-T28); 409
    `stale_version` when another version is in use now."""
    plan = await countersign.remind_send(
        ctx, body.envelope_ids, body.template_version_id, body.template_version, idempotency_key
    )
    return RemindOut(count=plan.count, skipped=list(plan.skipped))


@router.get("/{envelope_id}", action="envelope.read", response_model=EnvelopeOut)
async def get_envelope_route(envelope_id: EnvelopeId, ctx: Ctx) -> EnvelopeOut:
    """SIG-01 drawer, SIG-02 builder (N-02-T13)."""
    return _drawer_out(await hub.drawer(ctx, envelope_id))


@router.post(
    "",
    action="envelope.draft",
    response_model=EnvelopeOut,
    status_code=201,
    errors=(409,),
)
async def create_envelope_draft_route(body: DraftIn, ctx: Ctx) -> EnvelopeOut:
    """A draft from a registered source; the agent may call this (N-02-T20)."""
    envelope_id = await builder.create_draft(ctx, body.source_kind, body.source_id)
    return _drawer_out(await hub.drawer(ctx, envelope_id))


@router.put("/{envelope_id}", action="envelope.draft", response_model=EnvelopeOut, errors=(409,))
async def update_envelope_draft_route(
    envelope_id: EnvelopeId, body: DraftUpdateIn, ctx: Ctx, if_match: IfMatch
) -> EnvelopeOut:
    """SIG-02 edits (N-02-T20): 409 `stale_version` when `If-Match` is not the current
    version; 409 `envelope_not_draft` after Send."""
    edit = builder.DraftEdit(
        signers=tuple(
            builder.SignerEdit(
                s.order, s.routing_group, s.contact_id, s.user_id, s.role, s.identity_method
            )
            for s in body.signers
        ),
        signer_order=body.signer_order,
        message=body.message,
        reminder_cadence=body.reminder_cadence,
        expires_on=body.expires_on,
        date_as_of_mode=body.date_as_of_mode,
        date_as_of=body.date_as_of,
        document_order=tuple(body.document_order) if body.document_order is not None else None,
        fields=None
        if body.fields is None
        else tuple(
            builder.FieldEdit(f.document_id, f.signer_index, f.kind, f.page, f.x, f.y, f.w, f.h)
            for f in body.fields
        ),
    )
    await builder.update_draft(ctx, envelope_id, edit, if_match)
    return _drawer_out(await hub.drawer(ctx, envelope_id))


@router.post("/{envelope_id}/validate", action="envelope.draft", response_model=ValidationOut)
async def validate_envelope_route(envelope_id: EnvelopeId, ctx: Ctx) -> ValidationOut:
    """Code-computed checks (N-02-T20)."""
    found = await builder.validate(ctx, envelope_id)
    return ValidationOut(
        ok=found.ok,
        problems=list(found.problems),
        checks=[ValidationCheck(code=c.code, ok=c.ok) for c in found.checks],
    )


@router.get(
    "/{envelope_id}/documents/{document_id}/pages/{page_no}",
    action="envelope.read",
    response_model=bytes,
    errors=(409,),
)
async def envelope_page_route(
    envelope_id: EnvelopeId,
    document_id: UUID,
    page_no: Annotated[int, Path(ge=1, le=2000)],
    ctx: Ctx,
) -> Response:
    """SIG-02's preview page: the document's masked page image as the evidence viewer renders it
    (`no-store`, `nosniff`); 409 `preview_unavailable` for a generated document until P-11, 409
    `preview_outdated` before masking; 403 for a reader who may not read the evidence."""
    page = await builder.document_page(ctx, envelope_id, document_id, page_no)
    return Response(
        content=page,
        media_type="image/png",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.post("/{envelope_id}/send", action="envelope.send", response_model=SendOut, errors=(409,))
async def send_envelope_route(
    envelope_id: EnvelopeId, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SendOut:
    """Human send through a single-use grant, +10 s (N-02-T20): 409 `validation_failed` with
    each check in `facts`; the provider is called after the window (N-02-T22)."""

    await builder.check_send(ctx, envelope_id)

    async def run() -> tuple[int, dict[str, object]]:
        sent = await builder.send(ctx, envelope_id)
        out = SendOut(
            envelope_id=sent.envelope_id, grant_id=sent.grant_id, not_before=sent.not_before
        )
        return 200, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="envelope.send",
        key=idempotency_key,
        body={"envelope_id": str(envelope_id)},
        run=run,
    )
    return SendOut.model_validate(stored.body)


@router.post(
    "/{envelope_id}/send/undo",
    action="envelope.send",
    response_model=EnvelopeOut,
    errors=(409,),
)
async def undo_envelope_send_route(envelope_id: EnvelopeId, ctx: Ctx) -> EnvelopeOut:
    """Undo inside the window (N-02-T20): no provider call is made."""
    await builder.undo_send(ctx, envelope_id)
    return _drawer_out(await hub.drawer(ctx, envelope_id))


@router.post(
    "/{envelope_id}/resend",
    action="envelope.draft",
    response_model=EnvelopeOut,
    status_code=201,
    errors=(409, 501),
)
async def resend_envelope_route(envelope_id: EnvelopeId, ctx: Ctx) -> EnvelopeOut:
    """A new draft copying an expired, declined or voided envelope (N-02-T28)."""
    await _stub(ctx, "envelope.draft")


@router.post(
    "/{envelope_id}/void", action="envelope.void", response_model=EnvelopeOut, errors=(409,)
)
async def void_envelope_route(envelope_id: EnvelopeId, body: VoidIn, ctx: Ctx) -> EnvelopeOut:
    """Void with a reason; evidence kept (N-02-T13)."""
    await hub.void(ctx, envelope_id, body.reason)
    return _drawer_out(await hub.drawer(ctx, envelope_id))


@router.post(
    "/{envelope_id}/signers/{signer_id}/reveal-ip",
    action="signer.reveal_ip",
    response_model=RevealOut,
    errors=(409,),
)
async def reveal_signer_ip_route(
    envelope_id: EnvelopeId, signer_id: UUID, body: RevealIn, ctx: Ctx, response: Response
) -> RevealOut:
    """10-second reveal, audited (N-02-T13); never cached."""
    revealed = await hub.reveal_ip(ctx, envelope_id, signer_id, body.reason)
    response.headers["Cache-Control"] = "no-store"
    return RevealOut(ip=revealed.ip, expires_at=revealed.expires_at)


@router.get(
    "/{envelope_id}/evidence.zip",
    action="envelope.evidence_download",
    response_model=bytes,
)
async def envelope_evidence_route(envelope_id: EnvelopeId, ctx: Ctx) -> Response:
    """Packages, certificate, manifest (N-02-T13); audited, byte-identical on repeat."""
    made = await hub.evidence_package(ctx, envelope_id)
    return Response(
        made.body,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{made.file_name}"',
            "Cache-Control": "no-store",
            "X-Content-SHA256": made.sha256,
        },
    )


@router.post(
    "/{envelope_id}/signers/{signer_id}/wet-signature",
    action="envelope.record_wet_signature",
    response_model=EnvelopeOut,
    errors=(409,),
)
async def record_wet_signature_route(
    envelope_id: EnvelopeId,
    signer_id: UUID,
    body: WetSignatureIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> EnvelopeOut:
    """DF-11: the hand-signed 8879 (N-02-T27): the signer signed, method Handwritten."""
    if ctx.client:
        raise NotFound("envelopes")

    async def run() -> tuple[int, dict[str, object]]:
        await fallback.record_wet_signature(
            ctx,
            envelope_id,
            signer_id,
            fallback.WetSignature(
                upload_id=body.upload_id,
                signed_on=body.signed_on,
                received_on=body.received_on,
                in_person_id=None
                if body.in_person_id is None
                else fallback.InPersonId(
                    body.in_person_id.id_type, body.in_person_id.checked_by_user_id
                ),
            ),
        )
        return 200, _drawer_out(await hub.drawer(ctx, envelope_id)).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="envelope.record_wet_signature",
        key=idempotency_key,
        body={
            "envelope_id": str(envelope_id),
            "signer_id": str(signer_id),
            **body.model_dump(mode="json"),
        },
        run=run,
    )
    return EnvelopeOut.model_validate(stored.body)


@router.post(
    "/{envelope_id}/countersign/session",
    action="envelope.countersign",
    response_model=SigningSessionOut,
    errors=(409,),
)
async def countersign_session_route(envelope_id: EnvelopeId, ctx: Ctx) -> SigningSessionOut:
    """The provider view for the named firm signer only; any other person 403 (N-02-T28)."""
    made = await countersign.countersign_session(ctx, envelope_id)
    return SigningSessionOut(
        session_id=made.id,
        presentation=cast(Literal["iframe", "redirect"], made.presentation),
        url=made.url,
        expires_at=made.expires_at,
    )


@policies_router.get("", action="envelope_policy.read", response_model=list[EnvelopePolicyOut])
async def list_envelope_policies_route(ctx: Ctx) -> list[EnvelopePolicyOut]:
    """The firm's policies: each family's row, else the published floor (N-02-T27)."""
    if ctx.client:
        raise NotFound("envelopes")
    return [_policy_out(p) for p in await fallback.list_policies(ctx)]


@policies_router.put(
    "/{family}",
    action="envelope_policy.manage",
    response_model=EnvelopePolicyOut,
    errors=(409,),
)
async def update_envelope_policy_route(
    family: PolicyFamily, body: EnvelopePolicyIn, ctx: Ctx
) -> EnvelopePolicyOut:
    """Stricter-only against the floor (AC-9; N-02-T27)."""
    if ctx.client:
        raise NotFound("envelopes")
    changed = await fallback.update_policy(
        ctx,
        family,
        fallback.PolicyChange(
            allowed_identity_methods=tuple(body.allowed_identity_methods),
            default_identity_method=body.default_identity_method,
            kba_max_attempts=body.kba_max_attempts,
            max_reminders=body.max_reminders,
            default_expiry_days=body.default_expiry_days,
            countersign_required=body.countersign_required,
            version=body.version,
        ),
    )
    return _policy_out(changed)


def _policy_out(p: fallback.Policy) -> EnvelopePolicyOut:
    return EnvelopePolicyOut(
        policy_family=p.policy_family,
        allowed_identity_methods=[cast(IdentityMethod, m) for m in p.allowed_identity_methods],
        default_identity_method=cast(IdentityMethod, p.default_identity_method),
        kba_max_attempts=p.kba_max_attempts,
        failure_path=p.failure_path,
        reminder_cadences=list(p.reminder_cadences),
        max_reminders=p.max_reminders,
        default_expiry_days=p.default_expiry_days,
        countersign_required=p.countersign_required,
        version=p.version,
    )


# --- Portal routes (POR-06) --------------------------------------------------------------------


class PortalEnvelopeRow(BaseModel):
    """One POR-06 list row, in client words."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    status: Annotated[EnvelopeStatus, classified("internal")]
    my_status: Annotated[EnvelopeSignerStatus, classified("internal")]
    due_on: Annotated[date | None, classified("internal")]


class PortalSignerOut(BaseModel):
    """One signer of the envelope as the portal's signing order shows them (N-02-T29, DEC-1388):
    the name the firm recorded, the role, the routing group and the status. No contact detail."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    role: Annotated[SignerRole, classified("internal")]
    routing_group: Annotated[int, classified("internal")]
    status: Annotated[EnvelopeSignerStatus, classified("internal")]
    signed_at: Annotated[datetime | None, classified("internal")]
    me: Annotated[bool, classified("internal")]


class PortalEnvelopeView(BaseModel):
    """`EnvelopeVM`: steps, documents, fields, signers, my state; `signing_session` and `outcome`
    reserved (null in record mode and until `signatures.esign_provider`). N-02-T29 (additive,
    DEC-1388): the envelope's policy `family`, the viewer's `identity_method`, the `signers` in
    order, and `signing_opens_on`, the `date_as_of` while the firm's today is before it (the
    session's `before_date_as_of` check), else null."""

    model_config = ConfigDict(frozen=True)

    row: Annotated[PortalEnvelopeRow, classified("internal")]
    documents: Annotated[list[EnvelopeDocumentOut], classified("internal")]
    my_fields: Annotated[list[FieldOut], classified("internal")]
    signers_signed: Annotated[int, classified("internal")]
    signers_total: Annotated[int, classified("internal")]
    esign_consent_needed: Annotated[bool, classified("internal")]
    disclosure_version_id: Annotated[UUID | None, classified("internal")]
    date_as_of: Annotated[date | None, classified("internal")]
    paper_form_follows: Annotated[bool, classified("internal")]
    signing_session: Annotated[SigningSessionOut | None, classified("internal")] = None
    outcome: Annotated[
        Literal["signed", "declined", "abandoned"] | None, classified("internal")
    ] = None
    family: Annotated[PolicyFamily, classified("internal")]
    identity_method: Annotated[IdentityMethod, classified("internal")]
    signers: Annotated[list[PortalSignerOut], classified("confidential")]
    signing_opens_on: Annotated[date | None, classified("internal")]


class ConsentIn(BaseModel):
    """ERSD acceptance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    disclosure_version_id: Annotated[UUID, classified("internal")]


class ProgressIn(BaseModel):
    """The last page seen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    last_page_seen: Annotated[int, Field(ge=1, le=2000), classified("internal")]


class SignerDeclineIn(BaseModel):
    """Decline with a reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: Annotated[DeclineReason, classified("internal")]
    note: Annotated[str | None, Field(max_length=1000), classified("confidential")] = None


portal_router = AbacusRouter(prefix="/v1/portal/envelopes", tags=["portal"])

_NO_STORE = {"Cache-Control": "private, no-store"}


def _portal_row(r: portal.ListRow) -> PortalEnvelopeRow:
    return PortalEnvelopeRow(
        id=r.id,
        title=r.title,
        status=cast(EnvelopeStatus, r.status),
        my_status=cast(EnvelopeSignerStatus, r.my_status),
        due_on=r.due_on,
    )


def _portal_view(v: portal.View) -> PortalEnvelopeView:
    return PortalEnvelopeView(
        row=_portal_row(v.row),
        documents=[
            EnvelopeDocumentOut(
                id=d.id,
                order=d.order,
                title=d.title,
                page_count=d.page_count,
                sha256=d.sha256,
                read_only=d.read_only,
                tri=d.tri,
            )
            for d in v.documents
        ],
        my_fields=[
            FieldOut(
                id=f.id,
                document_id=f.document_id,
                signer_id=v.signer_id,
                kind=cast(FieldKind, f.kind),
                page=f.page,
                x=f.x,
                y=f.y,
                w=f.w,
                h=f.h,
                anchor=f.anchor,
            )
            for f in v.my_fields
        ],
        signers_signed=v.signers_signed,
        signers_total=v.signers_total,
        esign_consent_needed=v.esign_consent_needed,
        disclosure_version_id=v.disclosure_version_id,
        date_as_of=v.date_as_of,
        paper_form_follows=v.paper_form_follows,
        outcome=cast(Literal["signed", "declined", "abandoned"] | None, v.outcome),
        family=cast(PolicyFamily, v.family),
        identity_method=cast(IdentityMethod, v.identity_method),
        signers=[
            PortalSignerOut(
                id=p.id,
                name=p.name,
                role=cast(SignerRole, p.role),
                routing_group=p.routing_group,
                status=cast(EnvelopeSignerStatus, p.status),
                signed_at=p.signed_at,
                me=p.id == v.signer_id,
            )
            for p in v.signers
        ],
        signing_opens_on=v.signing_opens_on,
    )


@portal_router.get("", action="portal_envelopes.read", response_model=ListPage[PortalEnvelopeRow])
async def portal_list_route(
    ctx: Member,
    status: Literal["to_sign", "signed"] = "to_sign",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListPage[PortalEnvelopeRow]:
    """POR-06 list (N-02-T23): the person's own signer rows, through `scope_only`."""
    page = await portal.list_mine(ctx, tab=status, cursor=cursor, limit=limit)
    return listing.envelope(
        [_portal_row(r) for r in page.rows],
        next_position=page.next_position,
        tenant_id=ctx.tenant_id,
        resource=portal.LIST_RESOURCE,
        query=page.query,
        total=(len(page.rows), page.next_position is not None),
    )


@portal_router.get(
    "/{envelope_id}", action="portal_envelopes.read", response_model=PortalEnvelopeView
)
async def portal_view_route(envelope_id: EnvelopeId, ctx: Member) -> PortalEnvelopeView:
    """POR-06 review (N-02-T23): the documents, the person's fields and state."""
    return _portal_view(await portal.view(ctx, envelope_id))


@portal_router.get(
    "/{envelope_id}/documents/{document_id}/pages/{page_no}",
    action="portal_envelopes.read",
    response_model=bytes,
    errors=(409,),
)
async def portal_page_route(
    envelope_id: EnvelopeId,
    document_id: UUID,
    page_no: Annotated[int, Path(ge=1, le=2000)],
    ctx: Member,
) -> Response:
    """A masked page the signer reviews (N-02-T23); the read is logged."""
    body = await portal.page(ctx, envelope_id, document_id, page_no)
    return Response(
        content=body,
        media_type="image/png",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@portal_router.post(
    "/{envelope_id}/viewed", action="portal_envelopes.read", response_model=PortalEnvelopeRow
)
async def portal_viewed_route(envelope_id: EnvelopeId, ctx: Member) -> PortalEnvelopeRow:
    """The first view, once (N-02-T23)."""
    return _portal_row(await portal.viewed(ctx, envelope_id))


@portal_router.post(
    "/{envelope_id}/progress", action="portal_envelopes.read", response_model=PortalEnvelopeRow
)
async def portal_progress_route(
    envelope_id: EnvelopeId, body: ProgressIn, ctx: Member
) -> PortalEnvelopeRow:
    """The furthest page seen (N-02-T23)."""
    return _portal_row(await portal.progress(ctx, envelope_id, body.last_page_seen))


@portal_router.post(
    "/{envelope_id}/esign-consent",
    action="portal_envelopes.sign",
    response_model=PortalEnvelopeView,
    errors=(409,),
)
async def portal_consent_route(
    envelope_id: EnvelopeId, body: ConsentIn, ctx: Member
) -> PortalEnvelopeView:
    """ERSD acceptance of the firm's newest disclosure, stored per signer (N-02-T23); 409
    `disclosure_outdated` for any other version."""
    return _portal_view(await portal.consent(ctx, envelope_id, body.disclosure_version_id))


@portal_router.post(
    "/{envelope_id}/signing-session",
    action="portal_envelopes.sign",
    response_model=SigningSessionOut,
    errors=(409, 503),
)
async def portal_signing_session_route(
    envelope_id: EnvelopeId, ctx: Member, idempotency_key: IdempotencyKey, response: Response
) -> SigningSessionOut:
    """A one-time provider view for the named signer (N-02-T23): 409 `envelope_not_open`,
    `declined`, `verification_failed`, `mfa_required`, `not_your_turn`, `before_date_as_of` or
    `esign_consent_required`; 503 `provider_unavailable`. A replay answers the same session while
    it is open; the link is never stored."""
    mine = await portal.check_session(ctx, envelope_id)

    async def run() -> tuple[int, dict[str, object]]:
        made = await portal.issue_session(ctx, mine)
        return 200, {"session_id": str(made)}

    stored = await idempotent(
        ctx.tenant,
        route="portal_envelopes.signing_session",
        key=idempotency_key,
        body={"envelope_id": str(envelope_id)},
        run=run,
    )
    made = await portal.open_session(ctx, mine, UUID(str(stored.body["session_id"])))
    response.headers.update(_NO_STORE)
    return SigningSessionOut(
        session_id=made.id,
        presentation=cast(Literal["iframe", "redirect"], made.presentation),
        url=made.url,
        expires_at=made.expires_at,
    )


@portal_router.get(
    "/{envelope_id}/signing-session/{session_id}/return",
    action="portal_envelopes.sign",
    response_model=PortalEnvelopeView,
)
async def portal_signing_return_route(
    envelope_id: EnvelopeId, session_id: UUID, ctx: Member, response: Response
) -> PortalEnvelopeView:
    """The server-checked return (N-02-T23): the provider is polled before anything is shown;
    query parameters are ignored, and `outcome` is `signed` only once the poll says so."""
    view = await portal.signing_return(ctx, envelope_id, session_id)
    response.headers.update(_NO_STORE)
    return _portal_view(view)


@portal_router.post(
    "/{envelope_id}/decline",
    action="portal_envelopes.decline",
    response_model=PortalEnvelopeView,
    errors=(409,),
)
async def portal_decline_route(
    envelope_id: EnvelopeId, body: SignerDeclineIn, ctx: Member
) -> PortalEnvelopeView:
    """Decline with a reason (N-02-T23); signing sessions are refused while declined."""
    return _portal_view(await portal.decline(ctx, envelope_id, body.reason, body.note))


@portal_router.post(
    "/{envelope_id}/decline/withdraw",
    action="portal_envelopes.decline",
    response_model=PortalEnvelopeView,
    errors=(409,),
)
async def portal_decline_withdraw_route(
    envelope_id: EnvelopeId, ctx: Member
) -> PortalEnvelopeView:
    """Withdraw the person's own portal decline while the envelope is Declined (N-02-T23);
    409 `decline_not_withdrawable` otherwise."""
    return _portal_view(await portal.withdraw_decline(ctx, envelope_id))


@portal_router.get(
    "/{envelope_id}/download",
    action="portal_envelopes.download",
    response_model=bytes,
    errors=(409,),
)
async def portal_download_route(envelope_id: EnvelopeId, ctx: Member) -> Response:
    """The signed copy with its evidence pages, audited (N-02-T23); 409
    `signed_copy_not_ready` until evidence is recorded."""
    made = await portal.signed_copy(ctx, envelope_id)
    return Response(
        made.body,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{made.file_name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "X-Content-SHA256": made.sha256,
        },
    )
