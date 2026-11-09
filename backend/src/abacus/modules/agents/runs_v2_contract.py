"""C6 v2, the runs half (P-10-T09 stub; P-10 §4.3; SPEC-647). Contract:
`docs/contracts/agent-runs.md` §9; screens SHL-13, WB-03, WB-09 (owned by P-09 and W-02).

One owner per route: P-09 owns the run view, items feed, run list and trace; P-10 owns the streams,
run commands and engagement run below. `GET /v1/agent-runs/{id}` gains these fields with P-10-T29.

Every route answers, in order: its flag (P-10-T24: `agent_runtime.v2`, `realtime.sse` for the run
stream, `engagement_run.enabled` for the engagement run; 404 off), then 501 until its task.

**Events carry identifiers, enums and verified items only** (AC-T2): an item that would hold a
Restricted-tagged field travels as `{id, ref_only: true}`. No model token is streamed (ADR-234).
A plan decision, an answer and a sign-off are a person's: `agent: deny` in the matrix, and the
database refuses anyone else (P-10-T03).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn, get_args
from uuid import UUID

from fastapi import Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AGENT_RUNTIME_V2, ENGAGEMENT_RUN_ENABLED, REALTIME_SSE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
Restricted = classified("restricted")

# The 14 canonical states (ADR-169, status registry `agent_run`). `approved`, `partially_approved`
# and `rejected` are derived from proposals; the rest are written.
RunStateV2 = Literal[
    "queued",
    "planning",
    "awaiting_plan_approval",
    "dispatched",
    "running",
    "needs_input",
    "blocked_on_decision",
    "waiting_on_inputs",
    "succeeded",
    "approved",
    "partially_approved",
    "rejected",
    "failed",
    "cancelled",
]
RunMode = Literal["plan", "run", "auto"]
TriggerKind = Literal[
    "manual",
    "schedule",
    "agent_trigger",
    "engagement_trigger",
    "retry",
    "test",
    "engagement_plan",
    "agent_column",
    "event_policy",
]
BlockedOnKind = Literal["decision", "question", "inputs", "approval", "capacity"]
StepKind = Literal[
    "tool",
    "compute",
    "model",
    "question",
    "decision",
    "approval",
    "narration",
    "wait",
    "child_run",
]
StepState = Literal[
    "queued",
    "dispatched",
    "running",
    "waiting_on_inputs",
    "blocked",
    "succeeded",
    "failed",
    "cancelled",
    "skipped",
]
PlanState = Literal["proposed", "approved", "edited", "cancelled", "standing"]
QuestionState = Literal["open", "answered", "skipped", "expired"]
RunEventType = Literal[
    "run.state",
    "step.state",
    "item.appended",
    "item.patched",
    "plan.proposed",
    "plan.decided",
    "question.opened",
    "question.answered",
    "proposal.created",
    "proposal.decided",
    "decision.requested",
    "decision.decided",
    "artifact.ready",
    "resync",
    "locked",
]
RunAction = Literal[
    "approve_plan",
    "edit_plan",
    "cancel_plan",
    "answer",
    "skip",
    "redirect",
    "retry",
    "stop",
    "sign_off",
]
FeedbackRating = Literal["up", "down"]
FeedbackReason = Literal[
    "wrong_figure", "wrong_source", "missed_something", "too_long", "not_useful", "other"
]
RUN_EVENT_TYPES: frozenset[str] = frozenset(get_args(RunEventType))


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class BlockedOnOut(BaseModel):
    model_config = _frozen()

    kind: Annotated[BlockedOnKind, Internal]
    id: Annotated[UUID | None, Internal] = None
    role: Annotated[str | None, Internal] = None
    user_id: Annotated[UUID | None, Internal] = None
    needs: Annotated[list[str], Internal] = Field(default_factory=list[str])


class RunCountersOut(BaseModel):
    """Code's counts, summed from steps (ADR-050). #4118: 2,625 records, 79 citations."""

    model_config = _frozen()

    records_read: Annotated[int, Internal] = 0
    citations_count: Annotated[int, Internal] = 0
    writes_done: Annotated[int, Internal] = 0
    writes_waiting: Annotated[int, Internal] = 0
    agent_ms: Annotated[int, Internal] = 0
    agent_minutes: Annotated[int, Internal] = 0


