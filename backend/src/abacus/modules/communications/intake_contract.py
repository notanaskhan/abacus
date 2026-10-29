"""C5 v1.2 intake half: firm intake, the stubs (N-01-T02; N-01 §4.3; ADR-210; SPEC-380).
Contract: `docs/contracts/firm-intake.md`.

Each route answers 404 with `inbox.firm_intake` off and 501 `not_implemented` with it on until
its task lands: staff-logged intake in N-01-T09; the summary, threads, viewer and downloads in
T13; matching, triage, destinations, apply and bulk-file in T18.

Rules the shapes carry:
- **One model, many channels** (ADR-210 clause 1): `email`, `portal_upload`, `staff_logged`.
- **People decide** (clause 5): every write here is a person's; the matrix denies the agent and
  the system, and a decision row is `actor_kind = 'human'` by CHECK (N-01-T07).
- **Unmatched threads** are the intake scope's only, by sender and subject (clause 3).
- **Facts are identifiers**: flag facts carry ids, years and masked last-4 only; numbers are
  computed by code (ADR-050).
- **Uploads** follow the repo's raw-body pattern: the batch first, then one request per file
  (`?filename=`), scanned before storage and refused closed when the scanner is down (DEC-703).
- Classification: subjects, sender and file names are confidential; bodies and notes are sealed
  (restricted) and never on these shapes except through `inbox.read_content`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import INBOX_FIRM_INTAKE
from abacus.kernel._statuses import InboxItemStatus, InboxThreadStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import (
    DomainConflict,
    DomainTooLarge,
    DomainUnavailable,
    DomainUnsupported,
    NotFound,
    NotImplementedYet,
)
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.communications import intake
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    authorise_with_scope,
    current_context,
    in_intake_scope,
    mask_tins_for,
    walled_from,
)
from abacus.modules.organisations.api import MaskedTinOut

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

SourceKind = Literal["mailbox", "portal", "staff"]
Channel = Literal["email", "portal_upload", "staff_logged"]
ReceivedVia = Literal["email", "mail", "fax", "in_person", "portal", "other"]
MatchMethod = Literal[
    "contact_email", "sender_rule", "portal_principal", "staff_selected", "manual", "none"
]
Decision = Literal["file", "ignore", "hold"]
VersionMode = Literal["new_document", "new_version", "new_version_supersede"]
DestinationKind = Literal[
    "request", "permanent_file", "work_item_folder", "notice", "close_receipt"
]
FolderKind = Literal[
    "source_documents", "workpapers", "correspondence", "deliverables", "signed_authorizations"
]
FlagKind = Literal[
    "duplicate_hash",
    "wrong_year",
    "tin_mismatch",
    "possible_replacement",
    "corrected_form",
    "unreadable",
    "low_confidence",
    "ambiguous_candidates",
    "duplicate_of_notice",
]
FlagSeverity = Literal["info", "block_bulk", "force_hold"]
SuggestionSource = Literal["rule", "content", "matcher", "none"]
IgnoreReason = Literal["wrong_year", "duplicate", "not_ours", "spam", "unreadable", "other"]
BulkOutcome = Literal["ok", "has_flags", "low_confidence", "proposal_changed"]
Fingerprint = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]


# --- Errors (N-01 §4.10; the catalogue is rebuilt from these classes) ----------------------------


class DecisionRequired(DomainConflict):
    """An attachment in the apply has no decision, or a forced Hold was answered otherwise."""

    code = "decision_required"


class HasFlags(DomainConflict):
    """A flagged attachment cannot be bulk-filed: review it in File… (INB-01 e)."""

    code = "has_flags"


class LowConfidence(DomainConflict):
    """The top destination is below the bulk threshold or ambiguous: choose it in File…."""

    code = "low_confidence"


class ItemClosed(DomainConflict):
    """The destination request or work item closed since the triage was read."""

    code = "item_closed"


class DestinationArchived(DomainConflict):
    """The destination engagement or folder is archived: read-only."""

    code = "destination_archived"


class AttachmentFiled(DomainConflict):
    """The attachment was already filed: it cannot be decided or withdrawn again."""

    code = "attachment_filed"


class AttachmentWithdrawn(DomainConflict):
    """The client withdrew the attachment before it was filed (ADR-162)."""

    code = "attachment_withdrawn"


class IntakeNotAllowed(DomainConflict):
    """The principal's shell cannot use intake (third party, K-1 only, TCWG, prospect)."""

    code = "intake_not_allowed"


