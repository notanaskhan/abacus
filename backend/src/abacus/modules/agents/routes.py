"""Agent routes (SPEC-000 §8; TASK-012 Q1): screening results for the evidence board. Read-only:
agents propose, and nothing here lets anyone act on a proposal (ADR-005)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import MultiLineText
from abacus.modules.agents.adopt import adopt
from abacus.modules.agents.assess_start import assessments_of, request_assessments
from abacus.modules.agents.draft_start import (
    Approval,
    decide_drafts,
    decide_template_drafts,
    pending_drafts,
    publish_template_drafts,
    request_drafts,
    request_template_drafts,
    template_drafts_for,
)
from abacus.modules.agents.engagement_agent import (
    AgentView,
    activity_feed,
    agent_view,
    draft_follow_ups,
    drafts,
    preview_follow_up,
    set_paused,
    settle_draft,
)
from abacus.modules.agents.graph import EngagementGraph, engagement_graph
from abacus.modules.agents.knowledge import (
    DocumentView,
    MediaType,
    NewDocument,
    SourceKind,
    add_document,
    document,
    documents,
    search_knowledge,
    withdraw_document,
)
from abacus.modules.agents.match_start import matches_of, request_match
from abacus.modules.agents.review_start import request_review, review_flag_counts, review_of
from abacus.modules.agents.screenings import request_screening
from abacus.modules.agents.service import ScreeningResultView, screening_results_for
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

# One router for the engagement's agent surfaces (screening results; SPEC-027's agent and feed).
router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["agents"])
Action = Literal["ready_for_review", "needs_revision"]
Reason = Literal["cell_not_found", "quote_mismatch", "value_mismatch"]


class CitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    cell: Annotated[str, classified("internal")]
    quote: Annotated[str | None, classified("confidential")]
    value: Annotated[str | None, classified("confidential")]
    verified: Annotated[bool, classified("internal")]
    reason: Annotated[Reason | None, classified("internal")]


class ScreeningResultOut(BaseModel):
    """Model text (`rationale`, `quote`, `unverified`) is untrusted: render as plain text."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    action: Annotated[Action, classified("internal")]
    confidence: Annotated[Decimal, classified("internal")]
    rationale: Annotated[str, classified("confidential")]
    citations: Annotated[list[CitationOut], classified("confidential")]
    unverified: Annotated[list[str], classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]


def _out(result: ScreeningResultView) -> ScreeningResultOut:
    return ScreeningResultOut.model_validate(result, from_attributes=True)


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.get("/screening-results", action="evidence.read", response_model=list[ScreeningResultOut])
async def list_screening_results_route(engagement_id: UUID, ctx: Ctx) -> list[ScreeningResultOut]:
    return [_out(r) for r in await screening_results_for(ctx, engagement_id)]


class ScreenRequestIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_version_id: Annotated[UUID, classified("internal")]


class ScreenRequestedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]


@router.post(
    "/screening-results/request",
    action="screening.request",
    response_model=ScreenRequestedOut,
    status_code=202,
)
async def request_screening_route(
    engagement_id: UUID, body: ScreenRequestIn, ctx: Ctx
) -> ScreenRequestedOut:
    """SPEC-024 (TASK-042 D1): "Screen now"; the result appears with the others when ready."""
    await request_screening(ctx, engagement_id, body.evidence_version_id)
    return ScreenRequestedOut(evidence_version_id=body.evidence_version_id)


# --- The engagement agent (SPEC-027; TASK-050) ---------------------------------------------------


class AgentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: Annotated[bool, classified("internal")]
    paused_at: Annotated[datetime | None, classified("internal")]
    paused_by: Annotated[str | None, classified("confidential")]
    reason: Annotated[str | None, classified("confidential")]
    firm_paused_at: Annotated[datetime | None, classified("internal")]


class PauseIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[str | None, Field(max_length=300), classified("confidential")] = None