class RunV2Out(BaseModel):
    """The run v2 projection; USD and model family stay out of it (WB-09: "Accrued Agent
    runtime" plus region)."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    run_number: Annotated[int, Internal]
    title: Annotated[str, Confidential]
    state: Annotated[RunStateV2, Internal]
    state_reason: Annotated[str | None, Internal] = None
    blocked_on: Annotated[BlockedOnOut | None, Internal] = None
    mode: Annotated[RunMode, Internal]
    trigger_kind: Annotated[TriggerKind, Internal]
    session_id: Annotated[UUID | None, Internal] = None
    parent_run_id: Annotated[UUID | None, Internal] = None
    work_item_ref: Annotated[str | None, Internal] = None
    subject_ref: Annotated[str | None, Internal] = None
    plan_id: Annotated[UUID | None, Internal] = None
    auto_mode: Annotated[bool, Internal] = False
    initiator_name: Annotated[str, Confidential]
    region: Annotated[str | None, Internal] = None
    counters: Annotated[RunCountersOut, Internal]
    started_at: Annotated[datetime | None, Internal] = None
    finished_at: Annotated[datetime | None, Internal] = None
    signed_off_by: Annotated[str | None, Confidential] = None
    signed_off_at: Annotated[datetime | None, Internal] = None
    version: Annotated[int, Internal]
    allowed_actions: Annotated[list[RunAction], Internal]


class RunStepV2Out(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    seq: Annotated[int, Internal]
    plan_step_key: Annotated[str | None, Internal] = None
    level: Annotated[int, Internal] = 0
    kind: Annotated[StepKind, Internal]
    label: Annotated[str, Confidential]
    tool_name: Annotated[str | None, Internal] = None
    state: Annotated[StepState, Internal]
    needs: Annotated[list[str], Internal] = Field(default_factory=list[str])
    started_at: Annotated[datetime | None, Internal] = None
    ended_at: Annotated[datetime | None, Internal] = None
    active_ms: Annotated[int, Internal] = 0
    records_read: Annotated[int, Internal] = 0
    error_code: Annotated[str | None, Internal] = None


class RunPlanStepOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Confidential]
    level: Annotated[int, Internal] = 0
    writes: Annotated[bool, Internal] = False


class RunPlanOut(BaseModel):
    """One insert-only plan version; a decision is a new version, never an update."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    run_id: Annotated[UUID, Internal]
    version: Annotated[int, Internal]
    state: Annotated[PlanState, Internal]
    steps: Annotated[list[RunPlanStepOut], Confidential]
    sources: Annotated[list[str], Confidential] = Field(default_factory=list[str])
    decided_by: Annotated[str | None, Confidential] = None
    decided_at: Annotated[datetime | None, Internal] = None


class QuestionOptionOut(BaseModel):
    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Confidential]