class UnsupportedMediaType(DomainUnsupported):
    """Not one of PDF, JPG, PNG, HEIC, XLSX, DOCX or CSV: 415."""

    code = "unsupported_media_type"


class FileTooLarge(DomainTooLarge):
    """Over 50 MB: 413."""

    code = "file_too_large"


class ScannerUnavailable(DomainUnavailable):
    """The malware scanner is unreachable; every intake path fails closed (P-64): 503."""

    code = "scanner_unavailable"


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    """A client principal never reaches the firm inbox: 404. Then the route's action at the firm
    (the agent and the system refused on every write: 403, before the flag is read), then the
    flag, then 501."""
    if ctx.client:
        raise NotFound("inbox")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, INBOX_FIRM_INTAKE):
        raise NotFound(INBOX_FIRM_INTAKE.name)
    raise NotImplementedYet


# --- Shapes --------------------------------------------------------------------------------------


class SourceCount(BaseModel):
    """One intake source's waiting count (the rail pill and its menu)."""

    model_config = ConfigDict(frozen=True)

    source_kind: Annotated[SourceKind, classified("internal")]
    source_display: Annotated[str | None, classified("confidential")]
    waiting: Annotated[int, classified("internal")]


class InboxSummaryOut(BaseModel):
    """`GET /v1/inbox/summary`: counted over rows the viewer can see only (DEC-43)."""

    model_config = ConfigDict(frozen=True)

    waiting: Annotated[int, classified("internal")]
    unmatched: Annotated[int, classified("internal")]
    by_source: Annotated[list[SourceCount], classified("internal")]


class InboxThreadRow(BaseModel):
    """One rail row (INB-01)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    source_kind: Annotated[SourceKind, classified("internal")]
    channel: Annotated[Channel, classified("internal")]
    match_state: Annotated[InboxThreadStatus, classified("internal")]
    client_id: Annotated[UUID | None, classified("internal")]
    client_name: Annotated[str | None, classified("confidential")]
    subject_display: Annotated[str, classified("confidential")]
    sender_display: Annotated[str, classified("confidential")]
    last_received_at: Annotated[datetime, classified("internal")]
    # The roll-up dot: `new` while any attachment is new, else the most pressing state.
    status: Annotated[InboxItemStatus, classified("internal")]
    waiting: Annotated[int, classified("internal")]
    message_count: Annotated[int, classified("internal")]


class AttachmentFlagOut(BaseModel):
    """A code-raised flag; `facts` hold identifiers, years and masked last-4 only."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[FlagKind, classified("internal")]
    severity: Annotated[FlagSeverity, classified("internal")]
    ref_evidence_version_id: Annotated[UUID | None, classified("internal")]
    facts: Annotated[dict[str, str | int | bool], classified("internal")]