class ActivityOut(BaseModel):
    """One automatic action: references only, never client content (AC-7)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    policy: Annotated[str, classified("internal")]
    policy_version: Annotated[int, classified("internal")]
    action: Annotated[str, classified("internal")]
    outcome: Annotated[Literal["done", "skipped", "failed"], classified("internal")]
    reason: Annotated[str | None, classified("internal")]
    record_type: Annotated[str | None, classified("internal")]
    record_id: Annotated[UUID | None, classified("internal")]
    item_count: Annotated[int | None, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


def _agent_out(view: AgentView) -> AgentOut:
    return AgentOut.model_validate(asdict(view))


# --- The upload reviewer (SPEC-030; TASK-059) ----------------------------------------------------


class ReviewQuoteOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: Annotated[int | None, classified("internal")]
    sheet: Annotated[str | None, classified("confidential")]
    cell: Annotated[str | None, classified("internal")]
    quote: Annotated[str, classified("confidential")]


class ReviewFlagOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: Annotated[Literal["irrelevant", "draft", "altered"], classified("internal")]
    confidence: Annotated[Decimal, classified("internal")]
    rationale: Annotated[str, classified("confidential")]
    quotes: Annotated[list[ReviewQuoteOut], classified("confidential")]


class ReviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[str, classified("internal")]
    reason: Annotated[str | None, classified("internal")]
    flags: Annotated[list[ReviewFlagOut], classified("confidential")]


class ReviewFlagCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    flags: Annotated[int, classified("internal")]


@router.get(
    "/evidence-versions/{version_id}/review",
    action="upload_review.read",
    response_model=ReviewOut,
)
async def upload_review_route(engagement_id: UUID, version_id: UUID, ctx: Ctx) -> ReviewOut:
    """SPEC-030 AC-6: the latest AI review of an upload, firm roles only, verified quotes only."""
    view = await review_of(ctx, engagement_id, version_id)
    return ReviewOut.model_validate(asdict(view))


class ReviewRequestedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]


@router.post(
    "/evidence-versions/{version_id}/review",
    action="upload_review.request",
    status_code=202,
    response_model=ReviewRequestedOut,
    errors=(409,),
)
async def request_review_route(
    engagement_id: UUID, version_id: UUID, ctx: Ctx
) -> ReviewRequestedOut:
    """SPEC-030 §6.4: "Review now" (at Advise, or after a document kind change)."""
    await request_review(ctx, engagement_id, version_id)
    return ReviewRequestedOut(evidence_version_id=version_id)


@router.get("/review-flags", action="upload_review.read", response_model=list[ReviewFlagCountOut])
async def review_flags_route(engagement_id: UUID, ctx: Ctx) -> list[ReviewFlagCountOut]:
    """For the Board's "AI flags" marker: shown flags per version's latest review."""
    counts = await review_flag_counts(ctx, engagement_id)
    return [ReviewFlagCountOut(evidence_version_id=v, flags=n) for v, n in counts.items()]


# --- The matcher (SPEC-033; TASK-066) ------------------------------------------------------------


class MatchProposalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    confidence: Annotated[Decimal, classified("internal")]
    rationale: Annotated[str, classified("confidential")]
    quotes: Annotated[list[ReviewQuoteOut], classified("confidential")]


class FileMatchOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    inbox_file_id: Annotated[UUID, classified("internal")]
    status: Annotated[str, classified("internal")]
    reason: Annotated[str | None, classified("internal")]
    none_fit: Annotated[bool, classified("internal")]
    none_fit_rationale: Annotated[str | None, classified("confidential")]
    proposals: Annotated[list[MatchProposalOut], classified("confidential")]


@router.get("/inbox-matches", action="inbox_match.read", response_model=list[FileMatchOut])
async def inbox_matches_route(engagement_id: UUID, ctx: Ctx) -> list[FileMatchOut]:
    """SPEC-033 AC-3, AC-5: each inbox file's latest matcher run, firm roles only, verified quotes
    only."""
    return [FileMatchOut.model_validate(asdict(v)) for v in await matches_of(ctx, engagement_id)]


class MatchRequestedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    inbox_file_id: Annotated[UUID, classified("internal")]


@router.post(
    "/inbox/{file_id}/match",
    action="inbox_match.request",
    status_code=202,
    response_model=MatchRequestedOut,
    errors=(409,),
)
async def request_match_route(engagement_id: UUID, file_id: UUID, ctx: Ctx) -> MatchRequestedOut:
    """SPEC-033 §4.5: "Suggest with AI" (at Advise, or again)."""
    await request_match(ctx, engagement_id, file_id)
    return MatchRequestedOut(inbox_file_id=file_id)


# --- Drafted guidance (SPEC-035; TASK-073) -------------------------------------------------------


class DraftGuidanceIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item_ids: Annotated[list[UUID] | None, Field(max_length=500), classified("internal")] = None


class DraftStartedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[UUID], classified("internal")]
    skipped: Annotated[list[UUID], classified("internal")]


@router.post(
    "/request-items/draft-guidance",
    action="guidance_draft.request",
    status_code=202,
    response_model=DraftStartedOut,
    errors=(409,),
)
async def draft_guidance_route(
    engagement_id: UUID, body: DraftGuidanceIn, ctx: Ctx
) -> DraftStartedOut:
    """SPEC-035 AC-1: "Draft guidance" for the named items, or every item without guidance."""
    started = await request_drafts(ctx, engagement_id, body.item_ids)
    return DraftStartedOut(items=list(started.items), skipped=list(started.skipped))


class GuidanceDraftOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    why: Annotated[str, classified("confidential")]
    good_looks_like: Annotated[str, classified("confidential")]
    effort: Annotated[Literal["small", "medium", "large"] | None, classified("internal")] = None
    effort_reason: Annotated[str | None, classified("internal")] = None
    blocks_fieldwork: Annotated[bool | None, classified("internal")] = None
    blocks_reason: Annotated[str | None, classified("internal")] = None
    created_at: Annotated[datetime, classified("internal")]


@router.get(
    "/guidance-drafts", action="guidance_draft.read", response_model=list[GuidanceDraftOut]
)
async def guidance_drafts_route(engagement_id: UUID, ctx: Ctx) -> list[GuidanceDraftOut]:
    """SPEC-035 §4.5: drafts awaiting a decision (firm roles; never one that failed)."""
    return [
        GuidanceDraftOut.model_validate(asdict(d))
        for d in await pending_drafts(ctx, engagement_id)
    ]


class ApprovalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    draft_id: Annotated[UUID, classified("internal")]
    why: Annotated[MultiLineText | None, Field(max_length=300), classified("confidential")] = None
    good_looks_like: Annotated[
        MultiLineText | None, Field(max_length=600), classified("confidential")
    ] = None
    effort: Annotated[Literal["small", "medium", "large"] | None, classified("internal")] = None
    blocks_fieldwork: Annotated[bool | None, classified("internal")] = None


class DecideIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    approvals: Annotated[
        list[ApprovalIn], Field(min_length=1, max_length=500), classified("internal")
    ]
    confirmed_read: Annotated[bool, classified("internal")] = False


class DecidedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decided: Annotated[int, classified("internal")]


@router.post(
    "/guidance-drafts/approve",
    action="guidance_draft.decide",
    response_model=DecidedOut,
    status_code=201,
    errors=(409,),
)
async def approve_drafts_route(engagement_id: UUID, body: DecideIn, ctx: Ctx) -> DecidedOut:
    """SPEC-035 AC-4: approve drafts (edits checked again); several at once need
    `confirmed_read` (Q5)."""
    approvals = [
        Approval(a.draft_id, a.why, a.good_looks_like, a.effort, a.blocks_fieldwork)
        for a in body.approvals
    ]
    count = await decide_drafts(ctx, engagement_id, approvals, confirmed_read=body.confirmed_read)
    return DecidedOut(decided=count)


@router.post(
    "/guidance-drafts/discard",
    action="guidance_draft.decide",
    response_model=DecidedOut,
    status_code=201,
    errors=(409,),
)
async def discard_drafts_route(engagement_id: UUID, body: DecideIn, ctx: Ctx) -> DecidedOut:
    approvals = [Approval(a.draft_id) for a in body.approvals]
    return DecidedOut(decided=await decide_drafts(ctx, engagement_id, approvals, discard=True))


# --- The entry assessor (SPEC-037 Q4; TASK-085) -------------------------------------------------


class AssessIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item_ids: Annotated[list[UUID] | None, Field(max_length=200), classified("internal")] = None


class AssessStartedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[UUID], classified("internal")]


@router.post(
    "/procedures/{procedure_id}/assess",
    action="entry_assessment.request",
    status_code=202,
    response_model=AssessStartedOut,
    errors=(409,),
)
async def assess_route(
    engagement_id: UUID, procedure_id: UUID, body: AssessIn, ctx: Ctx
) -> AssessStartedOut:
    """SPEC-037 Q4: "Assess with AI" for entries with documents and no assessment yet."""
    started = await request_assessments(ctx, engagement_id, procedure_id, body.item_ids)
    return AssessStartedOut(items=list(started))


class EntryCitationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    document: Annotated[str, classified("internal")]
    claim: Annotated[str, classified("internal")]
    page: Annotated[int | None, classified("internal")] = None
    sheet: Annotated[str | None, classified("confidential")] = None
    cell: Annotated[str | None, classified("internal")] = None
    quote: Annotated[str, classified("restricted")]
    verified: Annotated[bool, classified("internal")]
    reason: Annotated[str | None, classified("internal")] = None
    amount_matches: Annotated[bool | None, classified("internal")] = None


class AssessmentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    selected_item_id: Annotated[UUID, classified("internal")]
    verdict: Annotated[Literal["explained", "not_explained", "unclear"], classified("internal")]
    rationale: Annotated[str, classified("confidential")]
    citations: Annotated[list[EntryCitationOut], classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]


@router.get(
    "/procedures/{procedure_id}/assessments",
    action="procedure.read",
    response_model=list[AssessmentOut],
)
async def assessments_route(
    engagement_id: UUID, procedure_id: UUID, ctx: Ctx
) -> list[AssessmentOut]:
    """Each entry's newest assessment, AI-tagged on screen; firm roles only."""
    return [
        AssessmentOut.model_validate({**asdict(a), "citations": list(a.citations)})
        for a in await assessments_of(ctx, engagement_id, procedure_id)
    ]


