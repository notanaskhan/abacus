"""C3 v1, the review grammar: stub PR 2 (P-04-T08), the SHL-10 family. Proposals and suggestions
are the agents module's (ADR-161); the C3 contract is `docs/contracts/review-grammar.md` part 2.

Behind `review.grammar_api`: off, every route answers 404; on, 501 `not_implemented` until the
proposals and suggestions service lands (P-04-T24, Undo P-04-T29). The agent proposes; every
route here is a person's act or read (ADR-005, INV-1). Proposal and suggestion values may be
return information (§7216) or client figures, so they are Restricted and never in a list.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Path
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import REVIEW_GRAMMAR_API
from abacus.kernel._statuses import ProposalStatus, SuggestionStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.text import MultiLineText
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]

# A proposal's UUID, or a typed adapter's projection of a repo table (ADR-161 clause 3).
ProposalRef = Annotated[
    str,
    Path(
        pattern=(
            r"^((screening_result|upload_review|inbox_match):)?"
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
    ),
]
ProposalDecisionKind = Literal[
    "approved", "approved_with_edits", "rejected", "routed", "follow_up", "undone"
]
RejectReason = Literal["wrong_treatment", "unsupported_value", "needs_client_input", "other"]
PolicyResult = Literal["within_threshold", "review_required"]
SuggestionDecisionKind = Literal["adopted", "edited", "dismissed", "undone"]


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, REVIEW_GRAMMAR_API):
        raise NotFound("review.grammar_api")
    raise NotImplementedYet


# --- Proposals (SHL-10) ------------------------------------------------------------------------


class ProposalRowOut(BaseModel):
    """One change: Field · Before → After · Cause. A row without a verified citation is
    `unsupported` and blocks approval (422 `uncited_change`)."""

    model_config = ConfigDict(frozen=True)

    n: Annotated[int, classified("internal")]
    suggestion_id: Annotated[UUID | None, classified("internal")]
    field_key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    before: Annotated[str | None, classified("restricted")]
    after: Annotated[str | None, classified("restricted")]
    cause: Annotated[str | None, classified("confidential")]
    citation_ids: Annotated[list[UUID], classified("internal")]
    unsupported: Annotated[bool, classified("internal")]


class ProposalTotalOut(BaseModel):
    """A totals row computed by code ("Net change to Form 1040 total income · 0 · tie")."""

    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("confidential")]
    value: Annotated[str, classified("restricted")]
    ties: Annotated[bool, classified("internal")]


class ProposalEvidenceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]
    citation_count: Annotated[int, classified("internal")]


class ProposalPolicyOut(BaseModel):
    """`proposals.policy_eval` and the policy note. While P-08 is dormant the approver is always
    a named person, never "Policy" or the agent (INV-5)."""

    model_config = ConfigDict(frozen=True)

    policy_name: Annotated[str | None, classified("internal")]
    result: Annotated[PolicyResult | None, classified("internal")]
    routed_to_user_id: Annotated[UUID | None, classified("internal")]
    routed_to_name: Annotated[str | None, classified("internal")]
    # Agent text (the web app renders it only through AgentText); may hold return information.
    note: Annotated[str | None, classified("restricted")]


class ProposalSetOut(BaseModel):
    """SHL-10 g: the proposal's set. The link row opens SHL-19 and approves nothing."""

    model_config = ConfigDict(frozen=True)

    set_type: Annotated[str, classified("internal")]
    set_id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]
    results: Annotated[int, classified("internal")]
    exceptions: Annotated[int, classified("internal")]


class ProposalDecisionOut(BaseModel):
    """The latest insert-only, human-only `proposal_decisions` row. `undo_until` is the end of
    the 10-second window (ADR-161 clause 6); null once an effect has started or for none."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    decision: Annotated[ProposalDecisionKind, classified("internal")]
    reason_code: Annotated[RejectReason | None, classified("internal")]
    note: Annotated[str | None, classified("restricted")]
    decided_by_user_id: Annotated[UUID, classified("internal")]
    decided_by_name: Annotated[str, classified("internal")]
    decided_at: Annotated[datetime, classified("internal")]
    routed_to_user_id: Annotated[UUID | None, classified("internal")]
    undo_until: Annotated[datetime | None, classified("internal")]


class ProposalOut(BaseModel):
    """`GET /v1/proposals/{ref}`: the C3 projection SHL-10 renders, for a generic proposal or a
    typed adapter's (screener, upload reviewer, matcher)."""

    model_config = ConfigDict(frozen=True)

    ref: Annotated[str, classified("internal")]
    kind: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    context_label: Annotated[str, classified("confidential")]
    state: Annotated[ProposalStatus, classified("internal")]
    version: Annotated[int, classified("internal")]
    agent_run_id: Annotated[UUID | None, classified("internal")]
    proposed_at: Annotated[datetime, classified("internal")]
    change_count: Annotated[int, classified("internal")]
    # Agent text, rendered only through AgentText; may hold return information.
    reasoning: Annotated[str, classified("restricted")]
    rows: Annotated[list[ProposalRowOut], classified("restricted")]
    totals: Annotated[list[ProposalTotalOut], classified("restricted")]
    evidence: Annotated[list[ProposalEvidenceOut], classified("confidential")]
    policy: Annotated[ProposalPolicyOut | None, classified("restricted")]
    set: Annotated[ProposalSetOut | None, classified("confidential")]
    checkpoint_id: Annotated[UUID | None, classified("internal")]
    decision: Annotated[ProposalDecisionOut | None, classified("restricted")]
    allowed_actions: Annotated[list[str], classified("internal")]


