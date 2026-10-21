"""Evidence routes (SPEC-000 §8; TASK-012 Q1), and review queues and decisions (SPEC-004).
Provenance only: content is read through `read_version`, never listed."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints

from abacus.kernel._statuses import RequestStatus
from abacus.kernel.classification import classified
from abacus.modules.evidence.board_summary import board_summary
from abacus.modules.evidence.client_view import client_view
from abacus.modules.evidence.inbox import (
    InboxEntry,
    add_to_inbox,
    check_inbox,
    discard,
    inbox,
    inbox_preview,
    inbox_preview_page,
)
from abacus.modules.evidence.inbox import (
    assign as assign_inbox_file,
)
from abacus.modules.evidence.item_detail import ItemVersion, download, item_versions
from abacus.modules.evidence.service import (
    Decision,
    DecisionView,
    EvidenceVersionSummary,
    Proposal,
    QueueEntry,
    assign,
    decide,
    evidence_versions_for,
    reason_codes_for,
    release,
    review_queue,
    review_waiting,
    take,
)
from abacus.modules.evidence.setup_files import download_setup_file, upload_setup_file
from abacus.modules.evidence.statement_review import (
    Decisions,
    StatementView,
    approve_statement,
    statement_for,
)
from abacus.modules.evidence.unlock import unlock_upload
from abacus.modules.evidence.uploads import (
    MAX_UPLOAD_BYTES,
    PreviewView,
    UploadTooLarge,
    UploadView,
    check_upload,
    upload,
    upload_checks,
    upload_preview,
    upload_preview_page,
    uploads_for,
)
from abacus.modules.identity.api import (
    OWN,
    AbacusRouter,
    AuthContext,
    current_context,
    current_member,
)

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["evidence"])
Method = Literal["retrieved", "uploaded", "imported"]
PreviewKind = Literal["pages", "image", "table", "none", "pending"]


class EvidenceVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    evidence_item_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    method: Annotated[Method, classified("internal")]
    source: Annotated[str, classified("internal")]
    pulled_at: Annotated[datetime | None, classified("internal")]
    period_start: Annotated[date | None, classified("internal")]
    period_end: Annotated[date | None, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    # SPEC-029 (TASK-057): problem checks on its latest check run (the Board's marker).
    problems: Annotated[int, classified("internal")] = 0


def _out(version: EvidenceVersionSummary) -> EvidenceVersionOut:
    return EvidenceVersionOut.model_validate(version, from_attributes=True)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.get("/evidence-versions", action="evidence.read", response_model=list[EvidenceVersionOut])
async def list_evidence_versions_route(engagement_id: UUID, ctx: Ctx) -> list[EvidenceVersionOut]:
    return [_out(v) for v in await evidence_versions_for(ctx, engagement_id)]


# --- Review queues and decisions (SPEC-004) ---------------------------------------------------


class CitationOut(BaseModel):
    """A checked citation of the proposal (the same shape as the board's)."""

    model_config = ConfigDict(frozen=True)

    cell: Annotated[str, classified("internal")]
    quote: Annotated[str | None, classified("confidential")]
    value: Annotated[str | None, classified("confidential")]
    verified: Annotated[bool, classified("internal")]
    reason: Annotated[
        Literal["cell_not_found", "quote_mismatch", "value_mismatch"] | None,
        classified("internal"),
    ] = None


class ProposalOut(BaseModel):
    """The agent's proposal. Rationale and quotes are model text: shown as plain text (ADR-065)."""

    model_config = ConfigDict(frozen=True)

    screening_result_id: Annotated[UUID, classified("internal")]
    action: Annotated[Literal["ready_for_review", "needs_revision"], classified("internal")]
    confidence: Annotated[Decimal, classified("internal")]
    rationale: Annotated[str, classified("confidential")]
    citations: Annotated[list[CitationOut], classified("confidential")]
    unverified: Annotated[list[str], classified("confidential")]


class QueueEntryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version: Annotated[EvidenceVersionOut, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    item_description: Annotated[str, classified("confidential")]
    item_audit_area: Annotated[str, classified("internal")]
    proposal: Annotated[ProposalOut | None, classified("confidential")]
    assignee_user_id: Annotated[UUID | None, classified("internal")]


class TakenOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    assignee_user_id: Annotated[UUID | None, classified("internal")]


class AssignIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]


# May discuss client data: stored confidential, never logged (AC-9). Blank notes don't count.
Note = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2000),
    classified("confidential"),
]
# The proposal the reviewer was shown (None: none was), so a correction is recorded against what
# they saw; a newer one answers 409 `proposal_changed` (AC-10).
SeenProposal = Annotated[UUID | None, classified("internal")]


class AcceptIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    note: Note = None
    seen_proposal: SeenProposal = None


class RejectIn(BaseModel):
    """Reject or send back: a reason code from the catalogue is required (AC-7, AC-8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z_]{0,49}$"), classified("public")]
    note: Note = None
    seen_proposal: SeenProposal = None


class DecisionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    request_item_ids: Annotated[list[UUID], classified("internal")]
    decision: Annotated[Literal["accept", "reject", "send_back"], classified("internal")]
    reason_code: Annotated[str | None, classified("public")]
    corrects_proposal: Annotated[bool, classified("internal")]
    item_status: Annotated[RequestStatus, classified("internal")]


class ReasonCodeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("public")]
    label: Annotated[str, classified("public")]
    description: Annotated[str, classified("public")]
    requires_note: Annotated[bool, classified("public")]


def _proposal_out(p: Proposal) -> ProposalOut:
    return ProposalOut.model_validate(p, from_attributes=True)


def _entry_out(e: QueueEntry) -> QueueEntryOut:
    return QueueEntryOut(
        evidence_version=_out(e.evidence_version),
        request_item_id=e.request_item_id,
        item_description=e.item_description,
        item_audit_area=e.item_audit_area,
        proposal=_proposal_out(e.proposal) if e.proposal is not None else None,
        assignee_user_id=e.assignee_user_id,
    )


@router.get("/review-queue", action="review.read", response_model=list[QueueEntryOut])
async def review_queue_route(engagement_id: UUID, ctx: Ctx) -> list[QueueEntryOut]:
    return [_entry_out(e) for e in await review_queue(ctx, engagement_id)]


@router.post(
    "/review-queue/{version_id}/take", action="review.take", response_model=TakenOut, errors=(409,)
)
async def take_route(engagement_id: UUID, version_id: UUID, ctx: Ctx) -> TakenOut:
    await take(ctx, engagement_id, version_id)
    return TakenOut(evidence_version_id=version_id, assignee_user_id=ctx.user_id)


@router.post(
    "/review-queue/{version_id}/release",
    action="review.take",
    response_model=TakenOut,
    errors=(409,),
)
async def release_route(engagement_id: UUID, version_id: UUID, ctx: Ctx) -> TakenOut:
    await release(ctx, engagement_id, version_id)
    return TakenOut(evidence_version_id=version_id, assignee_user_id=None)


@router.post(
    "/review-queue/{version_id}/assign",
    action="review.assign",
    response_model=TakenOut,
    errors=(409,),
)
async def assign_route(
    engagement_id: UUID, version_id: UUID, body: AssignIn, ctx: Ctx
) -> TakenOut:
    await assign(ctx, engagement_id, version_id, body.user_id)
    return TakenOut(evidence_version_id=version_id, assignee_user_id=body.user_id)


def _decision_out(d: DecisionView) -> DecisionOut:
    return DecisionOut.model_validate(d, from_attributes=True)


async def _decide(
    ctx: AuthContext,
    engagement_id: UUID,
    version_id: UUID,
    kind: Decision,
    *,
    reason_code: str | None,
    note: str | None,
    seen_proposal: UUID | None,
) -> DecisionOut:
    view = await decide(
        ctx,
        engagement_id,
        version_id,
        kind,
        reason_code=reason_code,
        note=note,
        seen_proposal=seen_proposal,
    )
    return _decision_out(view)


_DECISION_ERRORS = (409, 503)  # plus 401/403/404/422, which every route declares


# One route per matrix action (AbacusRouter: one action per route): accept is `evidence.accept`;
# reject and send back are `evidence.reject`.
@router.post(
    "/evidence-versions/{version_id}/decision/accept",
    action="evidence.accept",
    response_model=DecisionOut,
    status_code=201,
    errors=_DECISION_ERRORS,
)
async def accept_route(
    engagement_id: UUID, version_id: UUID, body: AcceptIn, ctx: Ctx
) -> DecisionOut:
    return await _decide(
        ctx,
        engagement_id,
        version_id,
        "accept",
        reason_code=None,
        note=body.note,
        seen_proposal=body.seen_proposal,
    )


@router.post(
    "/evidence-versions/{version_id}/decision/reject",
    action="evidence.reject",
    response_model=DecisionOut,
    status_code=201,
    errors=_DECISION_ERRORS,
)
async def reject_route(
    engagement_id: UUID, version_id: UUID, body: RejectIn, ctx: Ctx
) -> DecisionOut:
    return await _decide(
        ctx,
        engagement_id,
        version_id,
        "reject",
        reason_code=body.reason_code,
        note=body.note,
        seen_proposal=body.seen_proposal,
    )


@router.post(
    "/evidence-versions/{version_id}/decision/send-back",
    action="evidence.reject",
    response_model=DecisionOut,
    status_code=201,
    errors=_DECISION_ERRORS,
)
async def send_back_route(
    engagement_id: UUID, version_id: UUID, body: RejectIn, ctx: Ctx
) -> DecisionOut:
    return await _decide(
        ctx,
        engagement_id,
        version_id,
        "send_back",
        reason_code=body.reason_code,
        note=body.note,
        seen_proposal=body.seen_proposal,
    )


@router.get(
    "/review-reason-codes/{applies_to}", action="review.read", response_model=list[ReasonCodeOut]
)
async def reason_codes_route(
    engagement_id: UUID, applies_to: Literal["reject", "send_back"], ctx: Ctx
) -> list[ReasonCodeOut]:
    return [
        ReasonCodeOut.model_validate(c, from_attributes=True)
        for c in await reason_codes_for(ctx, engagement_id, applies_to)
    ]


# --- Client uploads (SPEC-020; TASK-035) -------------------------------------------------------


class UploadOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    # The client's file name: untrusted text, shown as plain text only (ADR-052).
    file_name: Annotated[str, classified("confidential")]
    media_type: Annotated[str, classified("internal")]
    size_bytes: Annotated[int, classified("internal")]
    uploaded_by: Annotated[UUID | None, classified("internal")]
    uploaded_by_name: Annotated[str, classified("confidential")]
    uploaded_at: Annotated[datetime, classified("internal")]
    # SPEC-023: added by the firm for the client, and where it came from (plain text).
    on_behalf: Annotated[bool, classified("internal")] = False
    note: Annotated[str | None, classified("confidential")] = None


def _upload_out(view: UploadView) -> UploadOut:
    return UploadOut.model_validate(view, from_attributes=True)


async def _file(request: Request) -> bytes:
    """The raw file body (SPEC-008 D3), refused past the limit before it is all read."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_UPLOAD_BYTES:
            raise UploadTooLarge
    return bytes(data)


class CheckOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    outcome: Annotated[Literal["passed", "problem", "not_applicable"], classified("internal")]
    audience: Annotated[Literal["client", "firm"], classified("internal")]
    document_kind: Annotated[str | None, classified("internal")]
    reason: Annotated[str | None, classified("internal")]
    expected_date: Annotated[date | None, classified("confidential")]
    found_date: Annotated[date | None, classified("confidential")]
    amount: Annotated[Decimal | None, classified("confidential")]
    difference: Annotated[Decimal | None, classified("confidential")]
    account_code: Annotated[str | None, classified("confidential")]
    ref_item_id: Annotated[UUID | None, classified("internal")]


class SheetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("confidential")]
    rows: Annotated[list[list[str]], classified("restricted")]


class PreviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[PreviewKind, classified("internal")]
    reason: Annotated[str | None, classified("internal")]
    page_count: Annotated[int, classified("internal")]
    truncated: Annotated[bool, classified("internal")]
    sheets: Annotated[list[SheetOut], classified("restricted")]


def _preview_out(view: PreviewView) -> PreviewOut:
    return PreviewOut(
        kind=cast(PreviewKind, view.kind),  # the service returns only these
        reason=view.reason,
        page_count=view.page_count,
        truncated=view.truncated,
        sheets=[SheetOut(name=n, rows=[list(r) for r in rows]) for n, rows in view.sheets],
    )