@router.get("/agent", action="activity.read", response_model=AgentOut)
async def agent_route(engagement_id: UUID, ctx: Ctx) -> AgentOut:
    """SPEC-027: whether the agent is on, and the engagement's and the firm's pause."""
    return _agent_out(await agent_view(ctx, engagement_id))


@router.post("/agent/pause", action="agent.pause", response_model=AgentOut)
async def pause_agent_route(engagement_id: UUID, body: PauseIn, ctx: Ctx) -> AgentOut:
    """SPEC-027 AC-6: nothing automatic happens on this engagement until resumed."""
    return _agent_out(await set_paused(ctx, engagement_id, paused=True, reason=body.reason))


@router.post("/agent/resume", action="agent.pause", response_model=AgentOut)
async def resume_agent_route(engagement_id: UUID, ctx: Ctx) -> AgentOut:
    """SPEC-027 AC-6: the agent looks once: what arrived while paused is screened."""
    return _agent_out(await set_paused(ctx, engagement_id, paused=False))


@router.get("/activity", action="activity.read", response_model=list[ActivityOut])
async def activity_route(
    engagement_id: UUID,
    ctx: Ctx,
    before: datetime | None = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 50,
) -> list[ActivityOut]:
    """SPEC-027 AC-7: the activity feed, newest first."""
    rows = await activity_feed(ctx, engagement_id, before, limit)
    return [ActivityOut.model_validate(r, from_attributes=True) for r in rows]


class DraftItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]


class DraftOut(BaseModel):
    """SPEC-027 AC-4: a reminder the agent drafted at Advise, for a person to send or dismiss."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    recipient_user_id: Annotated[UUID, classified("internal")]
    recipient_name: Annotated[str, classified("confidential")]
    items: Annotated[list[DraftItemOut], classified("confidential")]
    created_at: Annotated[datetime, classified("internal")]


class SendDraftIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    note: Annotated[str | None, Field(max_length=500), classified("confidential")] = None


class SettledOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]


@router.get("/follow-ups", action="follow_up.draft", response_model=list[DraftOut])
async def drafts_route(engagement_id: UUID, ctx: Ctx) -> list[DraftOut]:
    return [
        DraftOut(
            id=d.id,
            recipient_user_id=d.recipient_user_id,
            recipient_name=d.recipient_name,
            items=[DraftItemOut(request_item_id=i, description=t) for i, t in d.items],
            created_at=d.created_at,
        )
        for d in await drafts(ctx, engagement_id)
    ]


@router.post(
    "/follow-ups/{follow_up_id}/send",
    action="follow_up.send",
    response_model=SettledOut,
    errors=(409,),
)
async def send_draft_route(
    engagement_id: UUID, follow_up_id: UUID, body: SendDraftIn, ctx: Ctx
) -> SettledOut:
    await settle_draft(ctx, engagement_id, follow_up_id, send=True, note=body.note)
    return SettledOut(id=follow_up_id)


@router.post(
    "/follow-ups/{follow_up_id}/dismiss",
    action="follow_up.send",
    response_model=SettledOut,
    errors=(409,),
)
async def dismiss_draft_route(engagement_id: UUID, follow_up_id: UUID, ctx: Ctx) -> SettledOut:
    await settle_draft(ctx, engagement_id, follow_up_id, send=False)
    return SettledOut(id=follow_up_id)


class DraftedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    drafted: Annotated[int, classified("internal")]


@router.post(
    "/follow-ups/draft",
    action="follow_up.draft",
    response_model=DraftedOut,
    status_code=201,
    errors=(409,),
)
async def draft_follow_ups_route(engagement_id: UUID, ctx: Ctx) -> DraftedOut:
    """TASK-104: follow-ups for everything overdue now, one per contact, for a person to send."""
    return DraftedOut(drafted=await draft_follow_ups(ctx, engagement_id))


class FollowUpPreviewIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    note: Annotated[str | None, Field(default=None, max_length=500), classified("confidential")]


class FollowUpPreviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject: Annotated[str, classified("confidential")]
    body: Annotated[str, classified("confidential")]


@router.post(
    "/follow-ups/{follow_up_id}/preview",
    action="follow_up.draft",
    response_model=FollowUpPreviewOut,
)
async def preview_follow_up_route(
    engagement_id: UUID, follow_up_id: UUID, body: FollowUpPreviewIn, ctx: Ctx
) -> FollowUpPreviewOut:
    """TASK-104: the email exactly as it will be sent (fixed template; no model text)."""
    subject, text = await preview_follow_up(ctx, engagement_id, follow_up_id, body.note)
    return FollowUpPreviewOut(subject=subject, body=text)


class AdoptIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item_ids: Annotated[
        list[UUID] | None, Field(default=None, max_length=500), classified("internal")
    ]


class AdoptedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    adopted: Annotated[int, classified("internal")]


@router.post(
    "/procedures/{procedure_id}/adopt",
    action="entry_assessment.adopt",
    response_model=AdoptedOut,
    status_code=201,
    errors=(409,),
)
async def adopt_route(
    engagement_id: UUID, procedure_id: UUID, body: AdoptIn, ctx: Ctx
) -> AdoptedOut:
    """SPEC-044 AC-4: a person adopts the agent's proposals as results."""
    return AdoptedOut(adopted=await adopt(ctx, engagement_id, procedure_id, body.item_ids))