class ProposalEditIn(BaseModel):
    """An edited After value with its citation note (SHL-10 "Approve with edits")."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n: Annotated[int, Field(ge=1), classified("internal")]
    after: Annotated[str, Field(max_length=200), classified("restricted")]
    citation_note: Annotated[
        MultiLineText, Field(min_length=1, max_length=2000), classified("restricted")
    ]


class ApproveProposalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    edits: Annotated[list[ProposalEditIn], Field(max_length=100), classified("restricted")] = []


class RejectProposalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    reason_code: Annotated[RejectReason, classified("internal")]
    note: Annotated[MultiLineText | None, Field(max_length=2000), classified("restricted")] = None


class RouteProposalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    approver_user_id: Annotated[UUID, classified("internal")]


class FollowUpIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[MultiLineText, Field(min_length=1, max_length=2000), classified("restricted")]


class UndoProposalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: Annotated[UUID, classified("internal")]


proposals_router = AbacusRouter(prefix="/v1/proposals", tags=["agents"])


@proposals_router.get("/{ref}", action="proposal.read", response_model=ProposalOut, errors=(501,))
async def proposal_route(ref: ProposalRef, ctx: Ctx) -> ProposalOut:
    """SHL-10 a to g: the proposal projection with the caller's allowed actions."""
    await _stub(ctx)


@proposals_router.post(
    "/{proposal_id}/approve",
    action="proposal.approve",
    response_model=ProposalOut,
    errors=(409, 501),
)
async def proposal_approve_route(
    proposal_id: UUID, body: ApproveProposalIn, ctx: Ctx
) -> ProposalOut:
    """Approve, or approve with edits (human only). Over the viewer's limit: 403 with the
    approver to route to."""
    await _stub(ctx)


@proposals_router.post(
    "/{proposal_id}/reject",
    action="proposal.reject",
    response_model=ProposalOut,
    errors=(409, 501),
)
async def proposal_reject_route(
    proposal_id: UUID, body: RejectProposalIn, ctx: Ctx
) -> ProposalOut:
    """SHL-10 f: reject with a reason (human only)."""
    await _stub(ctx)


@proposals_router.post(
    "/{proposal_id}/route",
    action="proposal.route",
    response_model=ProposalOut,
    errors=(409, 501),
)
async def proposal_route_to_route(
    proposal_id: UUID, body: RouteProposalIn, ctx: Ctx
) -> ProposalOut:
    """SHL-10 d: send it to a named approver ("Send to Priya Raman for approval")."""
    await _stub(ctx)


@proposals_router.post(
    "/{proposal_id}/follow-up",
    action="proposal.follow_up",
    response_model=ProposalOut,
    errors=(409, 501),
)
async def proposal_follow_up_route(proposal_id: UUID, body: FollowUpIn, ctx: Ctx) -> ProposalOut:
    """ "Ask follow-up": a follow-up recorded for the originating thread or run."""
    await _stub(ctx)


@proposals_router.post(
    "/{proposal_id}/undo",
    action="proposal.undo",
    response_model=ProposalOut,
    errors=(409, 501),
)
async def proposal_undo_route(proposal_id: UUID, body: UndoProposalIn, ctx: Ctx) -> ProposalOut:
    """Undo inside 10 seconds by the same person: 409 `undo_window_closed` or `effect_started`."""
    await _stub(ctx)


# --- Suggestions (C-31 Adopt) ------------------------------------------------------------------


class SuggestionOut(BaseModel):
    """One proposed value for one target, after a person's decision."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    field_key: Annotated[str, classified("internal")]
    proposed_value: Annotated[str, classified("restricted")]
    # Agent text, rendered only through AgentText.
    rationale: Annotated[str | None, classified("restricted")]
    citation_ids: Annotated[list[UUID], classified("internal")]
    status: Annotated[SuggestionStatus, classified("internal")]
    version: Annotated[int, classified("internal")]
    agent_run_id: Annotated[UUID | None, classified("internal")]
    decision: Annotated[SuggestionDecisionKind | None, classified("internal")]
    decided_by_user_id: Annotated[UUID | None, classified("internal")]
    decided_at: Annotated[datetime | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class AdoptSuggestionIn(BaseModel):
    """Adopt as proposed, or with an edited value and its citation note (decision `edited`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    edited_value: Annotated[str | None, Field(max_length=200), classified("restricted")] = None
    citation_note: Annotated[
        MultiLineText | None, Field(max_length=2000), classified("restricted")
    ] = None


class DismissSuggestionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    reason_code: Annotated[RejectReason | None, classified("internal")] = None


suggestions_router = AbacusRouter(prefix="/v1/suggestions", tags=["agents"])


@suggestions_router.post(
    "/{suggestion_id}/adopt",
    action="suggestion.resolve",
    response_model=SuggestionOut,
    errors=(409, 501),
)
async def suggestion_adopt_route(
    suggestion_id: UUID, body: AdoptSuggestionIn, ctx: Ctx
) -> SuggestionOut:
    """Adopt through the target's registered applier (human only)."""
    await _stub(ctx)


@suggestions_router.post(
    "/{suggestion_id}/dismiss",
    action="suggestion.resolve",
    response_model=SuggestionOut,
    errors=(409, 501),
)
async def suggestion_dismiss_route(
    suggestion_id: UUID, body: DismissSuggestionIn, ctx: Ctx
) -> SuggestionOut:
    """Dismiss (human only)."""
    await _stub(ctx)
