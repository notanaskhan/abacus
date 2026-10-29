"""The team, acceptance and independence contract, v1: ENG-05, CLI-07 and CLI-08 (P-07-T29 stub;
ADR-139, ADR-164, P-36). Contract: `docs/contracts/acceptance-independence.md`; spec: SPEC-332;
DEC-326. The conflict and screening half is `organisations.conflicts_contract`.

- **Acceptance (CLI-07)** and **independence (CLI-08)** routes are live (P-07-T35 acceptance,
  P-07-T41 independence); their flag retired with P-07-T59 (DEC-905).
- **Team and roles (ENG-05)** routes, and the confirmation requests, are live since P-07-T30
  (`engagements.team`).

Every decision and confirmation here is a person's: `acceptance.decide`, `independence.confirm`,
`independence.conclude`, `team.approve` and `eqr.approve_eligibility` deny the agent and the
system at the matrix (INV-1, I-AGENT-NEVER), and the decision rows they write carry an
`actor_kind = 'human'` CHECK. No client role holds any action here. A walled engagement answers
404 on every route (INV-3). Free text (rationale, notes, safeguards, evaluations) is sealed per
tenant at rest and read back only on these routes.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import (
    AcceptanceRecordStatus,
    IndependenceConclusionStatus,
    NasEvaluationStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.modules.engagements import acceptance as acceptance_model
from abacus.modules.engagements import independence as independence_model
from abacus.modules.engagements import team as team_model
from abacus.modules.engagements.service import get_ref
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]

# P-07 §4.2 M5 (P-07-T35).
AcceptanceKind = Literal["new_client", "new_engagement_existing_client", "continuance"]
AnswerState = Literal["pending", "complete", "flag", "manual_check_open", "manual_check_done"]
RiskRating = Literal["low", "moderate", "high"]
FlagSeverity = Literal["low", "medium", "high"]
DecisionOption = Literal["accept", "accept_with_conditions", "decline"]
SourceKind = Literal["evidence_version", "request_item"]  # a flag's sources open SHL-08
# P-07 §4.2 M7 (P-07-T41).
ConfirmationAnswer = Literal["requested", "confirmed", "declined"]
BreachEventKind = Literal["evaluated", "tcwg_communicated", "remediated"]
# P-07 §4.2 M4 (P-07-T30): ENG-05.
EqrCheckCode = Literal["not_on_team", "cooling_off", "competence", "independence", "capacity"]
EqrCheckResult = Literal["pass", "fail", "pending", "not_assessed"]
EqrEligibility = Literal["eligible", "not_eligible"]
TeamRole = Literal["engagement_partner", "manager", "senior", "staff", "reviewer", "specialist"]

Code = Annotated[str, Field(pattern=r"^[a-z0-9_]{1,64}$")]  # a section, service or statement code
ShortText = Annotated[SingleLineText, Field(min_length=1, max_length=200)]
LongText = Annotated[MultiLineText, Field(min_length=1, max_length=8000)]
AnswerValue = str | int | bool | None


# --- Errors (`error-codes.yaml`; ENG-05's are in `team_errors.py`) -------------------------------


class NotSelf(DomainConflict):
    """Only the person themself confirms or declines their own independence."""

    code = "not_self"


# --- Shared parts -------------------------------------------------------------------------------


class SourceRefIn(BaseModel):
    """A flag's source: a file version or a request item, never a model output (INV-2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[SourceKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class SourceRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[SourceKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]


# --- Acceptance (CLI-07; P-07-T35) --------------------------------------------------------------


class ManualCheckOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_code: Annotated[str, classified("internal")]
    requested_of: Annotated[UUID, classified("internal")]
    requested_by: Annotated[UUID, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]
    completed_by: Annotated[UUID | None, classified("internal")] = None
    completed_at: Annotated[datetime | None, classified("internal")] = None
    note: Annotated[str | None, classified("confidential")] = None


class AcceptanceSectionOut(BaseModel):
    """A questionnaire section from the firm's pinned template version (never a constant)."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    title: Annotated[str, classified("internal")]  # firm content, from the template version
    answer_state: Annotated[AnswerState, classified("internal")]
    answers: Annotated[dict[str, AnswerValue], classified("confidential")] = {}
    manual_check: Annotated[ManualCheckOut | None, classified("internal")] = None
    version: Annotated[int, classified("internal")]


class AcceptanceFlagOut(BaseModel):
    """Insert-only; authored by a person (`authored_kind = 'human'` CHECK)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    severity: Annotated[FlagSeverity, classified("internal")]
    title: Annotated[str, classified("confidential")]
    body: Annotated[str, classified("confidential")]
    sources: Annotated[list[SourceRefOut], classified("internal")] = []
    authored_by: Annotated[UUID, classified("internal")]
    authored_at: Annotated[datetime, classified("internal")]


class AcceptanceConditionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    text: Annotated[str, classified("confidential")]
    assignee_user_id: Annotated[UUID, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None
    completed_by: Annotated[UUID | None, classified("internal")] = None
    completed_at: Annotated[datetime | None, classified("internal")] = None


class AcceptanceDecisionOut(BaseModel):
    """The one insert-only decision row (`record_id` UNIQUE, `actor_kind = 'human'` CHECK)."""

    model_config = ConfigDict(frozen=True)

    option: Annotated[DecisionOption, classified("internal")]
    rationale: Annotated[str, classified("confidential")]
    decided_by: Annotated[UUID, classified("internal")]
    decided_at: Annotated[datetime, classified("internal")]


class RiskPartnerReviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    partner_id: Annotated[UUID, classified("internal")]
    requested_by: Annotated[UUID, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]
    completed_at: Annotated[datetime | None, classified("internal")] = None


class PriorAcceptanceOut(BaseModel):
    """A continuance's prior year through the `prior_engagement_id` chain, read-only (AC-5)."""

    model_config = ConfigDict(frozen=True)

    record_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    option: Annotated[DecisionOption | None, classified("internal")] = None
    decided_at: Annotated[datetime | None, classified("internal")] = None
    conditions: Annotated[list[AcceptanceConditionOut], classified("confidential")] = []
    independence: Annotated[IndependenceConclusionStatus | None, classified("internal")] = None


class AcceptanceRecordOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    kind: Annotated[AcceptanceKind, classified("internal")]
    status: Annotated[AcceptanceRecordStatus, classified("internal")]  # C2 `acceptance_record`
    template_version_id: Annotated[UUID, classified("internal")]
    template_name: Annotated[str, classified("internal")]
    prepared_by: Annotated[UUID, classified("internal")]
    risk_rating: Annotated[RiskRating | None, classified("internal")] = None
    sent_to_partner_at: Annotated[datetime | None, classified("internal")] = None
    sent_to_partner_by: Annotated[UUID | None, classified("internal")] = None
    sections: Annotated[list[AcceptanceSectionOut], classified("confidential")] = []
    flags: Annotated[list[AcceptanceFlagOut], classified("confidential")] = []
    decision: Annotated[AcceptanceDecisionOut | None, classified("confidential")] = None
    conditions: Annotated[list[AcceptanceConditionOut], classified("confidential")] = []
    risk_partner_review: Annotated[RiskPartnerReviewOut | None, classified("internal")] = None
    prior: Annotated[PriorAcceptanceOut | None, classified("confidential")] = None
    version: Annotated[int, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")] = []


class AcceptanceAnswersIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=0), classified("internal")]
    answers: Annotated[dict[Code, AnswerValue], Field(max_length=200), classified("confidential")]
    complete: Annotated[bool, classified("internal")] = False
    risk_rating: Annotated[RiskRating | None, classified("internal")] = None


class AcceptanceFlagIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    severity: Annotated[FlagSeverity, classified("internal")]
    title: Annotated[ShortText, classified("confidential")]
    body: Annotated[LongText, classified("confidential")]
    sources: Annotated[list[SourceRefIn], Field(max_length=20), classified("internal")] = []


class ManualCheckRequestIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_of: Annotated[UUID, classified("internal")]


class ManualCheckCompleteIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    note: Annotated[LongText | None, classified("confidential")] = None


class SendToPartnerIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=0), classified("internal")]