# --- The engagement graph (SPEC-008 §8; TASK-023 D1) --------------------------------------------

graph_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/graph", tags=["agents"])


class GraphItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]
    status: Annotated[str, classified("internal")]
    retrievability_tier: Annotated[str | None, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    screening_action: Annotated[str | None, classified("internal")]


class GraphAccountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("confidential")]
    name: Annotated[str, classified("confidential")]
    balance: Annotated[Decimal, classified("confidential")]


class GraphAreaOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str | None, classified("internal")]
    name: Annotated[str, classified("confidential")]
    items: Annotated[list[GraphItemOut], classified("confidential")]
    accounts: Annotated[list[GraphAccountOut], classified("confidential")]


class CoverageGapsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    areas_without_requests: Annotated[list[str], classified("confidential")]
    areas_with_accounts_without_requests: Annotated[list[str], classified("confidential")]
    unmapped_accounts: Annotated[list[GraphAccountOut], classified("confidential")]
    items_without_evidence: Annotated[list[UUID], classified("internal")]


class GraphTeamMemberOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    role: Annotated[str, classified("internal")]


class GraphEngagementOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    client_name: Annotated[str, classified("confidential")]
    client_entity_name: Annotated[str, classified("confidential")]
    fiscal_period_start: Annotated[date, classified("confidential")]
    fiscal_period_end: Annotated[date, classified("confidential")]
    status: Annotated[str, classified("internal")]


class GraphMethodologyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    template_id: Annotated[UUID, classified("internal")]
    template_name: Annotated[str, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]


class EngagementGraphOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement: Annotated[GraphEngagementOut, classified("confidential")]
    team: Annotated[list[GraphTeamMemberOut], classified("confidential")]
    methodology: Annotated[GraphMethodologyOut | None, classified("internal")]
    snapshot_id: Annotated[UUID | None, classified("internal")]
    areas: Annotated[list[GraphAreaOut], classified("confidential")]
    unmapped_accounts: Annotated[list[GraphAccountOut], classified("confidential")]
    gaps: Annotated[CoverageGapsOut, classified("confidential")]