class FiledDestinationOut(BaseModel):
    """Where a person filed an attachment, for the "Filed to …" line."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[DestinationKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]
    path: Annotated[list[str], classified("confidential")]
    route: Annotated[str, classified("internal")]


class InboxAttachmentOut(BaseModel):
    """One attachment on a message, with its state and what it may do (`allowed_actions`)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    media_type: Annotated[str, classified("internal")]
    size_bytes: Annotated[int, classified("internal")]
    fingerprint: Annotated[Fingerprint, classified("internal")]
    status: Annotated[InboxItemStatus, classified("internal")]
    flags: Annotated[list[AttachmentFlagOut], classified("internal")]
    filed: Annotated[FiledDestinationOut | None, classified("internal")]
    ignored_reason: Annotated[IgnoreReason | None, classified("internal")]
    held_at: Annotated[datetime | None, classified("internal")]
    thumbnail_ref: Annotated[str | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class InboundMessageOut(BaseModel):
    """One received message. `body` is present only with `inbox.read_content`."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    channel: Annotated[Channel, classified("internal")]
    received_via: Annotated[ReceivedVia | None, classified("internal")]
    sender_display: Annotated[str, classified("confidential")]
    logged_by_name: Annotated[str | None, classified("internal")]
    subject_display: Annotated[str, classified("confidential")]
    received_at: Annotated[datetime, classified("internal")]
    body: Annotated[str | None, classified("restricted")]
    attachments: Annotated[list[InboxAttachmentOut], classified("internal")]


class InboxThreadDetail(BaseModel):
    """`GET /v1/inbox/threads/{id}`: messages newest first."""

    model_config = ConfigDict(frozen=True)

    thread: Annotated[InboxThreadRow, classified("internal")]
    match_method: Annotated[MatchMethod, classified("internal")]
    work_item_label: Annotated[str | None, classified("confidential")]
    messages: Annotated[list[InboundMessageOut], classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    version: Annotated[int, classified("internal")]


class LogIntakeIn(BaseModel):
    """`POST /v1/inbox/intake`: a staff-logged batch; files follow, one request each."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: Annotated[UUID | None, classified("internal")] = None
    client_entity_id: Annotated[UUID | None, classified("internal")] = None
    received_via: Annotated[ReceivedVia, classified("internal")]
    from_contact_id: Annotated[UUID | None, classified("internal")] = None
    from_display: Annotated[str | None, Field(max_length=320), classified("confidential")] = None
    received_at: Annotated[date, classified("internal")]
    subject: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    note: Annotated[str | None, Field(max_length=4000), classified("restricted")] = None


class IntakeCreatedOut(BaseModel):
    """The new thread and the message its files attach to."""

    model_config = ConfigDict(frozen=True)

    thread_id: Annotated[UUID, classified("internal")]
    message_id: Annotated[UUID, classified("internal")]


class IntakeFileOut(BaseModel):
    """One stored file of an intake batch."""

    model_config = ConfigDict(frozen=True)

    attachment_id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    status: Annotated[InboxItemStatus, classified("internal")]


class MatchClientIn(BaseModel):
    """`POST /v1/inbox/threads/{id}/match-client` (INB-01 b)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    client_id: Annotated[UUID, classified("internal")]
    client_entity_id: Annotated[UUID | None, classified("internal")] = None
    remember_sender: Annotated[bool, classified("internal")] = False
    seen_version: Annotated[int, classified("internal")]


class IgnoreThreadIn(BaseModel):
    """`POST /v1/inbox/threads/{id}/ignore` for an unmatched sender."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason_code: Annotated[IgnoreReason, classified("internal")]
    note: Annotated[str | None, Field(max_length=2000), classified("restricted")] = None


class ClassificationOut(BaseModel):
    """What code (or the matcher) says the file is; agent values carry citations or none."""

    model_config = ConfigDict(frozen=True)

    form_family: Annotated[str | None, classified("internal")]
    form_code: Annotated[str | None, classified("internal")]
    tax_year: Annotated[int | None, classified("internal")]
    issuer_name: Annotated[str | None, classified("confidential")]
    page_count: Annotated[int | None, classified("internal")]
    taxpayer_tin: Annotated[MaskedTinOut | None, classified("restricted")]  # P-12: last four only
    taxpayer_matches_client: Annotated[bool | None, classified("internal")]
    proposed_by_kind: Annotated[Literal["rule", "agent"], classified("internal")]
    citation_ids: Annotated[list[UUID], classified("internal")]


class DestinationCandidate(BaseModel):
    """A ranked destination with its code-computed confidence."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[DestinationKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]
    path: Annotated[list[str], classified("confidential")]
    confidence: Annotated[float, classified("internal")]
    source: Annotated[SuggestionSource, classified("internal")]
    request_state: Annotated[str | None, classified("internal")]
    requested_on: Annotated[date | None, classified("internal")]
    proposal_id: Annotated[UUID | None, classified("internal")]


class TriageDefaults(BaseModel):
    """What the sheet opens with; a person may change every field before Apply."""

    model_config = ConfigDict(frozen=True)

    decision: Annotated[Decision, classified("internal")]
    decision_forced: Annotated[bool, classified("internal")]
    reason_codes: Annotated[list[IgnoreReason], classified("internal")]
    rename_to: Annotated[str | None, classified("confidential")]
    version_mode: Annotated[VersionMode | None, classified("internal")]
    tell_client: Annotated[bool, classified("internal")]
    template_key: Annotated[str | None, classified("internal")]


class AttachmentTriageOut(BaseModel):
    """One card of INB-02."""

    model_config = ConfigDict(frozen=True)

    attachment: Annotated[InboxAttachmentOut, classified("internal")]
    classification: Annotated[ClassificationOut | None, classified("internal")]
    candidates: Annotated[list[DestinationCandidate], classified("internal")]
    supersede_candidate_version_id: Annotated[UUID | None, classified("internal")]
    defaults: Annotated[TriageDefaults, classified("internal")]


class MessageTriageOut(BaseModel):
    """`GET /v1/inbox/messages/{id}/triage`."""

    model_config = ConfigDict(frozen=True)

    message_id: Annotated[UUID, classified("internal")]
    attachments: Annotated[list[AttachmentTriageOut], classified("internal")]
    seen_proposals: Annotated[list[UUID], classified("internal")]
    classified_at: Annotated[datetime | None, classified("internal")]
    notify_names: Annotated[list[str], classified("internal")]


class DestinationRef(BaseModel):
    """A chosen destination."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[DestinationKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class TriageDecisionIn(BaseModel):
    """One attachment's decision in an apply."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment_id: Annotated[UUID, classified("internal")]
    decision: Annotated[Decision, classified("internal")]
    destination: Annotated[DestinationRef | None, classified("internal")] = None
    version_mode: Annotated[VersionMode | None, classified("internal")] = None
    supersede_version_id: Annotated[UUID | None, classified("internal")] = None
    keep_both: Annotated[bool, classified("internal")] = False
    rename_to: Annotated[str | None, Field(max_length=255), classified("confidential")] = None
    reason_codes: Annotated[list[IgnoreReason], classified("internal")] = []
    tell_client: Annotated[bool, classified("internal")] = False


class TriageApplyIn(BaseModel):
    """`POST /v1/inbox/messages/{id}/triage/apply`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decisions: Annotated[
        list[TriageDecisionIn], Field(min_length=1, max_length=50), classified("internal")
    ]
    seen_proposals: Annotated[list[UUID], classified("internal")] = []


class TriageApplyOut(BaseModel):
    """What the apply wrote; `undo_grant_id` while a client email waits its 10 s (DEC-24)."""

    model_config = ConfigDict(frozen=True)

    filed: Annotated[int, classified("internal")]
    ignored: Annotated[int, classified("internal")]
    held: Annotated[int, classified("internal")]
    notified_user_ids: Annotated[list[UUID], classified("internal")]
    undo_grant_id: Annotated[UUID | None, classified("internal")]


class BulkFileIn(BaseModel):
    """`POST /v1/inbox/attachments/bulk-file` (INB-01 e)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attachment_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=100), classified("internal")
    ]
    seen_proposals: Annotated[list[UUID], classified("internal")] = []


class BulkFileResult(BaseModel):
    """One attachment's outcome."""

    model_config = ConfigDict(frozen=True)

    attachment_id: Annotated[UUID, classified("internal")]
    outcome: Annotated[BulkOutcome, classified("internal")]


class BulkFileOut(BaseModel):
    """Per-item outcomes; `ok` items are filed as suggested."""

    model_config = ConfigDict(frozen=True)

    results: Annotated[list[BulkFileResult], classified("internal")]
    notified_user_ids: Annotated[list[UUID], classified("internal")]


class DestinationNode(BaseModel):
    """A picker node: client > work item > request, permanent file, folders, registered kinds."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[DestinationKind | Literal["client", "work_item"], classified("internal")]
    id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]
    folder_kind: Annotated[FolderKind | None, classified("internal")]
    has_children: Annotated[bool, classified("internal")]
    selectable: Annotated[bool, classified("internal")]
    # Why a node cannot take a file (`archived`, `closed`), a code.
    reason_code: Annotated[str | None, classified("internal")]


class IntakeViewerManifestOut(BaseModel):
    """The C4 viewer manifest over an intake object (masked pages only)."""

    model_config = ConfigDict(frozen=True)

    attachment_id: Annotated[UUID, classified("internal")]
    page_count: Annotated[int, classified("internal")]
    masked: Annotated[bool, classified("internal")]
    page_refs: Annotated[list[str], classified("internal")]


# --- Routes --------------------------------------------------------------------------------------

intake_router = AbacusRouter(prefix="/v1/inbox", tags=["inbox"])
destinations_router = AbacusRouter(prefix="/v1", tags=["inbox"])


@intake_router.get("/summary", action="inbox.read", response_model=InboxSummaryOut, errors=(501,))
async def inbox_summary_route(ctx: Ctx) -> InboxSummaryOut:
    """INB-01 "23 waiting · 4 unmatched", over visible rows only (N-01-T13)."""
    await _stub(ctx, "inbox.read")


@intake_router.get(
    "/threads", action="inbox.read", response_model=ListPage[InboxThreadRow], errors=(501,)
)
async def list_threads_route(
    ctx: Ctx,
    source: SourceKind | None = None,
    client_id: UUID | None = None,
    status: InboxItemStatus | None = None,
    received_since: date | None = None,
    channel: Channel | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    show_ignored: bool = False,
    show_filed: bool = True,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListPage[InboxThreadRow]:
    """INB-01 rail, `last_received_at` descending (N-01-T13)."""
    await _stub(ctx, "inbox.read")


@intake_router.get(
    "/threads/{thread_id}", action="inbox.read", response_model=InboxThreadDetail, errors=(501,)
)
async def get_thread_route(thread_id: UUID, ctx: Ctx) -> InboxThreadDetail:
    """INB-01 reading pane; bodies only with `inbox.read_content` (N-01-T13)."""
    await _stub(ctx, "inbox.read")


@intake_router.post(
    "/intake",
    action="inbox.log_intake",
    response_model=IntakeCreatedOut,
    status_code=201,
    errors=(409,),
)
async def log_intake_route(
    body: LogIntakeIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> IntakeCreatedOut:
    """Log received documents (DV-1): the batch, one thread and one message; files follow
    (N-01-T09). The intake scope or `inbox.log_intake` on the named client; people only."""
    await _log_check(ctx, body.client_id)

    async def run() -> tuple[int, dict[str, object]]:
        made = await intake.record_inbound_message(
            ctx.tenant,
            intake.Inbound(
                channel="staff_logged",
                sender_display=body.from_display or "Logged by staff",
                subject=body.subject,
                received_at=datetime.combine(body.received_at, time(12, 0), tzinfo=UTC),
                body=body.note,
                client_id=body.client_id,
                client_entity_id=body.client_entity_id,
                from_contact_id=body.from_contact_id,
                logged_by=ctx.user_id,
                received_via=body.received_via,
            ),
        )
        out = IntakeCreatedOut(thread_id=made.thread_id, message_id=made.message_id)
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="inbox.log_intake",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        run=run,
    )
    return IntakeCreatedOut.model_validate(stored.body)


@intake_router.post(
    "/intake/{message_id}/files",
    action="inbox.log_intake",
    response_model=IntakeFileOut,
    status_code=201,
    errors=(409, 413, 503),
)
async def log_intake_file_route(
    message_id: UUID,
    request: Request,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
) -> IntakeFileOut:
    """One file of a staff-logged batch, scanned before storage, fail closed (N-01-T09). Only the
    person who logged the batch adds to it."""
    facts = await intake.message_facts(ctx.tenant, message_id)
    if facts.channel != "staff_logged" or facts.logged_by != ctx.user_id:
        await _log_check(ctx, facts.client_id)
        raise NotFound("inbound_message")
    await _log_check(ctx, facts.client_id)
    content = await request.body()

    async def run() -> tuple[int, dict[str, object]]:
        made = await intake.add_attachment(
            ctx.tenant, message_id, file_name=filename, content=content
        )
        out = IntakeFileOut(
            attachment_id=made.attachment_id,
            file_name=made.file_name,
            status=InboxItemStatus(made.status),
        )
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="inbox.log_intake_file",
        key=idempotency_key,
        body={"message_id": str(message_id), "filename": filename, "size": len(content)},
        run=run,
    )
    return IntakeFileOut.model_validate(stored.body)


async def _log_check(ctx: AuthContext, client_id: UUID | None) -> None:
    """A firm person (404 for a client principal); a person on an intake team may log for any
    client or none; anyone else needs `inbox.log_intake` on the named client (the wall 404s).
    The agent and the system are refused by the matrix before the flag is read."""
    if ctx.client:
        raise NotFound("inbox")
    resource = (
        Resource.firm(ctx.tenant_id)
        if client_id is None
        else Resource.client(ctx.tenant_id, client_id)
    )
    in_scope = ctx.tenant.actor_kind == "human" and await in_intake_scope(ctx.tenant, ctx.user_id)
    # The intake scope logs for any client (DEC-20) except one its member is walled from: 404,
    # as if it did not exist (DEC-43).
    if (
        in_scope
        and client_id is not None
        and client_id in await walled_from(ctx.tenant, ctx.user_id)
    ):
        raise NotFound("client")
    await authorise_with_scope(ctx, "inbox.log_intake", resource, in_scope=in_scope)
    if not await flag_enabled(ctx.tenant, INBOX_FIRM_INTAKE):
        raise NotFound(INBOX_FIRM_INTAKE.name)


@intake_router.post(
    "/threads/{thread_id}/match-client",
    action="inbox.match_sender",
    response_model=InboxThreadDetail,
    errors=(409, 501),
)
async def match_client_route(thread_id: UUID, body: MatchClientIn, ctx: Ctx) -> InboxThreadDetail:
    """INB-01 b: attachments New → Waiting; "Remember sender" also needs
    `inbox_sender_rule.create` (N-01-T18)."""
    await _stub(ctx, "inbox.match_sender")


@intake_router.post(
    "/threads/{thread_id}/ignore",
    action="inbox.triage",
    response_model=InboxThreadDetail,
    errors=(409, 501),
)
async def ignore_thread_route(
    thread_id: UUID, body: IgnoreThreadIn, ctx: Ctx
) -> InboxThreadDetail:
    """INB-01 b "Ignore" for an unmatched sender (N-01-T18)."""
    await _stub(ctx, "inbox.triage")


@intake_router.get(
    "/attachments/{attachment_id}/viewer",
    action="inbox.read_content",
    response_model=IntakeViewerManifestOut,
    errors=(501,),
)
async def attachment_viewer_route(attachment_id: UUID, ctx: Ctx) -> IntakeViewerManifestOut:
    """SHL-08 over an intake object; masked pages only (N-01-T13)."""
    await _stub(ctx, "inbox.read_content")


@intake_router.get(
    "/attachments/{attachment_id}/content",
    action="inbox.download",
    response_model=bytes,
    errors=(501,),
)
async def attachment_content_route(attachment_id: UUID, ctx: Ctx) -> Response:
    """Audited download, `no-store` (N-01-T13)."""
    await _stub(ctx, "inbox.download")


@intake_router.get(
    "/messages/{message_id}/attachments.zip",
    action="inbox.download",
    response_model=bytes,
    errors=(501,),
)
async def message_zip_route(message_id: UUID, ctx: Ctx) -> Response:
    """ "Download All": stdlib zip, audited, `no-store` (N-01-T13)."""
    await _stub(ctx, "inbox.download")


@intake_router.get(
    "/messages/{message_id}/triage",
    action="inbox.triage",
    response_model=MessageTriageOut,
    errors=(501,),
)
async def message_triage_route(message_id: UUID, ctx: Ctx) -> MessageTriageOut:
    """INB-02's cards (N-01-T18). A card's classification carries a masked TIN, masked again for
    an offshore reader (review 6)."""
    return await mask_tins_for(ctx, await _stub(ctx, "inbox.triage"))


@intake_router.post(
    "/messages/{message_id}/triage/apply",
    action="inbox.file",
    response_model=TriageApplyOut,
    errors=(409, 501),
)
async def triage_apply_route(
    message_id: UUID, body: TriageApplyIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TriageApplyOut:
    """INB-02 "Apply n": one insert-only decision per attachment by a live human; Ignore needs
    `inbox.triage` and Hold `inbox.ask_client` too (N-01-T18)."""
    await _stub(ctx, "inbox.file")


@intake_router.post(
    "/attachments/bulk-file",
    action="inbox.file",
    response_model=BulkFileOut,
    errors=(409, 501),
)
async def bulk_file_route(
    body: BulkFileIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> BulkFileOut:
    """INB-01 e "File n as suggested": unflagged, confident, unchanged only (N-01-T18)."""
    await _stub(ctx, "inbox.file")


@destinations_router.get(
    "/destinations",
    action="inbox.triage",
    response_model=list[DestinationNode],
    errors=(501,),
)
async def destinations_route(
    ctx: Ctx,
    client_id: UUID,
    kind: DestinationKind | None = None,
    parent: UUID | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> list[DestinationNode]:
    """INB-02 path-chip pickers; nodes re-authorised, closed nodes carry a reason (N-01-T18)."""
    await _stub(ctx, "inbox.triage")