class RunQuestionOut(BaseModel):
    """A run asks one question at a time; agent text renders through AgentText (ADR-230)."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    run_id: Annotated[UUID, Internal]
    step_id: Annotated[UUID | None, Internal] = None
    state: Annotated[QuestionState, Internal]
    prompt: Annotated[str, Confidential]
    options: Annotated[list[QuestionOptionOut], Confidential] = Field(
        default_factory=list[QuestionOptionOut]
    )
    allow_free_text: Annotated[bool, Internal] = False
    answered_by: Annotated[str | None, Confidential] = None
    answered_at: Annotated[datetime | None, Internal] = None


class RunEventOut(BaseModel):
    """One SSE event's data. `seq` is `run_seq` on a run stream and `session_seq` on a session
    stream, and `Last-Event-ID` is scoped to that stream. `item` is a verified AgentBlocks item or
    `{id, ref_only: true}`; over 64 KB it goes by reference (AC-T2)."""

    model_config = _frozen()

    seq: Annotated[int, Internal]
    type: Annotated[RunEventType, Internal]
    run_id: Annotated[UUID | None, Internal] = None
    session_id: Annotated[UUID | None, Internal] = None
    step_id: Annotated[UUID | None, Internal] = None
    state: Annotated[str | None, Internal] = None
    ref_id: Annotated[UUID | None, Internal] = None
    ref_only: Annotated[bool, Internal] = False
    item: Annotated[dict[str, object] | None, Confidential] = (
        None  # Any: a verified AgentBlocks item
    )
    at: Annotated[datetime, Internal]


class EngagementRunIn(BaseModel):
    model_config = _strict()

    work_item_ref: Annotated[str | None, Field(max_length=80), Internal] = None
    auto: Annotated[bool, Internal] = False


class RunAcceptedOut(BaseModel):
    """202: every workflow start returns where to read it."""

    model_config = _frozen()

    run_id: Annotated[UUID, Internal]
    status_url: Annotated[str, Internal]


class RunPlanEditIn(BaseModel):
    model_config = _strict()

    steps: Annotated[list[str], Field(min_length=1, max_length=200), Internal]
    expected_version: Annotated[int, Internal]


class PlanDecisionIn(BaseModel):
    model_config = _strict()

    expected_version: Annotated[int, Internal]


class QuestionAnswerIn(BaseModel):
    model_config = _strict()

    option_key: Annotated[str | None, Field(max_length=80), Internal] = None
    text: Annotated[str | None, Field(max_length=4000), Restricted] = None


class RunMessageIn(BaseModel):
    """A redirect. Hostile to the model: it enters the next turn as a person's message."""

    model_config = _strict()

    body: Annotated[str, Field(min_length=1, max_length=4000), Restricted]


class RunSignOffIn(BaseModel):
    model_config = _strict()

    acknowledged_issue_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])
    acknowledged_decision_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class AgentFeedbackIn(BaseModel):
    model_config = _strict()

    run_id: Annotated[UUID, Internal]
    step_id: Annotated[UUID | None, Internal] = None
    item_id: Annotated[str | None, Field(max_length=120), Internal] = None
    rating: Annotated[FeedbackRating, Internal]
    reason: Annotated[FeedbackReason | None, Internal] = None


class AgentFeedbackOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]


class AutoModeIn(BaseModel):
    model_config = _strict()

    enabled: Annotated[bool, Internal]
    confirmed: Annotated[Literal[True], Internal]


class AutoModeOut(BaseModel):
    model_config = _frozen()

    enabled: Annotated[bool, Internal]
    changed_by: Annotated[str, Confidential]
    changed_at: Annotated[datetime, Internal]


class CapabilityAvailabilityOut(BaseModel):
    model_config = _frozen()

    capability: Annotated[str, Internal]
    available: Annotated[bool, Internal]
    reason: Annotated[str | None, Internal] = None


class AgentCapabilitiesOut(BaseModel):
    """From flags, policy, boundary facts and consent; no model call."""

    model_config = _frozen()

    items: Annotated[list[CapabilityAvailabilityOut], Internal]


runs_v2_router = AbacusRouter(prefix="/v1/agent-runs", tags=["agent runs v2"])
engagement_runs_v2_router = AbacusRouter(prefix="/v1/engagements", tags=["agent runs v2"])
feedback_router = AbacusRouter(prefix="/v1/agent-feedback", tags=["agent runs v2"])
capabilities_router = AbacusRouter(prefix="/v1/agents/capabilities", tags=["agent runs v2"])


