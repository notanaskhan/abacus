"""Evidence routes (SPEC-000 §8; TASK-012 Q1), and review queues and decisions (SPEC-004).
Provenance only: content is read through `read_version`, never listed."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from abacus.kernel.classification import classified
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