class RiskPartnerReviewCompleteIn(BaseModel):
    """The named risk partner completes the review they were asked for (AC-4; TASK-1258)."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ConditionCompleteIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    note: Annotated[LongText | None, classified("confidential")] = None


class RiskPartnerReviewIn(BaseModel):
    """The EP picks another partner (never the EP) for a High-risk record (AC-4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    partner_id: Annotated[UUID, classified("internal")]


class ConditionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    text: Annotated[ShortText, classified("confidential")]
    assignee_user_id: Annotated[UUID, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None


class AcceptanceDecisionIn(BaseModel):
    """AC-6, AC-7: the EP's decision with fresh MFA; 422 `rationale_required` without a
    rationale, or with Accept with conditions and no condition."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    option: Annotated[DecisionOption, classified("internal")]
    rationale: Annotated[MultiLineText, Field(max_length=8000), classified("confidential")]
    conditions: Annotated[list[ConditionIn], Field(max_length=20), classified("confidential")] = []
    seen_version: Annotated[int, Field(ge=0), classified("internal")]


# --- Independence (CLI-08; P-07-T41) ------------------------------------------------------------


class MemberConfirmationOut(BaseModel):
    """A member's own confirmation for this engagement; a decline's note is the EP's to read."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    role: Annotated[str, classified("internal")]
    confirmation: Annotated[ConfirmationAnswer, classified("internal")]
    answered_at: Annotated[datetime | None, classified("internal")] = None
    statement_version: Annotated[str | None, classified("internal")] = None
    decline_note: Annotated[str | None, classified("confidential")] = None
    reminder_count: Annotated[int, classified("internal")] = 0
    # P-07-T41 (DEC-428): the member's annual confirmation read from G-01, for a reader who holds
    # `independence.annual_read`; null for everyone else.
    annual_confirmed: Annotated[bool | None, classified("internal")] = None


class IndependenceConclusionOut(BaseModel):
    """Insert-only (`actor_kind = 'human'` CHECK); a later one names what it supersedes."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    option: Annotated[IndependenceConclusionStatus, classified("internal")]
    safeguards: Annotated[str | None, classified("confidential")] = None
    concluded_by: Annotated[UUID, classified("internal")]
    concluded_at: Annotated[datetime, classified("internal")]
    supersedes_id: Annotated[UUID | None, classified("internal")] = None


class IndependenceBlockerOut(BaseModel):
    """A banner reason: a registry code and the object it names, never prose."""

    model_config = ConfigDict(frozen=True)

    reason_code: Annotated[
        Literal[
            "member_not_confirmed",
            "member_declined",
            "conflict_not_cleared",
            "ske_designee_missing",
            "nas_not_evaluated",
            "breach_open",
        ],
        classified("internal"),
    ]
    ref_type: Annotated[str, classified("internal")]
    ref_id: Annotated[UUID, classified("internal")]


class IndependenceSummaryOut(BaseModel):
    """CLI-08 a: "{confirmed} of {total} confirmed", the banner reasons and the conclusion."""

    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    attest_client: Annotated[bool, classified("internal")]
    confirmed: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    members: Annotated[list[MemberConfirmationOut], classified("confidential")] = []
    blockers: Annotated[list[IndependenceBlockerOut], classified("internal")] = []
    conclusion: Annotated[IndependenceConclusionOut | None, classified("confidential")] = None
    ske_designee_contact_id: Annotated[UUID | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class RotationRowOut(BaseModel):
    """CLI-08 d: years served from the `prior_engagement_id` chain and role history (AC-27)."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    role: Annotated[str, classified("internal")]
    years_served: Annotated[int, classified("internal")]
    familiarity_flag: Annotated[bool, classified("internal")]


class RotationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    review_years: Annotated[int, classified("internal")]  # firm setting `rotation_review_years`
    rows: Annotated[list[RotationRowOut], classified("confidential")] = []


class ConfirmIn(BaseModel):
    """AC-17: the three statements ticked, for oneself only (409 `not_self` otherwise)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    statement_version: Annotated[Code, classified("internal")]
    statement_codes: Annotated[
        list[Code], Field(min_length=1, max_length=10), classified("internal")
    ]
    interests_note: Annotated[LongText | None, classified("confidential")] = None


class DeclineIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    note: Annotated[LongText, classified("confidential")]


class ConfirmationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]
    confirmation: Annotated[ConfirmationAnswer, classified("internal")]
    answered_at: Annotated[datetime | None, classified("internal")] = None


class RemindersIn(BaseModel):
    """ENG-05 "Send confirmation request" and CLI-08 "Send reminder": sent by the person
    clicking, for members whose confirmation is still requested or declined."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    user_ids: Annotated[list[UUID], Field(min_length=1, max_length=50), classified("internal")]


class RemindersOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    reminded_user_ids: Annotated[list[UUID], classified("internal")]


class NasRowOut(BaseModel):
    """A nonattest service on an attest engagement (AC-21); insert-only events behind it."""

    model_config = ConfigDict(frozen=True)

    service_code: Annotated[str, classified("internal")]
    provided: Annotated[bool, classified("internal")]
    status: Annotated[NasEvaluationStatus, classified("internal")]  # C2 `nas_evaluation`
    evaluation: Annotated[str | None, classified("confidential")] = None
    safeguards: Annotated[str | None, classified("confidential")] = None
    ske_contact_id: Annotated[UUID | None, classified("internal")] = None
    evaluated_by: Annotated[UUID | None, classified("internal")] = None
    evaluated_at: Annotated[datetime | None, classified("internal")] = None


class NasOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    attest_client: Annotated[bool, classified("internal")]
    ske_designee_contact_id: Annotated[UUID | None, classified("internal")] = None
    rows: Annotated[list[NasRowOut], classified("confidential")] = []


class NasEvaluationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    provided: Annotated[bool, classified("internal")]
    status: Annotated[NasEvaluationStatus, classified("internal")]
    evaluation: Annotated[LongText | None, classified("confidential")] = None
    safeguards: Annotated[LongText | None, classified("confidential")] = None
    ske_contact_id: Annotated[UUID | None, classified("internal")] = None


class BreachIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    description: Annotated[LongText, classified("confidential")]
    user_id: Annotated[UUID | None, classified("internal")] = None


class BreachEventIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    kind: Annotated[BreachEventKind, classified("internal")]
    note: Annotated[LongText | None, classified("confidential")] = None


class BreachEventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[
        Literal["logged", "evaluated", "tcwg_communicated", "remediated"], classified("internal")
    ]
    note: Annotated[str | None, classified("confidential")] = None
    recorded_by: Annotated[UUID, classified("internal")]
    recorded_at: Annotated[datetime, classified("internal")]


class BreachOut(BaseModel):
    """CLI-08 g: the banner stays until evaluated, TCWG communicated and remediated (AC-28)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    description: Annotated[str, classified("confidential")]
    user_id: Annotated[UUID | None, classified("internal")] = None
    events: Annotated[list[BreachEventOut], classified("confidential")] = []
    resolved: Annotated[bool, classified("internal")]


class ConcludeIn(BaseModel):
    """AC-18: Independent, Independent with safeguards (safeguards required) or Not independent,
    by the EP with fresh MFA; 409 `independence_preconditions_unmet` (AC-19)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    option: Annotated[IndependenceConclusionStatus, classified("internal")]
    safeguards: Annotated[LongText | None, classified("confidential")] = None


# --- Team and roles (ENG-05; P-07-T30) ----------------------------------------------------------


class TeamApprovalOut(BaseModel):
    """ENG-05's footer: "Team approved by {EP} · {date} · changes since: + {person} (awaiting
    approval)". `changed` compares the current member set with the approved one."""

    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    # The current team's sha256, to send back with `POST …/team/approve` (stale: 409).
    member_set_hash: Annotated[str, classified("internal")]
    approved_by: Annotated[UUID | None, classified("internal")] = None
    approved_by_name: Annotated[str | None, classified("confidential")] = None
    approved_at: Annotated[datetime | None, classified("internal")] = None
    changed: Annotated[bool, classified("internal")]
    added_since: Annotated[list[UUID], classified("internal")] = []


class TeamApproveIn(BaseModel):
    """The `member_set_hash` of the roster the partner approves (security review): a team that
    changed since answers 409 `stale_version`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    member_set_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


class PortalVisibilityIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    shown_on_portal: Annotated[bool, classified("internal")]


class PortalVisibilityOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    shown_on_portal: Annotated[bool, classified("internal")]


class EqrCheckOut(BaseModel):
    """One eligibility check, a code and its result; `year` names the cooling-off year."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[EqrCheckCode, classified("internal")]
    result: Annotated[EqrCheckResult, classified("internal")]
    count: Annotated[int | None, classified("internal")] = None  # competence: engagements served
    year: Annotated[int | None, classified("internal")] = None  # cooling-off: the year as EP


class EqrCandidateOut(BaseModel):
    """ENG-05 c: a Replace EQR candidate with its eligibility ("Not eligible — cooling-off")."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    eligibility: Annotated[EqrEligibility, classified("internal")]
    checks: Annotated[list[EqrCheckOut], classified("internal")]
    current: Annotated[bool, classified("internal")] = False


class EqrIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]


class EqrOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]
    eligibility: Annotated[EqrEligibility, classified("internal")]
    checks: Annotated[list[EqrCheckOut], classified("internal")]


class EqrEligibilityApprovalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_user_id: Annotated[UUID, classified("internal")]


class EqrEligibilityApprovalOut(BaseModel):
    """The quality owner's insert-only approval (`actor_kind = 'human'` CHECK), never the EP's."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    candidate_user_id: Annotated[UUID, classified("internal")]
    result: Annotated[EqrEligibility, classified("internal")]
    checks: Annotated[list[EqrCheckOut], classified("internal")]
    approved_by: Annotated[UUID, classified("internal")]
    approved_at: Annotated[datetime, classified("internal")]


# --- Routes -------------------------------------------------------------------------------------


async def _allowed(ctx: AuthContext, action: str, engagement_id: UUID) -> None:
    """Security review (DEC-326; `audits_contract._allowed`'s order): authorise before the flag
    or the stub answers, so no principal learns a flag state it may not use. No route here
    serves a client principal, an agent or the system (every one is a firm person's); a walled
    or unknown engagement is 404 whatever the flag."""
    if ctx.client or ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())


async def _acceptance_gate(ctx: AuthContext, action: str, engagement_id: UUID) -> None:
    """CLI-07's routes are live (P-07-T35; their flag retired with P-07-T59, DEC-905) after the
    same check; the service then requires a live person and authorises again inside its unit of
    work."""
    await _allowed(ctx, action, engagement_id)


async def _review_gate(ctx: AuthContext, engagement_id: UUID) -> None:
    """The risk partner's completion (DEC-375, L1): refused to a client, an agent and the
    system, authorised on the engagement's client (the derived `firm_partner`; walls apply),
    (`engagements.acceptance_v2` retired with P-07-T59, DEC-905)."""
    action = "acceptance.complete_review"
    if ctx.client or ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, Resource.client(ctx.tenant_id, ref.client_id))