def _graph_out(graph: EngagementGraph) -> EngagementGraphOut:
    view = graph.metadata.engagement
    m = graph.methodology
    return EngagementGraphOut(
        engagement=GraphEngagementOut(
            id=view.id,
            name=view.name,
            client_name=view.client_name,
            client_entity_name=view.client_entity_name,
            fiscal_period_start=view.fiscal_period_start,
            fiscal_period_end=view.fiscal_period_end,
            status=view.status,
        ),
        team=[
            GraphTeamMemberOut(user_id=t.user_id, display_name=t.display_name, role=t.role)
            for t in graph.metadata.team
        ],
        methodology=GraphMethodologyOut(
            template_id=m.template_id,
            template_name=m.template_name,
            version_id=m.version_id,
            version=m.version,
        )
        if m is not None
        else None,
        snapshot_id=graph.snapshot_id,
        areas=[GraphAreaOut.model_validate(asdict(a)) for a in graph.areas],
        unmapped_accounts=[
            GraphAccountOut.model_validate(asdict(a)) for a in graph.unmapped_accounts
        ],
        gaps=CoverageGapsOut.model_validate(asdict(graph.gaps)),
    )


@graph_router.get("", action="engagement.read", response_model=EngagementGraphOut)
async def engagement_graph_route(engagement_id: UUID, ctx: Ctx) -> EngagementGraphOut:
    return _graph_out(await engagement_graph(ctx, engagement_id))


# --- Knowledge (SPEC-009 §8) -------------------------------------------------------------------

knowledge_router = AbacusRouter(prefix="/v1/knowledge", tags=["knowledge"])


class KnowledgeDocumentIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200), classified("internal")]
    source_kind: Annotated[SourceKind, classified("internal")]
    media_type: Annotated[MediaType, classified("internal")]
    text: Annotated[str, Field(min_length=1), classified("internal")]


class KnowledgeDocumentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("internal")]
    source_kind: Annotated[str, classified("internal")]
    media_type: Annotated[str, classified("internal")]
    status: Annotated[
        Literal["pending", "ready", "failed", "withdrawn", "stale"], classified("internal")
    ]
    failure_code: Annotated[str | None, classified("internal")]
    chunk_count: Annotated[int, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class KnowledgeSearchIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query: Annotated[str, Field(min_length=1, max_length=1000), classified("internal")]
    k: Annotated[int, Field(ge=1, le=20), classified("internal")] = 8


class KnowledgeHitOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("internal")]
    heading_path: Annotated[str, classified("internal")]
    position: Annotated[int, classified("internal")]
    text: Annotated[str, classified("internal")]
    score: Annotated[float, classified("internal")]


def _document_out(view: DocumentView) -> KnowledgeDocumentOut:
    return KnowledgeDocumentOut.model_validate(asdict(view))


@knowledge_router.post(
    "/documents",
    action="knowledge.manage",
    response_model=KnowledgeDocumentOut,
    status_code=201,
    errors=(409,),
)
async def add_document_route(body: KnowledgeDocumentIn, ctx: Ctx) -> KnowledgeDocumentOut:
    document_id = await add_document(
        ctx, NewDocument(body.title, body.source_kind, body.media_type, body.text)
    )
    return _document_out(await document(ctx, document_id))


@knowledge_router.get(
    "/documents", action="knowledge.read", response_model=list[KnowledgeDocumentOut]
)
async def list_documents_route(ctx: Ctx) -> list[KnowledgeDocumentOut]:
    return [_document_out(v) for v in await documents(ctx)]


@knowledge_router.get(
    "/documents/{document_id}", action="knowledge.read", response_model=KnowledgeDocumentOut
)
async def get_document_route(document_id: UUID, ctx: Ctx) -> KnowledgeDocumentOut:
    return _document_out(await document(ctx, document_id))


@knowledge_router.post(
    "/documents/{document_id}/withdraw",
    action="knowledge.manage",
    response_model=KnowledgeDocumentOut,
    errors=(409,),
)
async def withdraw_document_route(document_id: UUID, ctx: Ctx) -> KnowledgeDocumentOut:
    await withdraw_document(ctx, document_id)
    return _document_out(await document(ctx, document_id))


