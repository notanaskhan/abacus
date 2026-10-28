"""C7 envelope service v1, the stubs (N-02-T03; N-02 §4.3; ADR-149; SPEC-381).
Contract: `docs/contracts/c7-envelopes.md`.

Every route answers 404 with `signatures.envelopes` off and 501 `not_implemented` with it on
until its task lands: record-mode import N-02-T08; the hub, drawer, evidence and reminders
T11-T15; drafts, validate, sends, void T18-T22, T30; portal signing T23-T29; policies T13.

Rules the shapes carry:
- **Record mode first** (ADR-149): `provider` is `record`, `docusign` or `fake`; a record-mode
  envelope never has provider fields or a signing session.
- **People send** (AC-16): drafting is the only verb the agent and the system hold.
- **No SMS for the 8879 family** (AC-8): `IdentityMethod` has no `sms_code`.
- **Masked by default**: a signer's IP is `ip_masked` only; the reveal is its own audited route.
  No SSN or TIN field exists on any shape.
- **Reserved**: `provider_envelope_id`, `provider_recipient_id`, `signing_session` and
  `outcome` are null until `signatures.docusign` (N-02-T18 onward).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

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
from abacus.modules.signatures import imports

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
Provider = Literal["docusign", "record", "fake"]
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


async def _portal_stub(ctx: AuthContext) -> NoReturn:
    """A firm principal never reaches portal signing: 404. Then the flag, then 501; the named
    signer and `scope_only` are the implementation's checks."""
    if not ctx.client:
        raise NotFound("portal envelopes")
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


class ValidationOut(BaseModel):
    """Code-computed checks before send."""

    model_config = ConfigDict(frozen=True)

    ok: Annotated[bool, classified("internal")]
    problems: Annotated[list[str], classified("internal")]


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
    template_version_id: Annotated[UUID, classified("internal")]


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