def _record_out(view: acceptance_model.RecordView) -> AcceptanceRecordOut:
    return AcceptanceRecordOut.model_validate(view, from_attributes=True)


async def _team_gate(ctx: AuthContext, action: str, engagement_id: UUID) -> None:
    """ENG-05's rows are live (P-07-T30) after the same check."""
    await _allowed(ctx, action, engagement_id)


acceptance_router = AbacusRouter(prefix="/v1/engagements", tags=["acceptance"])
independence_router = AbacusRouter(prefix="/v1/engagements", tags=["independence"])
team_roles_router = AbacusRouter(prefix="/v1/engagements", tags=["team"])
ACCEPTANCE = "/{engagement_id}/acceptance"
INDEPENDENCE = "/{engagement_id}/independence"
TEAM = "/{engagement_id}/team"
EQR = "/{engagement_id}/eqr"


@acceptance_router.get(ACCEPTANCE, action="acceptance.read", response_model=AcceptanceRecordOut)
async def get_acceptance_route(engagement_id: UUID, ctx: Ctx) -> AcceptanceRecordOut:
    """CLI-07: the record, answers, checks, flags, decision and conditions."""
    await _acceptance_gate(ctx, "acceptance.read", engagement_id)
    return _record_out(await acceptance_model.acceptance_record(ctx, engagement_id))