async def _flag_on(ctx: AuthContext, flag: Flag) -> None:
    """P-10-T24 (DEC-3110): a firm whose flag is off reaches nothing here (404); the matrix
    action is still declared and checked once the route has a resource (its build task)."""
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@runs_v2_router.get(
    "/{run_id}/events", action="agent_run.read", response_model=bytes, errors=(501,)
)
async def run_events_route(
    run_id: UUID,
    ctx: Ctx,
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID", ge=0)] = None,
) -> Response:
    """`text/event-stream` of `RunEventOut`: every later event in order, then tails; a gap older
    than the prune horizon answers `resync`; a new wall sends `locked` within 60 seconds (T26)."""
    await _flag_on(ctx, REALTIME_SSE)
    _not_yet()


@engagement_runs_v2_router.post(
    "/{engagement_id}/runs",
    action="agent_run.start",
    response_model=RunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def start_engagement_run_route(
    engagement_id: UUID, body: EngagementRunIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunAcceptedOut:
    """The engagement run: its plan computed by code from methodology (T39)."""
    await _flag_on(ctx, ENGAGEMENT_RUN_ENABLED)
    _not_yet()


@engagement_runs_v2_router.put(
    "/{engagement_id}/auto-mode",
    action="engagement_ai.configure",
    response_model=AutoModeOut,
    errors=(409, 501),
)
async def set_auto_mode_route(
    engagement_id: UUID, body: AutoModeIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AutoModeOut:
    """Standing plan approval per engagement type (ADR-186); refused for real firms in season 1."""
    await _flag_on(ctx, ENGAGEMENT_RUN_ENABLED)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/plan/approve",
    action="agent_run.approve_plan",
    response_model=RunPlanOut,
    errors=(409, 501),
)
async def approve_run_plan_route(
    run_id: UUID, body: PlanDecisionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunPlanOut:
    """Never optimistic. PLAN-001: plan decisions come only from `agents/commands.py` (T33)."""
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/plan/edit",
    action="agent_run.approve_plan",
    response_model=RunPlanOut,
    errors=(409, 501),
)
async def edit_run_plan_route(
    run_id: UUID, body: RunPlanEditIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunPlanOut:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/plan/cancel",
    action="agent_run.approve_plan",
    response_model=RunPlanOut,
    errors=(409, 501),
)
async def cancel_run_plan_route(
    run_id: UUID, body: PlanDecisionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunPlanOut:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/questions/{question_id}/answer",
    action="agent_run.answer",
    response_model=RunQuestionOut,
    errors=(409, 501),
)
async def answer_question_route(
    run_id: UUID,
    question_id: UUID,
    body: QuestionAnswerIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> RunQuestionOut:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/questions/{question_id}/skip",
    action="agent_run.answer",
    response_model=RunQuestionOut,
    errors=(409, 501),
)
async def skip_question_route(
    run_id: UUID, question_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunQuestionOut:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/messages",
    action="agent_run.control",
    response_model=RunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def redirect_run_route(
    run_id: UUID, body: RunMessageIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunAcceptedOut:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/steps/{step_id}/retry",
    action="agent_run.control",
    response_model=RunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def retry_step_route(
    run_id: UUID, step_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunAcceptedOut:
    """Re-dispatches only the failed step."""
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/stop",
    action="agent_run.control",
    response_model=RunAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def stop_run_route(
    run_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunAcceptedOut:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@runs_v2_router.post(
    "/{run_id}/sign-off",
    action="agent_run.sign_off",
    response_model=RunV2Out,
    errors=(409, 501),
)
async def sign_off_run_route(
    run_id: UUID, body: RunSignOffIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunV2Out:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@feedback_router.post(
    "",
    action="agent_feedback.create",
    response_model=AgentFeedbackOut,
    status_code=201,
    errors=(501,),
)
async def create_feedback_route(
    body: AgentFeedbackIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AgentFeedbackOut:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()


@capabilities_router.get(
    "", action="session.read", response_model=AgentCapabilitiesOut, errors=(501,)
)
async def list_capabilities_route(
    ctx: Ctx, engagement_id: Annotated[UUID | None, Query()] = None
) -> AgentCapabilitiesOut:
    await _flag_on(ctx, AGENT_RUNTIME_V2)
    _not_yet()