class WetSignatureIn(BaseModel):
    """DF-11: the hand-signed form, uploaded and attested."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    upload_id: Annotated[UUID, classified("internal")]
    signed_on: Annotated[date, classified("internal")]
    attested: Annotated[Literal[True], classified("internal")]


class SigningSessionOut(BaseModel):
    """A one-time, short-lived provider view (reserved until `signatures.docusign`)."""

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


@router.get("", action="envelope.read", response_model=ListPage[EnvelopeListRow], errors=(501,))
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
    """SIG-01 list (N-02-T13)."""
    await _stub(ctx, "envelope.read")


@router.get("/summary", action="envelope.read", response_model=EnvelopeSummary, errors=(501,))
async def envelope_summary_route(ctx: Ctx) -> EnvelopeSummary:
    """SIG-01 tiles (N-02-T13)."""
    await _stub(ctx, "envelope.read")


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
) -> ImportFileOut:
    """One file for a record-mode import (the completed document or the certificate), the raw
    bytes as the body: scanned before storage, refused closed (N-02-T08; DEC-818)."""
    staged = await imports.stage_file(ctx, file_name=filename, content=await request.body())
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


@router.post("/remind/preview", action="envelope.remind", response_model=RemindOut, errors=(501,))
async def remind_envelopes_preview_route(body: RemindIn, ctx: Ctx) -> RemindOut:
    """Template preview, nothing sent (N-02-T14)."""
    await _stub(ctx, "envelope.remind")


@router.post("/remind/send", action="envelope.remind", response_model=RemindOut, errors=(409, 501))
async def remind_envelopes_send_route(
    body: RemindIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RemindOut:
    """A person sends the template reminder (DEC-74; N-02-T14)."""
    await _stub(ctx, "envelope.remind")


@router.get("/{envelope_id}", action="envelope.read", response_model=EnvelopeOut, errors=(501,))
async def get_envelope_route(envelope_id: EnvelopeId, ctx: Ctx) -> EnvelopeOut:
    """SIG-01 drawer, SIG-02 builder (N-02-T11)."""
    await _stub(ctx, "envelope.read")


@router.post(
    "", action="envelope.draft", response_model=EnvelopeOut, status_code=201, errors=(409, 501)
)
async def create_envelope_draft_route(body: DraftIn, ctx: Ctx) -> EnvelopeOut:
    """A draft from a registered source; the agent may call this (N-02-T20)."""
    await _stub(ctx, "envelope.draft")


@router.put(
    "/{envelope_id}", action="envelope.draft", response_model=EnvelopeOut, errors=(409, 501)
)
async def update_envelope_draft_route(
    envelope_id: EnvelopeId, body: DraftUpdateIn, ctx: Ctx, if_match: IfMatch
) -> EnvelopeOut:
    """SIG-02 edits (N-02-T20)."""
    await _stub(ctx, "envelope.draft")


@router.post(
    "/{envelope_id}/validate", action="envelope.draft", response_model=ValidationOut, errors=(501,)
)
async def validate_envelope_route(envelope_id: EnvelopeId, ctx: Ctx) -> ValidationOut:
    """Code-computed checks (N-02-T20)."""
    await _stub(ctx, "envelope.draft")


@router.get(
    "/{envelope_id}/documents/{document_id}/pages/{page_no}",
    action="envelope.read",
    response_model=bytes,
    errors=(501,),
)
async def envelope_page_route(
    envelope_id: EnvelopeId, document_id: UUID, page_no: int, ctx: Ctx
) -> Response:
    """Rendered preview page (N-02-T21)."""
    await _stub(ctx, "envelope.read")


@router.post(
    "/{envelope_id}/send", action="envelope.send", response_model=SendOut, errors=(409, 501)
)
async def send_envelope_route(
    envelope_id: EnvelopeId, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SendOut:
    """Human send through a single-use grant, +10 s (N-02-T22)."""
    await _stub(ctx, "envelope.send")


@router.post(
    "/{envelope_id}/send/undo",
    action="envelope.send",
    response_model=EnvelopeOut,
    errors=(409, 501),
)
async def undo_envelope_send_route(envelope_id: EnvelopeId, ctx: Ctx) -> EnvelopeOut:
    """Undo inside the window (N-02-T22)."""
    await _stub(ctx, "envelope.send")


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
    "/{envelope_id}/void", action="envelope.void", response_model=EnvelopeOut, errors=(409, 501)
)
async def void_envelope_route(envelope_id: EnvelopeId, body: VoidIn, ctx: Ctx) -> EnvelopeOut:
    """Void with a reason; evidence kept (N-02-T28)."""
    await _stub(ctx, "envelope.void")


@router.post(
    "/{envelope_id}/signers/{signer_id}/reveal-ip",
    action="signer.reveal_ip",
    response_model=RevealOut,
    errors=(501,),
)
async def reveal_signer_ip_route(
    envelope_id: EnvelopeId, signer_id: UUID, body: RevealIn, ctx: Ctx
) -> RevealOut:
    """10-second reveal, audited (N-02-T13)."""
    await _stub(ctx, "signer.reveal_ip")


@router.get(
    "/{envelope_id}/evidence.zip",
    action="envelope.evidence_download",
    response_model=bytes,
    errors=(501,),
)
async def envelope_evidence_route(envelope_id: EnvelopeId, ctx: Ctx) -> Response:
    """Packages, certificate, manifest (N-02-T14)."""
    await _stub(ctx, "envelope.evidence_download")


@router.post(
    "/{envelope_id}/signers/{signer_id}/wet-signature",
    action="envelope.record_wet_signature",
    response_model=EnvelopeOut,
    errors=(409, 501),
)
async def record_wet_signature_route(
    envelope_id: EnvelopeId,
    signer_id: UUID,
    body: WetSignatureIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> EnvelopeOut:
    """DF-11: the hand-signed 8879 (N-02-T27)."""
    await _stub(ctx, "envelope.record_wet_signature")


@router.post(
    "/{envelope_id}/countersign/session",
    action="envelope.countersign",
    response_model=SigningSessionOut,
    errors=(409, 501),
)
async def countersign_session_route(envelope_id: EnvelopeId, ctx: Ctx) -> SigningSessionOut:
    """The provider view for the named firm signer (N-02-T28)."""
    await _stub(ctx, "envelope.countersign")


@policies_router.get(
    "", action="envelope_policy.read", response_model=list[EnvelopePolicyOut], errors=(501,)
)
async def list_envelope_policies_route(ctx: Ctx) -> list[EnvelopePolicyOut]:
    """The firm's policies (N-02-T13)."""
    await _stub(ctx, "envelope_policy.read")


@policies_router.put(
    "/{family}",
    action="envelope_policy.manage",
    response_model=EnvelopePolicyOut,
    errors=(409, 501),
)
async def update_envelope_policy_route(
    family: PolicyFamily, body: EnvelopePolicyIn, ctx: Ctx
) -> EnvelopePolicyOut:
    """Stricter-only (AC-9; N-02-T13)."""
    await _stub(ctx, "envelope_policy.manage")


# --- Portal routes (POR-06) --------------------------------------------------------------------