@acceptance_router.put(
    f"{ACCEPTANCE}/answers/{{section_code}}",
    action="acceptance.prepare",
    response_model=AcceptanceSectionOut,
    errors=(409,),
)
async def put_acceptance_answers_route(
    engagement_id: UUID, section_code: Code, body: AcceptanceAnswersIn, ctx: Ctx
) -> AcceptanceSectionOut:
    """`acceptance.answers_updated`; 409 `stale_version` (the section's version, 0 before its
    first answer), 409 `decision_locked`."""
    await _acceptance_gate(ctx, "acceptance.prepare", engagement_id)
    section = await acceptance_model.update_answers(
        ctx,
        engagement_id,
        section_code,
        seen_version=body.seen_version,
        values=body.answers,
        complete=body.complete,
        risk_rating=body.risk_rating,
    )
    return AcceptanceSectionOut.model_validate(section, from_attributes=True)


@acceptance_router.post(
    f"{ACCEPTANCE}/flags",
    action="acceptance.prepare",
    response_model=AcceptanceFlagOut,
    status_code=201,
    errors=(409,),
)
async def add_acceptance_flag_route(
    engagement_id: UUID, body: AcceptanceFlagIn, ctx: Ctx
) -> AcceptanceFlagOut:
    """AC-2: an insert-only flag authored by the caller; `acceptance.flag_added`."""
    await _acceptance_gate(ctx, "acceptance.prepare", engagement_id)
    flag = await acceptance_model.add_flag(
        ctx,
        engagement_id,
        severity=body.severity,
        title=body.title,
        body=body.body,
        sources=[acceptance_model.SourceRef(s.kind, s.id) for s in body.sources],
    )
    return AcceptanceFlagOut.model_validate(flag, from_attributes=True)


@acceptance_router.post(
    f"{ACCEPTANCE}/manual-checks/{{section_code}}/request",
    action="acceptance.prepare",
    response_model=ManualCheckOut,
    status_code=201,
    errors=(409,),
)
async def request_manual_check_route(
    engagement_id: UUID, section_code: Code, body: ManualCheckRequestIn, ctx: Ctx
) -> ManualCheckOut:
    """`acceptance.manual_check_requested`; 422 `invalid` when the person may not complete it
    here or the section already has an open check."""
    await _acceptance_gate(ctx, "acceptance.prepare", engagement_id)
    check = await acceptance_model.request_manual_check(
        ctx, engagement_id, section_code, body.requested_of
    )
    return ManualCheckOut.model_validate(check, from_attributes=True)


@acceptance_router.post(
    f"{ACCEPTANCE}/manual-checks/{{section_code}}/complete",
    action="acceptance.prepare",
    response_model=ManualCheckOut,
    errors=(409,),
)
async def complete_manual_check_route(
    engagement_id: UUID, section_code: Code, body: ManualCheckCompleteIn, ctx: Ctx
) -> ManualCheckOut:
    """By the person it was requested of (client service included); `…manual_check_completed`;
    403 for anyone else."""
    await _acceptance_gate(ctx, "acceptance.prepare", engagement_id)
    check = await acceptance_model.complete_manual_check(
        ctx, engagement_id, section_code, body.note
    )
    return ManualCheckOut.model_validate(check, from_attributes=True)


@acceptance_router.post(
    f"{ACCEPTANCE}/send-to-partner",
    action="acceptance.prepare",
    response_model=AcceptanceRecordOut,
    errors=(409,),
)
async def send_to_partner_route(
    engagement_id: UUID, body: SendToPartnerIn, ctx: Ctx
) -> AcceptanceRecordOut:
    """AC-1, AC-3: Draft → Awaiting partner; 409 `acceptance_not_ready` (open checks as facts),
    409 `illegal_transition` once sent."""
    await _acceptance_gate(ctx, "acceptance.prepare", engagement_id)
    return _record_out(
        await acceptance_model.send_to_partner(ctx, engagement_id, body.seen_version)
    )


