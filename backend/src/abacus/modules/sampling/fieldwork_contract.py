"""The fieldwork-testing contract stub, sampling half (A-08-T05; SPEC-657 F1, F3; DEC-5032).
Contract: `docs/contracts/fieldwork-testing.md`; screen AUD-12 (JE variant, expand testing).

JE tests over a GL population proved complete by code (A-03's `general_ledger` path), the firm's
risk criteria, code's scores with reason codes, the selection as a sample-set version, and sample
expansions a named approver alone decides. Every route has one matrix action and answers, in
order: a client principal 404; the action on the work item's engagement (walls 404,
independence 403); 404 with `audits.fieldwork_testing` off; then 501 until its task (T17; the
T12 routes are served, TASK-8086).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDITS_FIELDWORK_TESTING
from abacus.kernel._statuses import JeCriterionStatus, JeTestStatus, SampleExpansionStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Money = Annotated[Decimal, classified("confidential")]
Count = Annotated[int, Field(ge=0), classified("internal")]
CriterionKey = Literal[
    "weekend_holiday", "round_amount", "post_close", "manual_by_role", "keywords"
]
RoleClass = Literal["senior_management", "accounting_staff", "system", "unknown"]
ReasonCode = Literal[
    "weekend", "holiday", "round_amount", "post_close", "manual_by_role", "keyword"
]


class PopulationNotTied(DomainConflict):
    """Scoring refused until the population's completeness tie reads `tie` (AC-1.1)."""

    code = "population_not_tied"


class ExpansionRationaleRequired(DomainInvalid):
    code = "expansion_rationale_required"


class ApproverRequired(DomainInvalid):
    code = "approver_required"


class ContentChanged(DomainConflict):
    code = "content_changed"


# --- models --------------------------------------------------------------------------------------


class JeTestCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gl_snapshot_id: Annotated[UUID, classified("internal")]
    period_start: Annotated[date, classified("confidential")]
    period_end: Annotated[date, classified("confidential")]
    post_close_through: Annotated[date, classified("confidential")]


class TieOut(BaseModel):
    """'Opening TB + JE activity = closing TB for 214 of 214 accounts · $0.00'."""

    model_config = ConfigDict(frozen=True)

    accounts_tied: Count
    accounts_total: Count
    difference: Money
    result: Annotated[Literal["tie", "difference"], classified("internal")]


class CriterionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: Count
    key: Annotated[CriterionKey, classified("internal")]
    params: Annotated[dict[str, str], classified("internal")]  # the firm policy's, as text
    availability: Annotated[JeCriterionStatus, classified("internal")]
    missing_fields: Annotated[list[str], classified("internal")]  # P-58: what the export lacks
    hit_count: Count


class SelectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sample_set_id: Annotated[UUID, classified("internal")]
    version_no: Count
    by_score: Count
    unpredictable: Count
    score_min: Annotated[int, Field(ge=0, le=100), classified("internal")]
    seed: Annotated[str, classified("internal")]
    sampler_version: Annotated[str, classified("internal")]
    approved_by_initials: Annotated[str | None, classified("internal")]
    approved_on: Annotated[date | None, classified("internal")]
    pending_expansion: Annotated[ExpansionOut | None, classified("internal")] = None


class JeTestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    status: Annotated[JeTestStatus, classified("internal")]
    entries_count: Count
    lines_count: Count
    tie: Annotated[TieOut, classified("internal")]
    criteria: Annotated[list[CriterionOut], classified("internal")]
    unique_flagged: Count  # code's union, excluding unavailable criteria
    score_version: Count
    engine_version: Annotated[str | None, classified("internal")]
    selection: Annotated[SelectionOut | None, classified("internal")]
    allowed_actions: Annotated[
        list[Literal["je_test.configure", "je_test.score", "sample_set.create"]],
        classified("public"),
    ]


class CriteriaIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_version_id: Annotated[UUID, classified("internal")]
    overrides: Annotated[
        dict[CriterionKey, dict[str, str]], Field(max_length=5), classified("internal")
    ] = {}


class PostingUserRoleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    posting_user: Annotated[str, Field(min_length=1, max_length=120), classified("confidential")]
    role_class: Annotated[RoleClass, classified("internal")]
    citation_id: Annotated[UUID | None, classified("internal")] = None


class PostingUserRolesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roles: Annotated[list[PostingUserRoleIn], Field(max_length=500), classified("confidential")]