@knowledge_router.post("/search", action="knowledge.read", response_model=list[KnowledgeHitOut])
async def search_route(body: KnowledgeSearchIn, ctx: Ctx) -> list[KnowledgeHitOut]:
    hits = await search_knowledge(ctx, body.query, body.k)
    return [KnowledgeHitOut.model_validate(asdict(h)) for h in hits]


# --- Drafted guidance on templates (SPEC-035 Q3; TASK-074) -------------------------------------

template_drafts_router = AbacusRouter(
    prefix="/v1/methodology/versions/{version_id}", tags=["methodology"]
)


class DraftTemplateGuidanceIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    positions: Annotated[
        list[Annotated[int, Field(ge=0)]] | None, Field(max_length=500), classified("internal")
    ] = None


class TemplateDraftStartedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    positions: Annotated[list[int], classified("internal")]


@template_drafts_router.post(
    "/draft-guidance",
    action="template_guidance.request",
    status_code=202,
    response_model=TemplateDraftStartedOut,
    errors=(409,),
)
async def draft_template_guidance_route(
    version_id: UUID, body: DraftTemplateGuidanceIn, ctx: Ctx
) -> TemplateDraftStartedOut:
    """SPEC-035 Q3: "Draft guidance" for the named template items, or every item without."""
    started = await request_template_drafts(ctx, version_id, body.positions)
    return TemplateDraftStartedOut(positions=list(started.positions))


class TemplateDraftOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    position: Annotated[int, classified("internal")]
    why: Annotated[str, classified("internal")]
    good_looks_like: Annotated[str, classified("internal")]
    effort: Annotated[Literal["small", "medium", "large"] | None, classified("internal")] = None
    effort_reason: Annotated[str | None, classified("internal")] = None
    blocks_fieldwork: Annotated[bool | None, classified("internal")] = None
    blocks_reason: Annotated[str | None, classified("internal")] = None
    created_at: Annotated[datetime, classified("internal")]
    status: Annotated[Literal["pending", "approved"], classified("internal")]
    approved_by: Annotated[UUID | None, classified("internal")] = None


@template_drafts_router.get(
    "/guidance-drafts", action="template_guidance.read", response_model=list[TemplateDraftOut]
)
async def template_drafts_route(version_id: UUID, ctx: Ctx) -> list[TemplateDraftOut]:
    """SPEC-035 Q3: the version's drafts awaiting a decision or approved (to publish)."""
    return [
        TemplateDraftOut.model_validate(asdict(d))
        for d in await template_drafts_for(ctx, version_id)
    ]


@template_drafts_router.post(
    "/guidance-drafts/approve",
    action="template_guidance.decide",
    response_model=DecidedOut,
    status_code=201,
    errors=(409,),
)
async def approve_template_drafts_route(version_id: UUID, body: DecideIn, ctx: Ctx) -> DecidedOut:
    """SPEC-035 AC-4 on a template: approve drafts (edits checked again); several at once need
    `confirmed_read` (Q5). Nothing reaches engagements until a version is published."""
    approvals = [
        Approval(a.draft_id, a.why, a.good_looks_like, a.effort, a.blocks_fieldwork)
        for a in body.approvals
    ]
    count = await decide_template_drafts(
        ctx, version_id, approvals, confirmed_read=body.confirmed_read
    )
    return DecidedOut(decided=count)


@template_drafts_router.post(
    "/guidance-drafts/discard",
    action="template_guidance.decide",
    response_model=DecidedOut,
    status_code=201,
    errors=(409,),
)
async def discard_template_drafts_route(version_id: UUID, body: DecideIn, ctx: Ctx) -> DecidedOut:
    approvals = [Approval(a.draft_id) for a in body.approvals]
    count = await decide_template_drafts(ctx, version_id, approvals, discard=True)
    return DecidedOut(decided=count)


class PublishedVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]


@template_drafts_router.post(
    "/publish-drafted",
    action="methodology.manage",
    response_model=PublishedVersionOut,
    status_code=201,
    errors=(409,),
)
async def publish_drafted_route(version_id: UUID, ctx: Ctx) -> PublishedVersionOut:
    """TASK-074 D2: the template's next version with the approved drafted guidance."""
    summary = await publish_template_drafts(ctx, version_id)
    return PublishedVersionOut(version_id=summary.version_id, version=summary.version)