@acceptance_router.post(
    f"{ACCEPTANCE}/conditions/{{condition_id}}/complete",
    action="acceptance.prepare",
    response_model=AcceptanceConditionOut,
    errors=(409,),
)
async def complete_condition_route(
    engagement_id: UUID, condition_id: UUID, body: ConditionCompleteIn, ctx: Ctx
) -> AcceptanceConditionOut:
    """AC-9: an insert-only completion event by a person; `acceptance.condition_completed`;
    422 `invalid` when already complete."""
    await _acceptance_gate(ctx, "acceptance.prepare", engagement_id)
    done = await acceptance_model.complete_condition(ctx, engagement_id, condition_id, body.note)
    return AcceptanceConditionOut.model_validate(done, from_attributes=True)


@acceptance_router.post(
    f"{ACCEPTANCE}/risk-partner-review",
    action="acceptance.request_review",
    response_model=RiskPartnerReviewOut,
    status_code=201,
    errors=(409,),
)
async def request_risk_partner_review_route(
    engagement_id: UUID, body: RiskPartnerReviewIn, ctx: Ctx
) -> RiskPartnerReviewOut:
    """AC-4: another partner, picked by the EP; `acceptance.review_requested`; 422 `invalid`
    for the EP themself, an engagement partner here, a non-partner or someone walled from the
    client."""
    await _acceptance_gate(ctx, "acceptance.request_review", engagement_id)
    review = await acceptance_model.request_risk_review(ctx, engagement_id, body.partner_id)
    return RiskPartnerReviewOut.model_validate(review, from_attributes=True)


@acceptance_router.post(
    f"{ACCEPTANCE}/risk-partner-review/complete",
    action="acceptance.complete_review",
    response_model=RiskPartnerReviewOut,
    errors=(409,),
)
async def complete_risk_partner_review_route(
    engagement_id: UUID, body: RiskPartnerReviewCompleteIn, ctx: Ctx
) -> RiskPartnerReviewOut:
    """AC-4 (TASK-1258): only the named risk partner, authorised on the client (the derived
    `firm_partner`; walls apply); `acceptance.review_completed`."""
    await _review_gate(ctx, engagement_id)
    review = await acceptance_model.complete_risk_review(ctx, engagement_id)
    return RiskPartnerReviewOut.model_validate(review, from_attributes=True)


@acceptance_router.post(
    f"{ACCEPTANCE}/decision",
    action="acceptance.decide",
    response_model=AcceptanceRecordOut,
    status_code=201,
    errors=(409,),
)
async def decide_acceptance_route(
    engagement_id: UUID, body: AcceptanceDecisionIn, ctx: Ctx
) -> AcceptanceRecordOut:
    """Human-only (INV-1), fresh MFA: one insert-only decision, `acceptance.decided`, Prospect →
    Accepted or Declined (AC-6 to AC-8); 409 `review_required`, `decision_locked`; 422
    `rationale_required`."""
    await _acceptance_gate(ctx, "acceptance.decide", engagement_id)
    record = await acceptance_model.decide_acceptance(
        ctx,
        engagement_id,
        option=body.option,
        rationale=body.rationale,
        conditions=[
            acceptance_model.NewCondition(c.text, c.assignee_user_id, c.due_on)
            for c in body.conditions
        ],
        seen_version=body.seen_version,
    )
    return _record_out(record)


@independence_router.get(
    INDEPENDENCE, action="independence.read", response_model=IndependenceSummaryOut
)
async def get_independence_route(engagement_id: UUID, ctx: Ctx) -> IndependenceSummaryOut:
    """CLI-08 a: the summary and the banner reasons."""
    await _acceptance_gate(ctx, "independence.read", engagement_id)
    view = await independence_model.independence_summary(ctx, engagement_id)
    return IndependenceSummaryOut.model_validate(view, from_attributes=True)


@independence_router.get(
    f"{INDEPENDENCE}/rotation",
    action="independence.read",
    response_model=RotationOut,
)
async def get_rotation_route(engagement_id: UUID, ctx: Ctx) -> RotationOut:
    """CLI-08 d (AC-27)."""
    await _acceptance_gate(ctx, "independence.read", engagement_id)
    view = await independence_model.rotation(ctx, engagement_id)
    return RotationOut.model_validate(view, from_attributes=True)