class ScoredEntryOut(BaseModel):
    """One scored entry: never a score without its reason codes (AVOID)."""

    model_config = ConfigDict(frozen=True)

    entry_ref: Annotated[str, classified("confidential")]  # JE-26-17994
    posted_on: Annotated[date, classified("confidential")]
    amount: Money
    account_last4: Annotated[str | None, Field(pattern=r"^\d{4}$"), classified("confidential")]
    description: Annotated[str, Field(max_length=500), classified("confidential")]
    score: Annotated[int, Field(ge=0, le=100), classified("internal")]
    reason_codes: Annotated[list[ReasonCode], classified("internal")]
    selected: Annotated[bool, classified("internal")]


class ScoredEntriesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ScoredEntryOut], classified("internal")]
    next_cursor: Annotated[str | None, classified("internal")]


class ScoreRunOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    je_test_id: Annotated[UUID, classified("internal")]
    score_version: Count
    workflow_id: Annotated[str, classified("internal")]


class SelectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score_min: Annotated[int | None, Field(ge=0, le=100), classified("internal")] = None
    top_n: Annotated[int | None, Field(ge=1, le=5000), classified("internal")] = None
    unpredictable_n: Annotated[int, Field(ge=0, le=500), classified("internal")] = 0


class ExpansionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    add_by_score: Annotated[int, Field(ge=0, le=500), classified("internal")] = 0
    add_unpredictable: Annotated[int, Field(ge=0, le=500), classified("internal")] = 0
    add_item_keys: Annotated[list[str], Field(max_length=500), classified("internal")] = []
    rationale: Annotated[str, Field(max_length=2000), classified("confidential")]
    rationale_suggestion_id: Annotated[UUID | None, classified("internal")] = None
    approver_user_id: Annotated[UUID | None, classified("internal")] = None


class ExpansionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    status: Annotated[SampleExpansionStatus, classified("internal")]
    base_count: Count
    add_count: Count
    resulting_count: Count  # code's: "Selected becomes 50"
    approver_name: Annotated[str, classified("confidential")]
    approver_initials: Annotated[str, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]


class ExpansionDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Annotated[Literal["approved", "rejected"], classified("internal")]
    seen_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


SelectionOut.model_rebuild()


# --- routes --------------------------------------------------------------------------------------

router = AbacusRouter(prefix="/v1", tags=["fieldwork-testing"])


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str) -> None:
    if ctx.client:
        raise NotFound("je_test")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, AUDITS_FIELDWORK_TESTING):
        raise NotFound(AUDITS_FIELDWORK_TESTING.name)


async def _gate_record(ctx: AuthContext) -> None:
    """A record's own path: client 404 and the flag; the service authorises on its work item."""
    if ctx.client:
        raise NotFound("je_test")
    if not await flag_enabled(ctx.tenant, AUDITS_FIELDWORK_TESTING):
        raise NotFound(AUDITS_FIELDWORK_TESTING.name)


@router.post(
    "/work-items/{work_item_id}/je-tests",
    action="je_test.create",
    response_model=JeTestOut,
    status_code=201,
    errors=(409, 501),
)
async def create_je_test(
    work_item_id: UUID, body: JeTestCreateIn, ctx: Ctx, _key: IdempotencyKey
) -> JeTestOut:
    """The population, its completeness tie and a draft test."""
    await _gate(ctx, work_item_id, "je_test.create")
    from abacus.modules.sampling.je_tests import create_je_test as create

    return await create(ctx, work_item_id, body)


@router.get(
    "/je-tests/{je_test_id}", action="je_test.read", response_model=JeTestOut, errors=(501,)
)
async def get_je_test(je_test_id: UUID, ctx: Ctx) -> JeTestOut:
    await _gate_record(ctx)
    from abacus.modules.sampling.je_tests import je_test_view

    return await je_test_view(ctx, je_test_id)


@router.put(
    "/je-tests/{je_test_id}/criteria",
    action="je_test.configure",
    response_model=JeTestOut,
    errors=(409, 501),
)
async def put_criteria(je_test_id: UUID, body: CriteriaIn, ctx: Ctx) -> JeTestOut:
    await _gate_record(ctx)
    from abacus.modules.sampling.je_tests import put_criteria as configure

    return await configure(ctx, je_test_id, body)


@router.put(
    "/je-tests/{je_test_id}/posting-user-roles",
    action="je_test.configure",
    response_model=JeTestOut,
    errors=(409, 501),
)
async def put_posting_user_roles(
    je_test_id: UUID, body: PostingUserRolesIn, ctx: Ctx
) -> JeTestOut:
    await _gate_record(ctx)
    from abacus.modules.sampling.je_tests import put_posting_user_roles as roles

    return await roles(ctx, je_test_id, body)