class PortalEnvelopeRow(BaseModel):
    """One POR-06 list row, in client words."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    status: Annotated[EnvelopeStatus, classified("internal")]
    my_status: Annotated[EnvelopeSignerStatus, classified("internal")]
    due_on: Annotated[date | None, classified("internal")]


class PortalEnvelopeView(BaseModel):
    """`EnvelopeVM`: steps, documents, fields, signers, my state; `signing_session` and `outcome`
    reserved (null in record mode and until `signatures.docusign`)."""

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


@portal_router.get(
    "", action="portal_envelopes.read", response_model=ListPage[PortalEnvelopeRow], errors=(501,)
)
async def portal_list_route(
    ctx: Member,
    status: Literal["to_sign", "signed"] = "to_sign",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListPage[PortalEnvelopeRow]:
    """POR-06 list (N-02-T23)."""
    await _portal_stub(ctx)


@portal_router.get(
    "/{envelope_id}",
    action="portal_envelopes.read",
    response_model=PortalEnvelopeView,
    errors=(501,),
)
async def portal_view_route(envelope_id: EnvelopeId, ctx: Member) -> PortalEnvelopeView:
    """POR-06 review (N-02-T23)."""
    await _portal_stub(ctx)


@portal_router.get(
    "/{envelope_id}/documents/{document_id}/pages/{page_no}",
    action="portal_envelopes.read",
    response_model=bytes,
    errors=(501,),
)
async def portal_page_route(
    envelope_id: EnvelopeId, document_id: UUID, page_no: int, ctx: Member
) -> Response:
    """A page the signer reviews (N-02-T23)."""
    await _portal_stub(ctx)


@portal_router.post(
    "/{envelope_id}/viewed",
    action="portal_envelopes.read",
    response_model=PortalEnvelopeRow,
    errors=(501,),
)
async def portal_viewed_route(envelope_id: EnvelopeId, ctx: Member) -> PortalEnvelopeRow:
    """Viewed (N-02-T23)."""
    await _portal_stub(ctx)


@portal_router.post(
    "/{envelope_id}/progress",
    action="portal_envelopes.read",
    response_model=PortalEnvelopeRow,
    errors=(501,),
)
async def portal_progress_route(
    envelope_id: EnvelopeId, body: ProgressIn, ctx: Member
) -> PortalEnvelopeRow:
    """Last page seen (N-02-T23)."""
    await _portal_stub(ctx)


@portal_router.post(
    "/{envelope_id}/esign-consent",
    action="portal_envelopes.sign",
    response_model=PortalEnvelopeView,
    errors=(409, 501),
)
async def portal_consent_route(
    envelope_id: EnvelopeId, body: ConsentIn, ctx: Member
) -> PortalEnvelopeView:
    """ERSD acceptance, stored (N-02-T24)."""
    await _portal_stub(ctx)


@portal_router.post(
    "/{envelope_id}/signing-session",
    action="portal_envelopes.sign",
    response_model=SigningSessionOut,
    errors=(409, 501),
)
async def portal_signing_session_route(
    envelope_id: EnvelopeId, ctx: Member, idempotency_key: IdempotencyKey
) -> SigningSessionOut:
    """One-time provider view; refusals in the contract (N-02-T26)."""
    await _portal_stub(ctx)


@portal_router.get(
    "/{envelope_id}/signing-session/{session_id}/return",
    action="portal_envelopes.sign",
    response_model=PortalEnvelopeView,
    errors=(409, 501),
)
async def portal_signing_return_route(
    envelope_id: EnvelopeId, session_id: UUID, ctx: Member
) -> PortalEnvelopeView:
    """Server-checked return (N-02-T26)."""
    await _portal_stub(ctx)


@portal_router.post(
    "/{envelope_id}/decline",
    action="portal_envelopes.decline",
    response_model=PortalEnvelopeView,
    errors=(409, 501),
)
async def portal_decline_route(
    envelope_id: EnvelopeId, body: SignerDeclineIn, ctx: Member
) -> PortalEnvelopeView:
    """Decline with a reason (N-02-T28)."""
    await _portal_stub(ctx)


@portal_router.post(
    "/{envelope_id}/decline/withdraw",
    action="portal_envelopes.decline",
    response_model=PortalEnvelopeView,
    errors=(409, 501),
)
async def portal_decline_withdraw_route(
    envelope_id: EnvelopeId, ctx: Member
) -> PortalEnvelopeView:
    """Withdraw a decline while open (N-02-T28)."""
    await _portal_stub(ctx)


@portal_router.get(
    "/{envelope_id}/download",
    action="portal_envelopes.download",
    response_model=bytes,
    errors=(501,),
)
async def portal_download_route(envelope_id: EnvelopeId, ctx: Member) -> Response:
    """Signed copy plus evidence page, audited (N-02-T29)."""
    await _portal_stub(ctx)