@independence_router.post(
    f"{INDEPENDENCE}/confirm",
    action="independence.confirm",
    response_model=ConfirmationOut,
    errors=(409,),
)
async def confirm_independence_route(
    engagement_id: UUID, body: ConfirmIn, ctx: Ctx
) -> ConfirmationOut:
    """Human-only, self only (AC-17): the three statements; `independence.confirmed`."""
    await _acceptance_gate(ctx, "independence.confirm", engagement_id)
    view = await independence_model.confirm_independence(
        ctx,
        engagement_id,
        statement_version=body.statement_version,
        statement_codes=body.statement_codes,
        interests_note=body.interests_note,
    )
    return ConfirmationOut.model_validate(view, from_attributes=True)


@independence_router.post(
    f"{INDEPENDENCE}/decline",
    action="independence.confirm",
    response_model=ConfirmationOut,
    errors=(409,),
)
async def decline_independence_route(
    engagement_id: UUID, body: DeclineIn, ctx: Ctx
) -> ConfirmationOut:
    """Self only; the note sealed, the member stays not cleared (DF-06); `independence.declined`
    (the EP's notification registers with P-07-T47)."""
    await _acceptance_gate(ctx, "independence.confirm", engagement_id)
    view = await independence_model.decline_independence(ctx, engagement_id, note=body.note)
    return ConfirmationOut.model_validate(view, from_attributes=True)


@independence_router.post(
    f"{INDEPENDENCE}/reminders",
    action="independence.remind",
    response_model=RemindersOut,
)
async def send_reminders_route(engagement_id: UUID, body: RemindersIn, ctx: Ctx) -> RemindersOut:
    """Sent by the person clicking (no schedule); `independence.reminded` per member and the
    `independence.requested` notification again. Live with ENG-05 (P-07-T30); 422 for a member
    whose confirmation is not requested or declined."""
    await _team_gate(ctx, "independence.remind", engagement_id)
    reminded = await team_model.remind_independence(ctx, engagement_id, body.user_ids)
    return RemindersOut(reminded_user_ids=reminded)


@independence_router.get(f"{INDEPENDENCE}/nas", action="independence.read", response_model=NasOut)
async def get_nas_route(engagement_id: UUID, ctx: Ctx) -> NasOut:
    """CLI-08 b; a non-attest client answers `attest_client: false` and no rows (AC-22)."""
    await _acceptance_gate(ctx, "independence.read", engagement_id)
    view = await independence_model.nas(ctx, engagement_id)
    return NasOut.model_validate(view, from_attributes=True)


@independence_router.put(
    f"{INDEPENDENCE}/nas/{{service_code}}",
    action="nas.evaluate",
    response_model=NasRowOut,
    errors=(409,),
)
async def put_nas_route(
    engagement_id: UUID, service_code: Code, body: NasEvaluationIn, ctx: Ctx
) -> NasRowOut:
    """AC-21, AC-22: an insert-only event; the evaluation decision is the EP's; refused without
    an SKE designee on an attest client; `nas.evaluated`."""
    await _acceptance_gate(ctx, "nas.evaluate", engagement_id)
    row = await independence_model.evaluate_nas(
        ctx,
        engagement_id,
        service_code,
        provided=body.provided,
        status=body.status.value,
        evaluation=body.evaluation,
        safeguards=body.safeguards,
        ske_contact_id=body.ske_contact_id,
    )
    return NasRowOut.model_validate(row, from_attributes=True)


@independence_router.post(
    f"{INDEPENDENCE}/breaches",
    action="independence.breach_manage",
    response_model=BreachOut,
    status_code=201,
)
async def log_breach_route(engagement_id: UUID, body: BreachIn, ctx: Ctx) -> BreachOut:
    """AC-28: `independence_breach.logged`."""
    await _acceptance_gate(ctx, "independence.breach_manage", engagement_id)
    view = await independence_model.log_breach(
        ctx, engagement_id, description=body.description, user_id=body.user_id
    )
    return BreachOut.model_validate(view, from_attributes=True)


@independence_router.post(
    f"{INDEPENDENCE}/breaches/{{breach_id}}/events",
    action="independence.breach_manage",
    response_model=BreachOut,
    status_code=201,
    errors=(409,),
)
async def add_breach_event_route(
    engagement_id: UUID, breach_id: UUID, body: BreachEventIn, ctx: Ctx
) -> BreachOut:
    """AC-28: insert-only, each kind once (409 `illegal_transition`);
    `independence_breach.updated`."""
    await _acceptance_gate(ctx, "independence.breach_manage", engagement_id)
    view = await independence_model.add_breach_event(
        ctx, engagement_id, breach_id, kind=body.kind, note=body.note
    )
    return BreachOut.model_validate(view, from_attributes=True)


@independence_router.post(
    f"{INDEPENDENCE}/conclude",
    action="independence.conclude",
    response_model=IndependenceConclusionOut,
    status_code=201,
    errors=(409,),
)
async def conclude_independence_route(
    engagement_id: UUID, body: ConcludeIn, ctx: Ctx
) -> IndependenceConclusionOut:
    """Human-only, fresh MFA (AC-18 to AC-20); 409 `independence_preconditions_unmet`."""
    await _acceptance_gate(ctx, "independence.conclude", engagement_id)
    view = await independence_model.conclude_independence(
        ctx, engagement_id, option=body.option.value, safeguards=body.safeguards
    )
    return IndependenceConclusionOut.model_validate(view, from_attributes=True)