def _png_response(content: bytes) -> Response:
    """A server-made PNG (ADR-110): never the raw upload, never cached, never sniffed."""
    return Response(
        content=content,
        media_type="image/png",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


@router.get(
    "/request-items/{item_id}/uploads/{version_id}/preview",
    action="evidence.read",
    response_model=PreviewOut,
)
async def upload_preview_route(
    engagement_id: UUID, item_id: UUID, version_id: UUID, ctx: Ctx
) -> PreviewOut:
    """SPEC-029 AC-12: what the viewer shows ("pending" until the workflow has made it)."""
    return _preview_out(await upload_preview(ctx, engagement_id, item_id, version_id))


@router.get(
    "/request-items/{item_id}/uploads/{version_id}/preview/pages/{page_no}",
    action="evidence.read",
    response_model=bytes,
)
async def upload_preview_page_route(
    engagement_id: UUID,
    item_id: UUID,
    version_id: UUID,
    page_no: Annotated[int, Path(ge=1, le=50)],
    ctx: Ctx,
) -> Response:
    return _png_response(
        await upload_preview_page(ctx, engagement_id, item_id, version_id, page_no)
    )


@router.get("/inbox/{file_id}/preview", action="evidence.upload", response_model=PreviewOut)
async def inbox_preview_route(engagement_id: UUID, file_id: UUID, ctx: Ctx) -> PreviewOut:
    """SPEC-029 AC-12, Q8: an inbox file's preview, for whoever may see the file."""
    return _preview_out(await inbox_preview(ctx, engagement_id, file_id))


@router.get(
    "/inbox/{file_id}/preview/pages/{page_no}", action="evidence.upload", response_model=bytes
)
async def inbox_preview_page_route(
    engagement_id: UUID,
    file_id: UUID,
    page_no: Annotated[int, Path(ge=1, le=50)],
    ctx: Ctx,
) -> Response:
    return _png_response(await inbox_preview_page(ctx, engagement_id, file_id, page_no))


@router.get(
    "/request-items/{item_id}/uploads/{version_id}/checks",
    action="evidence.read",
    response_model=list[CheckOut],
)
async def upload_checks_route(
    engagement_id: UUID, item_id: UUID, version_id: UUID, ctx: Ctx
) -> list[CheckOut]:
    """SPEC-029 AC-6 to AC-11: what code found in an upload; client roles see only theirs."""
    return [
        CheckOut.model_validate(c, from_attributes=True)
        for c in await upload_checks(ctx, engagement_id, item_id, version_id)
    ]


# --- Statement transactions (SPEC-312; TASK-324) ---------------------------------------------


class ExclusionBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    position: Annotated[int, Field(ge=1), classified("internal")]
    reason: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]


class StatementDecisionsBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    excluded: Annotated[list[ExclusionBody], Field(max_length=5000), classified("internal")] = []
    flip_signs: Annotated[bool, classified("internal")] = False
    opening: Annotated[
        Decimal | None, Field(max_digits=16, decimal_places=2), classified("confidential")
    ] = None
    closing: Annotated[
        Decimal | None, Field(max_digits=16, decimal_places=2), classified("confidential")
    ] = None


class StatementLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: Annotated[int, classified("internal")]
    posted_on: Annotated[date | None, classified("internal")]
    description: Annotated[str, classified("confidential")]
    amount: Annotated[Decimal, classified("confidential")]
    page: Annotated[int | None, classified("internal")]
    excluded: Annotated[bool, classified("internal")]
    exclusion_reason: Annotated[str | None, classified("confidential")]


class ReconciliationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    opening: Annotated[Decimal | None, classified("confidential")]
    lines_total: Annotated[Decimal, classified("confidential")]
    expected_closing: Annotated[Decimal | None, classified("confidential")]
    closing: Annotated[Decimal | None, classified("confidential")]
    difference: Annotated[Decimal | None, classified("confidential")]
    reconciled: Annotated[bool, classified("internal")]


class StatementOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[Literal["draft", "approved"], classified("internal")]
    format: Annotated[Literal["pdf_text", "csv", "ofx"], classified("internal")]
    account_kind: Annotated[Literal["credit_card", "bank", "unknown"], classified("internal")]
    issuer: Annotated[str | None, classified("confidential")]
    last4: Annotated[str | None, classified("internal")]
    period_start: Annotated[date | None, classified("internal")]
    period_end: Annotated[date | None, classified("internal")]
    opening: Annotated[Decimal | None, classified("confidential")]
    closing: Annotated[Decimal | None, classified("confidential")]
    opening_source: Annotated[Literal["printed", "entered"] | None, classified("internal")]
    closing_source: Annotated[Literal["printed", "entered"] | None, classified("internal")]
    printed_opening: Annotated[bool, classified("internal")]
    printed_closing: Annotated[bool, classified("internal")]
    signs_inferred: Annotated[bool, classified("internal")]
    signs_flipped: Annotated[bool, classified("internal")]
    truncated: Annotated[bool, classified("internal")]
    lines: Annotated[list[StatementLineOut], classified("confidential")]
    reconciliation: Annotated[ReconciliationOut, classified("confidential")]
    approved_by_name: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")]


def _decisions(body: StatementDecisionsBody) -> Decisions:
    return Decisions(
        {e.position: e.reason for e in body.excluded}, body.flip_signs, body.opening, body.closing
    )


def _statement_out(v: StatementView) -> StatementOut:
    return StatementOut.model_validate(
        {
            **asdict(v),
            "lines": [asdict(line) for line in v.lines],
            "reconciliation": asdict(v.reconciliation),
        }
    )


_STATEMENT = "/request-items/{item_id}/uploads/{version_id}/statement"


@router.get(_STATEMENT, action="evidence.read", response_model=StatementOut, errors=(409,))
async def statement_route(
    engagement_id: UUID, item_id: UUID, version_id: UUID, ctx: Ctx
) -> StatementOut:
    """SPEC-312 AC-5: the statement's transactions: approved, or read from the file."""
    return _statement_out(await statement_for(ctx, engagement_id, item_id, version_id))


@router.post(
    _STATEMENT + "/preview", action="evidence.read", response_model=StatementOut, errors=(409,)
)
async def statement_preview_route(
    engagement_id: UUID, item_id: UUID, version_id: UUID, body: StatementDecisionsBody, ctx: Ctx
) -> StatementOut:
    """SPEC-312 AC-6: the reviewer's decisions applied and reconciled; nothing stored."""
    return _statement_out(
        await statement_for(ctx, engagement_id, item_id, version_id, _decisions(body))
    )


@router.post(
    _STATEMENT + "/approve",
    action="statement.approve",
    response_model=StatementOut,
    status_code=201,
    errors=(409,),
)
async def approve_statement_route(
    engagement_id: UUID, item_id: UUID, version_id: UUID, body: StatementDecisionsBody, ctx: Ctx
) -> StatementOut:
    """SPEC-312 AC-7: a person approves the reconciled transactions."""
    return _statement_out(
        await approve_statement(ctx, engagement_id, item_id, version_id, _decisions(body))
    )


class UnlockBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Used once to open the file; never stored, logged or echoed (TASK-323).
    password: Annotated[SecretStr, Field(min_length=1, max_length=256), classified("restricted")]


@router.post(
    "/request-items/{item_id}/uploads/{version_id}/unlock",
    action="evidence.upload",
    response_model=UploadOut,
    status_code=201,
    errors=(409,),
)
async def unlock_upload_route(
    engagement_id: UUID, item_id: UUID, version_id: UUID, body: UnlockBody, ctx: Ctx
) -> UploadOut:
    """TASK-323: a password-protected PDF upload, saved again without its password as a new
    version of the item."""
    await check_upload(ctx, engagement_id, item_id)
    return _upload_out(
        await unlock_upload(
            ctx, engagement_id, item_id, version_id, body.password.get_secret_value()
        )
    )


