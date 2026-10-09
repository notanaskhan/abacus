"""Evidence routes (SPEC-000 §8; TASK-012 Q1), and review queues and decisions (SPEC-004).
Provenance only: content is read through `read_version`, never listed."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from abacus.kernel.classification import classified
from abacus.modules.evidence.board_summary import board_summary
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
    take,
)
from abacus.modules.evidence.uploads import (
    MAX_UPLOAD_BYTES,
    UploadTooLarge,
    UploadView,
    check_upload,
    upload,
    uploads_for,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["evidence"])
Method = Literal["retrieved", "uploaded"]


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
    item_status: Annotated[str, classified("internal")]


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
) -> UploadOut:
    """SPEC-020 AC-8, AC-9: a client's file for a request item, stored as new evidence."""
    await check_upload(ctx, engagement_id, item_id)
    content = await _file(request)
    return _upload_out(
        await upload(ctx, engagement_id, item_id, file_name=filename, content=content)
    )


@router.get(
    "/request-items/{item_id}/uploads", action="evidence.read", response_model=list[UploadOut]
)
async def list_uploads_route(engagement_id: UUID, item_id: UUID, ctx: Ctx) -> list[UploadOut]:
    """SPEC-020: the item's uploads, newest first."""
    return [_upload_out(v) for v in await uploads_for(ctx, engagement_id, item_id)]


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