def _approval_out(a: team_model.TeamApproval) -> TeamApprovalOut:
    return TeamApprovalOut(
        engagement_id=a.engagement_id,
        member_set_hash=a.member_set_hash,
        approved_by=a.approved_by,
        approved_by_name=a.approved_by_name,
        approved_at=a.approved_at,
        changed=a.changed,
        added_since=a.added_since,
    )


def _checks_out(checks: list[team_model.Check]) -> list[EqrCheckOut]:
    return [EqrCheckOut(code=c.code, result=c.result, count=c.count, year=c.year) for c in checks]


@team_roles_router.get(
    f"{TEAM}/approval", action="engagement.read_metadata", response_model=TeamApprovalOut
)
async def get_team_approval_route(engagement_id: UUID, ctx: Ctx) -> TeamApprovalOut:
    """ENG-05's footer facts."""
    await _team_gate(ctx, "engagement.read_metadata", engagement_id)
    return _approval_out(await team_model.team_approval(ctx, engagement_id))


@team_roles_router.post(
    f"{TEAM}/approve",
    action="team.approve",
    response_model=TeamApprovalOut,
    status_code=201,
    errors=(409,),
)
async def approve_team_route(
    engagement_id: UUID, body: TeamApproveIn, ctx: Ctx
) -> TeamApprovalOut:
    """Human-only, fresh MFA: the EP approves the team they saw (an insert-only row);
    `team.approved`; 409 `stale_version` when it changed since."""
    await _team_gate(ctx, "team.approve", engagement_id)
    return _approval_out(await team_model.approve_team(ctx, engagement_id, body.member_set_hash))


@team_roles_router.put(
    f"{TEAM}/{{user_id}}/portal-visibility",
    action="engagement.update",
    response_model=PortalVisibilityOut,
)
async def put_portal_visibility_route(
    engagement_id: UUID, user_id: UUID, body: PortalVisibilityIn, ctx: Ctx
) -> PortalVisibilityOut:
    """POR-02's team card; `team.portal_visibility_changed`."""
    await _team_gate(ctx, "engagement.update", engagement_id)
    await team_model.set_portal_visibility(ctx, engagement_id, user_id, body.shown_on_portal)
    return PortalVisibilityOut(user_id=user_id, shown_on_portal=body.shown_on_portal)


@team_roles_router.get(
    f"{EQR}/candidates", action="eqr.assign", response_model=list[EqrCandidateOut]
)
async def eqr_candidates_route(engagement_id: UUID, ctx: Ctx) -> list[EqrCandidateOut]:
    """ENG-05 c: eligibility per candidate (not on the team, cooling-off, competence,
    independence, capacity)."""
    await _team_gate(ctx, "eqr.assign", engagement_id)
    return [
        EqrCandidateOut(
            user_id=c.user_id,
            display_name=c.display_name,
            eligibility=c.eligibility,
            checks=_checks_out(c.checks),
            current=c.current,
        )
        for c in await team_model.eqr_candidates(ctx, engagement_id)
    ]


@team_roles_router.post(EQR, action="eqr.assign", response_model=EqrOut, errors=(409,))
async def assign_eqr_route(engagement_id: UUID, body: EqrIn, ctx: Ctx) -> EqrOut:
    """Replaces the EQR; 409 `eqr_on_team`, 409 `eqr_not_eligible`; `eqr.assigned`."""
    await _team_gate(ctx, "eqr.assign", engagement_id)
    checks = await team_model.assign_eqr(ctx, engagement_id, body.user_id)
    return EqrOut(
        engagement_id=engagement_id,
        user_id=body.user_id,
        eligibility="eligible",
        checks=_checks_out(checks),
    )


@team_roles_router.post(
    f"{EQR}/eligibility/approve",
    action="eqr.approve_eligibility",
    response_model=EqrEligibilityApprovalOut,
    status_code=201,
    errors=(409,),
)
async def approve_eqr_eligibility_route(
    engagement_id: UUID, body: EqrEligibilityApprovalIn, ctx: Ctx
) -> EqrEligibilityApprovalOut:
    """Human-only, the quality owner: 409 `eqr_approver_is_ep`; `eqr.eligibility_approved`."""
    await _team_gate(ctx, "eqr.approve_eligibility", engagement_id)
    a = await team_model.approve_eqr_eligibility(ctx, engagement_id, body.candidate_user_id)
    return EqrEligibilityApprovalOut(
        id=a.id,
        engagement_id=a.engagement_id,
        candidate_user_id=a.candidate_user_id,
        result=a.result,
        checks=_checks_out(a.checks),
        approved_by=a.approved_by,
        approved_at=a.approved_at,
    )