@router.post(
    "/request-items/{item_id}/uploads",
    action="evidence.upload",
    response_model=UploadOut,
    status_code=201,
    errors=(409,),
)
async def upload_route(
    engagement_id: UUID,
    item_id: UUID,
    request: Request,
    ctx: Ctx,
    filename: Annotated[str, Query(min_length=1, max_length=1000)],
    on_behalf: bool = False,
    note: Annotated[str | None, Query(max_length=2000)] = None,
) -> UploadOut:
    """SPEC-020 AC-8, AC-9: a file for a request item, stored as new evidence. With
    `on_behalf`, the firm's team adds it for the client (SPEC-023 AC-1)."""
    await check_upload(ctx, engagement_id, item_id)
    content = await _file(request)
    return _upload_out(
        await upload(
            ctx,
            engagement_id,
            item_id,
            file_name=filename,
            content=content,
            on_behalf=on_behalf,
            note=note,
        )
    )


@router.get(
    "/request-items/{item_id}/uploads", action="evidence.read", response_model=list[UploadOut]
)
async def list_uploads_route(engagement_id: UUID, item_id: UUID, ctx: Ctx) -> list[UploadOut]:
    """SPEC-020: the item's uploads, newest first."""
    return [_upload_out(v) for v in await uploads_for(ctx, engagement_id, item_id)]


# --- The client's view of a request (SPEC-031; TASK-060) --------------------------------------


class ProvidedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: Annotated[Literal["connection", "export"], classified("internal")]
    on: Annotated[datetime, classified("internal")]


class GapOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    covered: Annotated[list[str], classified("confidential")]
    needed: Annotated[list[str], classified("confidential")]


class HistoryEntryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    added_by: Annotated[Literal["firm", "client"], classified("internal")]
    added_by_name: Annotated[str, classified("confidential")]
    added_at: Annotated[datetime, classified("internal")]
    outcome: Annotated[
        Literal["in_review", "replaced", "accepted", "sent_back", "not_accepted"],
        classified("internal"),
    ]
    reason_label: Annotated[str | None, classified("internal")] = None
    note: Annotated[str | None, classified("confidential")] = None


class ClientViewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    provided: Annotated[ProvidedOut | None, classified("internal")] = None
    gap: Annotated[GapOut | None, classified("confidential")] = None
    history: Annotated[list[HistoryEntryOut], classified("confidential")]


@router.get(
    "/request-items/{item_id}/client-view", action="evidence.read", response_model=ClientViewOut
)
async def client_view_route(engagement_id: UUID, item_id: UUID, ctx: Ctx) -> ClientViewOut:
    """SPEC-031 AC-4, AC-5, AC-7: provided, the bank statement gap, and the item's history."""
    view = await client_view(ctx, engagement_id, item_id)
    return ClientViewOut.model_validate(view, from_attributes=True)


# --- Request item detail (SPEC-021; TASK-037) --------------------------------------------------


class DecisionSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: Annotated[str, classified("internal")]
    reason_code: Annotated[str | None, classified("internal")]
    decided_by: Annotated[UUID | None, classified("internal")]
    decided_by_name: Annotated[str, classified("confidential")]
    decided_at: Annotated[datetime, classified("internal")]


class ItemVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    method: Annotated[Method, classified("internal")]
    source: Annotated[str, classified("internal")]
    period_start: Annotated[date | None, classified("internal")]
    period_end: Annotated[date | None, classified("internal")]
    pulled_at: Annotated[datetime | None, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    size_bytes: Annotated[int, classified("internal")]
    media_type: Annotated[str, classified("internal")]
    fingerprint: Annotated[str, classified("internal")]
    # The client's file name for uploads: untrusted text, shown as plain text only (ADR-052).
    file_name: Annotated[str | None, classified("confidential")]
    uploaded_by: Annotated[UUID | None, classified("internal")]
    uploaded_by_name: Annotated[str, classified("confidential")]
    decision: Annotated[DecisionSummaryOut | None, classified("internal")]
    on_behalf: Annotated[bool, classified("internal")] = False
    note: Annotated[str | None, classified("confidential")] = None


def _version_out(v: ItemVersion) -> ItemVersionOut:
    return ItemVersionOut.model_validate(v, from_attributes=True)


@router.get(
    "/request-items/{item_id}/versions",
    action="evidence.read",
    response_model=list[ItemVersionOut],
)
async def item_versions_route(
    engagement_id: UUID, item_id: UUID, ctx: Ctx
) -> list[ItemVersionOut]:
    """SPEC-021 AC-1: the item's versions, newest first, with provenance and decisions."""
    return [_version_out(v) for v in await item_versions(ctx, engagement_id, item_id)]


@router.get(
    "/evidence-versions/{version_id}/content",
    action="evidence.read",
    response_model=bytes,
    errors=(409,),
)
async def content_route(engagement_id: UUID, version_id: UUID, ctx: Ctx) -> Response:
    """SPEC-021 AC-2: the file as an attachment, never inline (ADR-052); audited and verified."""
    file = await download(ctx, engagement_id, version_id)
    return Response(
        content=file.content,
        media_type=file.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{file.file_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


# --- The evidence board's summary (SPEC-022 AC-5; TASK-038) ------------------------------------


class BoardSummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: Annotated[int, classified("internal")]
    by_status: Annotated[dict[str, int], classified("internal")]
    by_tier: Annotated[dict[str, int], classified("internal")]
    unclassified: Annotated[int, classified("internal")]
    retrieved_never_asked: Annotated[int, classified("internal")]
    retrievable_share: Annotated[float | None, classified("internal")]


@router.get("/board-summary", action="request_item.read", response_model=BoardSummaryOut)
async def board_summary_route(engagement_id: UUID, ctx: Ctx) -> BoardSummaryOut:
    """Counts by status and tier, "retrieved, never asked" and the retrievable share."""
    return BoardSummaryOut.model_validate(
        await board_summary(ctx, engagement_id), from_attributes=True
    )


# --- The engagement inbox (SPEC-023; TASK-039) -------------------------------------------------


class ReasonOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[
        Literal["kind", "date", "account", "holder", "file_name"], classified("internal")
    ]
    value: Annotated[str | None, classified("confidential")] = None


class SuggestionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    score: Annotated[int, classified("internal")]
    matched: Annotated[list[str], classified("confidential")]
    # SPEC-033 (TASK-064): where it came from, and why (fixed codes; values computed by code).
    source: Annotated[Literal["matcher", "content", "file_name"], classified("internal")] = (
        "file_name"
    )
    reasons: Annotated[list[ReasonOut], classified("confidential")] = []


class InboxFileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    media_type: Annotated[str, classified("internal")]
    size_bytes: Annotated[int, classified("internal")]
    uploaded_by: Annotated[UUID, classified("internal")]
    uploaded_by_name: Annotated[str, classified("confidential")]
    uploaded_by_staff: Annotated[bool, classified("internal")]
    note: Annotated[str | None, classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]
    suggestions: Annotated[list[SuggestionOut], classified("internal")]


def _inbox_out(entry: InboxEntry) -> InboxFileOut:
    return InboxFileOut(
        id=entry.id,
        file_name=entry.file_name,
        media_type=entry.media_type,
        size_bytes=entry.size_bytes,
        uploaded_by=entry.uploaded_by,
        uploaded_by_name=entry.uploaded_by_name,
        uploaded_by_staff=entry.uploaded_by_staff,
        note=entry.note,
        created_at=entry.created_at,
        suggestions=[
            SuggestionOut.model_validate(
                {
                    "request_item_id": s.request_item_id,
                    "score": s.score,
                    "matched": list(s.matched),
                    "source": s.source,
                    "reasons": [{"code": r.code, "value": r.value} for r in s.reasons],
                }
            )
            for s in entry.suggestions
        ],
    )


class InboxAssignIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_item_id: Annotated[UUID, classified("internal")]
    followed_suggestion: Annotated[bool, classified("internal")] = False
    # SPEC-033 AC-6 (TASK-064): which suggestion was followed, and its rank.
    suggestion_source: Annotated[
        Literal["file_name", "content", "matcher"] | None, classified("internal")
    ] = None
    suggestion_rank: Annotated[int | None, Field(ge=1, le=3), classified("internal")] = None


class AssignedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]


class DiscardedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]


@router.post(
    "/inbox", action="evidence.upload", response_model=InboxFileOut, status_code=201, errors=(409,)
)
async def add_to_inbox_route(
    engagement_id: UUID,
    request: Request,
    ctx: Ctx,
    filename: Annotated[str, Query(min_length=1, max_length=1000)],
    note: Annotated[str | None, Query(max_length=2000)] = None,
) -> InboxFileOut:
    """SPEC-023 AC-2: a file dropped at the engagement level, waiting to be matched."""
    await check_inbox(ctx, engagement_id)
    content = await _file(request)
    return _inbox_out(
        await add_to_inbox(ctx, engagement_id, file_name=filename, content=content, note=note)
    )


@router.get("/inbox", action="evidence.upload", response_model=list[InboxFileOut])
async def inbox_route(engagement_id: UUID, ctx: Ctx) -> list[InboxFileOut]:
    """SPEC-023 AC-2, AC-3: waiting files with their suggestions."""
    return [_inbox_out(e) for e in await inbox(ctx, engagement_id)]


@router.post(
    "/inbox/{file_id}/assign",
    action="evidence.upload",
    response_model=AssignedOut,
    status_code=201,
    errors=(409,),
)
async def assign_inbox_file_route(
    engagement_id: UUID, file_id: UUID, body: InboxAssignIn, ctx: Ctx
) -> AssignedOut:
    """SPEC-023 AC-4: the file becomes evidence on the chosen item."""
    version_id = await assign_inbox_file(
        ctx,
        engagement_id,
        file_id,
        request_item_id=body.request_item_id,
        followed_suggestion=body.followed_suggestion,
        suggestion_source=body.suggestion_source,
        suggestion_rank=body.suggestion_rank,
    )
    return AssignedOut(evidence_version_id=version_id)


@router.post(
    "/inbox/{file_id}/discard",
    action="evidence.upload",
    response_model=DiscardedOut,
    errors=(409,),
)
async def discard_route(engagement_id: UUID, file_id: UUID, ctx: Ctx) -> DiscardedOut:
    """SPEC-023 AC-5: take it out of the inbox; nothing becomes evidence."""
    await discard(ctx, engagement_id, file_id)
    return DiscardedOut(id=file_id)


# --- Acceptance files and signed letters (SPEC-025 AC-4, AC-6; TASK-044 D2) -------------------


class SetupFileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    stored: Annotated[bool, classified("internal")]


@router.post(
    "/acceptance/file",
    action="acceptance.record",
    response_model=SetupFileOut,
    status_code=201,
    errors=(409,),
)
async def acceptance_file_route(
    engagement_id: UUID,
    request: Request,
    ctx: Ctx,
    filename: Annotated[str, Query(min_length=1, max_length=1000)],
) -> SetupFileOut:
    """The acceptance or continuance documentation, attached to the latest record."""
    await upload_setup_file(
        ctx, engagement_id, "acceptance", file_name=filename, content=await _file(request)
    )
    return SetupFileOut(stored=True)


@router.post(
    "/letter/file",
    action="letter.record",
    response_model=SetupFileOut,
    status_code=201,
    errors=(409,),
)
async def letter_file_route(
    engagement_id: UUID,
    request: Request,
    ctx: Ctx,
    filename: Annotated[str, Query(min_length=1, max_length=1000)],
) -> SetupFileOut:
    """The signed engagement letter."""
    await upload_setup_file(
        ctx, engagement_id, "letter", file_name=filename, content=await _file(request)
    )
    return SetupFileOut(stored=True)


@router.get("/{which}/file", action="setup.read", response_model=bytes, errors=(409,))
async def setup_file_route(
    engagement_id: UUID, which: Literal["acceptance", "letter"], ctx: Ctx
) -> Response:
    """The file as an attachment, never inline; audited and verified."""
    content, media_type, name = await download_setup_file(ctx, engagement_id, which)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


# --- TASK-102: decisions waiting on the caller, across their engagements -------------------------

firm_router = AbacusRouter(prefix="/v1/firm", tags=["evidence"])


class EngagementCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    count: Annotated[int, classified("internal")]


@firm_router.get("/waiting/review", action=OWN, response_model=list[EngagementCountOut])
async def review_waiting_route(
    ctx: Annotated[AuthContext, Depends(current_member)],
) -> list[EngagementCountOut]:
    """Evidence waiting for the caller's decision, per engagement."""
    return [EngagementCountOut(engagement_id=e, count=n) for e, n in await review_waiting(ctx)]