@router.post(
    "/je-tests/{je_test_id}/score",
    action="je_test.score",
    response_model=ScoreRunOut,
    status_code=202,
    errors=(409, 501),
)
async def score(je_test_id: UUID, ctx: Ctx, _key: IdempotencyKey) -> ScoreRunOut:
    """202: `JeScoringWorkflow` (409 `population_not_tied`)."""
    await _gate_record(ctx)
    from abacus.modules.sampling.je_tests import start_scoring

    return await start_scoring(ctx, je_test_id, _key)


@router.get(
    "/je-tests/{je_test_id}/entries",
    action="je_test.read",
    response_model=ScoredEntriesOut,
    errors=(501,),
)
async def list_entries(
    je_test_id: UUID,
    ctx: Ctx,
    criterion: CriterionKey | None = None,
    selected: bool | None = None,
    cursor: str | None = None,
) -> ScoredEntriesOut:
    await _gate_record(ctx)
    from abacus.modules.sampling.je_tests import list_entries as entries

    return await entries(ctx, je_test_id, criterion=criterion, selected=selected, cursor=cursor)


@router.post(
    "/je-tests/{je_test_id}/selection",
    action="sample_set.create",
    response_model=SelectionOut,
    status_code=201,
    errors=(409, 501),
)
async def draw_selection(
    je_test_id: UUID, body: SelectionIn, ctx: Ctx, _key: IdempotencyKey
) -> SelectionOut:
    """A sample-set version, method `je_score_selection`, through `SampleDrawWorkflow`."""
    await _gate_record(ctx)
    from abacus.modules.sampling.je_tests import draw_selection as select

    return await select(ctx, je_test_id, body, _key)


@router.post(
    "/sample-sets/{sample_set_id}/expansions",
    action="sample_expansion.request",
    response_model=ExpansionOut,
    status_code=201,
    errors=(409, 501),
)
async def request_expansion(
    sample_set_id: UUID, body: ExpansionIn, ctx: Ctx, _key: IdempotencyKey
) -> ExpansionOut:
    """422 `expansion_rationale_required`, `approver_required`; nothing changes until approved."""
    await _gate_record(ctx)
    from abacus.modules.sampling import expansions

    view = await expansions.request_expansion(
        ctx,
        sample_set_id,
        add_by_score=body.add_by_score,
        add_unpredictable=body.add_unpredictable,
        add_item_keys=body.add_item_keys,
        rationale=body.rationale,
        approver_user_id=body.approver_user_id,
        rationale_suggestion_id=body.rationale_suggestion_id,
    )
    return _expansion_out(view)


@router.post(
    "/sample-expansions/{expansion_id}/decide",
    action="sample_expansion.decide",
    response_model=ExpansionOut,
    errors=(409, 501),
)
async def decide_expansion(
    expansion_id: UUID, body: ExpansionDecisionIn, ctx: Ctx, _key: IdempotencyKey
) -> ExpansionOut:
    """The named approver only, never the requester; 409 `content_changed`."""
    await _gate_record(ctx)
    from abacus.modules.sampling import expansions

    return _expansion_out(
        await expansions.record_decision(ctx, expansion_id, body.decision, body.seen_hash)
    )


@router.post(
    "/sample-expansions/{expansion_id}/withdraw",
    action="sample_expansion.request",
    response_model=ExpansionOut,
    errors=(409, 501),
)
async def withdraw_expansion(expansion_id: UUID, ctx: Ctx, _key: IdempotencyKey) -> ExpansionOut:
    await _gate_record(ctx)
    from abacus.modules.sampling import expansions

    return _expansion_out(await expansions.withdraw(ctx, expansion_id))


def _expansion_out(view: object) -> ExpansionOut:
    from abacus.modules.sampling.expansions import ExpansionView

    v = cast(ExpansionView, view)
    initials = "".join(part[0] for part in v.approver_name.split() if part)[:3].upper()
    return ExpansionOut(
        id=v.id,
        status=SampleExpansionStatus(v.status),
        base_count=v.base_count,
        add_count=v.add_count,
        resulting_count=v.resulting_count,
        approver_name=v.approver_name,
        approver_initials=initials or "-",
        requested_at=v.requested_at,  # type: ignore[arg-type] -- a timestamptz
    )
