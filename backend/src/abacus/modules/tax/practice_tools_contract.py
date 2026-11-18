"""Tax practice tools v1 stub (TP-1; T-08-T04; SPEC-710 AC-21 to AC-30;
`docs/contracts/tax-practice.md`). Screens TAX-10 two-year comparison, TAX-14 firm standards run,
TAX-15 planning opportunities, TAX-16 amendments and AARs.

Every route answers, in order: a client principal 404 (no portal route; INV-4); its flag off 404
(`tax.two_year`, `tax.standards_runs`, `tax.planning`, `tax.amendments`); a human-only route
refuses an agent, the platform or a support session 403 (INV-1); then 501 until its build task
(T-08-T11, T13, T14, T19, T30, T33).

Classification (ADR-031, ADR-167): every return figure, explanation, rationale and name is TRI
(`restricted`, `tri=True`); ids, counts, codes, states and percentages' codes are `internal`.
Money is `Decimal`; Δ, Δ%, check differences, savings estimates and amendment changes are code
(ADR-050). Tax, the IL-1040-X tax and the imputed underpayment are engine imports or a labelled
shadow tie-out (DEC-77).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_AMENDMENTS, TAX_PLANNING, TAX_STANDARDS_RUNS, TAX_TWO_YEAR
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=40)]
Internal = classified("internal")
Tri = classified("restricted", tri=True)
Count = Annotated[int, Field(ge=0), Internal]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Tri]
MaybeMoney = Annotated[Decimal | None, Field(max_digits=20, decimal_places=2), Tri]
MaybePct = Annotated[Decimal | None, Field(max_digits=7, decimal_places=1), Tri]
Text = Annotated[str, Field(max_length=2000), Tri]

ExplanationState = Literal["unexplained", "proposed", "accepted", "stale"]
TwoYearFilter = Literal["all", "over_threshold"]
RunStatus = Literal["queued", "running", "complete", "failed"]
RunItemStatus = Literal["queued", "running", "passed", "exceptions", "failed"]
CheckOutcome = Literal["pass", "exception", "manual_pending", "not_applicable"]
OpportunityStatus = Literal["open", "raised", "accepted", "declined", "not_screened", "dismissed"]
DismissReason = Literal["not_suitable", "already_in_place", "client_declined", "other"]
Jurisdiction = Literal["federal", "il"]
AmendmentKind = Literal["amended_return", "bba_aar"]
IuSource = Literal["engine", "shadow"]
BbaRoute = Literal["pay_imputed_underpayment", "push_out"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class TaxPracticeCitationOut(BaseModel):
    model_config = _cfg()

    citation_id: Annotated[UUID, Internal]
    label: Annotated[str, Field(max_length=200), Tri]
    verified: Annotated[bool, Internal]


# --- TAX-10 two-year comparison ----------------------------------------------------------------


class TaxPracticeTwoYearThresholdOut(BaseModel):
    """OQ-2: the source actually used, named and pinned (AC-22)."""

    model_config = _cfg()

    source: Annotated[Literal["checklist_parameter", "variance_policy"], Internal]
    source_label: Annotated[str, Field(max_length=120), Internal]
    version_id: Annotated[UUID, Internal]
    amount: Money
    percent: Annotated[Decimal, Field(max_digits=5, decimal_places=1), Internal]


class TaxPracticeTwoYearLineOut(BaseModel):
    model_config = _cfg()

    line_key: Annotated[str, Field(max_length=40), Internal]
    label: Annotated[str, Field(max_length=200), Internal]
    current: Money
    prior: Money
    delta: Money
    delta_pct: MaybePct = None
    flagged: Annotated[bool, Internal]
    below_reason: Annotated[str | None, Field(max_length=60), Internal] = None
    state: Annotated[ExplanationState | None, Internal] = None
    explanation: Annotated[str | None, Field(max_length=2000), Tri] = None
    explanation_version_id: Annotated[UUID | None, Internal] = None
    author_kind: Annotated[Literal["human", "agent"] | None, Internal] = (
        None  # this order: Literal is cached by members (tax_workbook v1 freezes human, agent)
    )
    citations: Annotated[list[TaxPracticeCitationOut], Internal] = []
    accepted_by_initials: Annotated[str | None, Field(max_length=4), Tri] = None
    accepted_at: Annotated[datetime | None, Internal] = None
    values_hash: Hash
    allowed_actions: Annotated[list[str], Internal] = []


class TaxPracticeTwoYearOut(BaseModel):
    """TAX-10 a (AC-21): AGI 598,030 (+8.4%) · total tax 123,223 · 8 flagged · 7 of 8 accepted."""

    model_config = _cfg()

    tax_return_id: Annotated[UUID, Internal]
    current_summary_id: Annotated[str, Field(max_length=60), Internal]
    filter: Annotated[TwoYearFilter, Internal]
    threshold: Annotated[TaxPracticeTwoYearThresholdOut, Internal]
    lines: Annotated[list[TaxPracticeTwoYearLineOut], Internal]
    agi: Money
    agi_delta_pct: MaybePct = None
    total_tax: Money
    total_tax_delta_pct: MaybePct = None
    refund: MaybeMoney = None
    prior_refund: MaybeMoney = None
    over_threshold: Count
    accepted: Count
    explain_available: Annotated[bool, Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class TaxPracticeExplainIn(BaseModel):
    model_config = _cfg()

    line_keys: Annotated[list[str], Field(max_length=200), Internal] = []


class TaxPracticeRunStartedOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    started_at: Annotated[datetime, Internal]


class TaxPracticeExplanationIn(BaseModel):
    """A human version (two lines; "Edited by <name>")."""

    model_config = _cfg()

    text: Annotated[str, Field(min_length=1, max_length=600), Tri]


class TaxPracticeAcceptIn(BaseModel):
    model_config = _cfg()

    explanation_version_id: Annotated[UUID, Internal]
    values_hash: Hash


# --- TAX-14 standards runs ---------------------------------------------------------------------


class TaxPracticeRunTilesOut(BaseModel):
    model_config = _cfg()

    selected: Count
    running: Count
    passed: Count
    exceptions: Count
    queued: Count


class TaxPracticeRunItemOut(BaseModel):
    model_config = _cfg()

    work_item_id: Annotated[UUID, Internal]
    client_name: Annotated[str, Field(max_length=200), Tri]
    status: Annotated[RunItemStatus, Internal]
    checks_total: Count
    checks_passed: Count
    exceptions: Count
    linked_issues: Count
    created_issues: Count
    issue_count: Count


class TaxPracticeRunOut(BaseModel):
    """TAX-14 A at 9:24 AM (AC-26): 6 = 1 running + 3 passed + 2 with exceptions."""

    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    standard_version_id: Annotated[UUID, Internal]
    standard_label: Annotated[str, Field(max_length=120), Internal]
    form: Annotated[str, Field(max_length=10), Internal]
    status: Annotated[RunStatus, Internal]
    started_at: Annotated[datetime, Internal]
    completed_at: Annotated[datetime | None, Internal] = None
    tiles: Annotated[TaxPracticeRunTilesOut, Internal]
    items: Annotated[list[TaxPracticeRunItemOut], Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class TaxPracticeRunListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TaxPracticeRunOut], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class TaxPracticeCheckOut(BaseModel):
    model_config = _cfg()

    result_id: Annotated[UUID, Internal]
    check_key: Annotated[str, Field(max_length=40), Internal]  # "1065-v4/C-17"
    display_code: Annotated[str, Field(max_length=10), Internal]  # "C-17"
    title: Annotated[str, Field(max_length=200), Internal]
    outcome: Annotated[CheckOutcome, Internal]
    difference: MaybeMoney = None
    linked_issue_id: Annotated[UUID | None, Internal] = None
    created_issue_id: Annotated[UUID | None, Internal] = None
    allowed_actions: Annotated[list[str], Internal] = []


class TaxPracticeCheckListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TaxPracticeCheckOut], Internal]


class TaxPracticeRunStartIn(BaseModel):
    model_config = _cfg()

    standard_version_id: Annotated[UUID, Internal]
    return_ids: Annotated[list[UUID], Field(min_length=1, max_length=200), Internal]


class TaxPracticeRerunIn(BaseModel):
    model_config = _cfg()

    return_ids: Annotated[list[UUID], Field(min_length=1, max_length=200), Internal]


class TaxPracticeConfirmIn(BaseModel):
    model_config = _cfg()

    outcome: Annotated[Literal["pass", "exception"], Internal]
    note: Annotated[str | None, Field(max_length=1000), Tri] = None


# --- TAX-15 planning ---------------------------------------------------------------------------


class TaxPracticePlanningSummaryOut(BaseModel):
    """The strip (AC-27): 58 clients · about $1.2M · Drafted · 1 consent-blocked; 9 of 71."""

    model_config = _cfg()

    tax_year: Annotated[int, Field(ge=2020, le=2100), Internal]
    clients_to_contact: Count
    est_savings: Money
    talking_points: Annotated[Literal["drafted", "template", "none"], Internal]
    consent_blocked: Count
    opportunities: Count
    clients: Count


class TaxPracticeOpportunityOut(BaseModel):
    model_config = _cfg()

    opportunity_id: Annotated[UUID, Internal]
    client_id: Annotated[UUID, Internal]
    client_name: Annotated[str, Field(max_length=200), Tri]
    work_item_id: Annotated[UUID | None, Internal] = None
    rule_key: Annotated[str, Field(max_length=60), Internal]
    category: Annotated[str, Field(max_length=60), Internal]
    title: Annotated[str, Field(max_length=200), Tri]
    status: Annotated[OpportunityStatus, Internal]
    est_savings: MaybeMoney = None
    rationale: Annotated[str | None, Field(max_length=4000), Tri] = None
    rationale_source: Annotated[Literal["agent", "template"] | None, Internal] = None
    citations: Annotated[list[TaxPracticeCitationOut], Internal] = []
    consent_envelope_id: Annotated[UUID | None, Internal] = None
    raised_at: Annotated[datetime | None, Internal] = None
    project_engagement_id: Annotated[UUID | None, Internal] = None
    row_version: Annotated[int, Field(ge=1), Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class TaxPracticeOpportunityListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[TaxPracticeOpportunityOut], Internal]
    total: Count
    next_cursor: Annotated[str | None, Internal] = None


class TaxPracticeRaiseSheetOut(BaseModel):
    """The send sheet's payload: the firm's database template, or a permitted draft (DEC-79)."""

    model_config = _cfg()

    template_id: Annotated[UUID | None, Internal] = None
    subject: Annotated[str, Field(max_length=200), Tri]
    body: Annotated[str, Field(max_length=8000), Tri]
    draft_from_agent: Annotated[bool, Internal]
    recipients: Annotated[list[str], Tri]


class TaxPracticeRaiseIn(BaseModel):
    model_config = _cfg()

    subject: Annotated[str, Field(min_length=1, max_length=200), Tri]
    body: Annotated[str, Field(min_length=1, max_length=8000), Tri]
    recipient_contact_ids: Annotated[list[UUID], Field(min_length=1, max_length=10), Internal]


class TaxPracticeProjectPrefillOut(BaseModel):
    model_config = _cfg()

    engagement_name: Annotated[str, Field(max_length=200), Tri]
    owner_user_id: Annotated[UUID, Internal]
    client_id: Annotated[UUID, Internal]
    source_ref: Annotated[str, Field(max_length=80), Internal]


class TaxPracticeDismissIn(BaseModel):
    model_config = _cfg()

    reason: Annotated[DismissReason, Internal]
    note: Annotated[str | None, Field(max_length=1000), Tri] = None


class TaxPracticeOpportunityCreateIn(BaseModel):
    model_config = _cfg()

    work_item_id: Annotated[UUID, Internal]
    title: Annotated[str, Field(min_length=1, max_length=200), Tri]
    source: Annotated[Literal["txt03_add_to_planning", "txp01_memo"], Internal]
    source_ref: Annotated[str, Field(max_length=80), Internal]


# --- TAX-16 amendments and AARs ----------------------------------------------------------------


class TaxPracticeAmendmentLineOut(BaseModel):
    model_config = _cfg()

    line_key: Annotated[str, Field(max_length=40), Internal]
    label: Annotated[str, Field(max_length=200), Internal]
    as_filed: Money
    as_amended: Money
    change: Money
    value_source: Annotated[Literal["engine", "shadow", "code"], Internal]
    citations: Annotated[list[TaxPracticeCitationOut], Internal] = []


class TaxPracticeAmendmentOut(BaseModel):
    """TAX-16 a (AC-28): refund due 2,708 = 41,000 - 37,678 - 614; IL change (495)."""

    model_config = _cfg()

    amendment_id: Annotated[UUID, Internal]
    kind: Annotated[AmendmentKind, Internal]
    work_item_id: Annotated[UUID, Internal]
    original_work_item_id: Annotated[UUID, Internal]
    jurisdiction: Annotated[Jurisdiction, Internal]
    jurisdictions: Annotated[list[Jurisdiction], Internal]
    lines: Annotated[list[TaxPracticeAmendmentLineOut], Internal]
    total_change: Money
    refund_due: MaybeMoney = None
    balance_due: MaybeMoney = None
    explanation: Annotated[str | None, Field(max_length=4000), Tri] = None
    explanation_author: Annotated[str | None, Field(max_length=200), Tri] = None
    status: Annotated[Literal["draft", "approved", "filed"], Internal]
    original_superseded: Annotated[bool, Internal]
    row_version: Annotated[int, Field(ge=1), Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class TaxPracticeAmendmentCreateIn(BaseModel):
    model_config = _cfg()

    kind: Annotated[AmendmentKind, Internal] = "amended_return"
    jurisdictions: Annotated[list[Jurisdiction], Field(min_length=1, max_length=5), Internal]


class TaxPracticeAmendmentExplanationIn(BaseModel):
    model_config = _cfg()

    text: Annotated[str, Field(min_length=1, max_length=4000), Tri]


class TaxPracticeAarAdjustmentOut(BaseModel):
    model_config = _cfg()

    reviewed_year: Annotated[int, Field(ge=2018, le=2100), Internal]
    description: Annotated[str, Field(max_length=200), Tri]
    amount: Money


class TaxPracticeAarOut(BaseModel):
    """TAX-16 e (AC-30): 14,800 = 40,000 x 37%; the election is the signer's decision."""

    model_config = _cfg()

    aar_id: Annotated[UUID, Internal]
    work_item_id: Annotated[UUID, Internal]
    adjustments: Annotated[list[TaxPracticeAarAdjustmentOut], Internal]
    imputed_underpayment: Money
    iu_source: Annotated[IuSource, Internal]
    decision_card_id: Annotated[UUID | None, Internal] = None
    recommendation: Annotated[BbaRoute | None, Internal] = None
    decided_route: Annotated[BbaRoute | None, Internal] = None
    allowed_actions: Annotated[list[str], Internal] = []


class TaxPracticeAarCreateIn(BaseModel):
    model_config = _cfg()

    reviewed_year: Annotated[int, Field(ge=2018, le=2100), Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

practice_tools_router = AbacusRouter(prefix="/v1", tags=["tax"])
_R = "/tax-returns/{return_id}"


async def _on(ctx: AuthContext, flag: Flag) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


async def _human(ctx: AuthContext, flag: Flag, action: str) -> None:
    await _on(ctx, flag)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


_Y = TAX_TWO_YEAR
_S = TAX_STANDARDS_RUNS
_P = TAX_PLANNING
_A = TAX_AMENDMENTS


@practice_tools_router.get(
    f"{_R}/two-year", action="tax_return.read", response_model=TaxPracticeTwoYearOut, errors=(501,)
)
async def two_year_route(
    return_id: UUID, ctx: Ctx, filter: TwoYearFilter = "all"
) -> TaxPracticeTwoYearOut:
    await _on(ctx, _Y)
    raise NotImplementedYet


@practice_tools_router.post(
    f"{_R}/two-year:explain",
    action="two_year.explain",
    response_model=TaxPracticeRunStartedOut,
    status_code=202,
    errors=(409, 501),
)
async def two_year_explain_route(
    return_id: UUID, body: TaxPracticeExplainIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeRunStartedOut:
    """A person starts the run; 409 `consent_7216_missing` without both consents (AC-23)."""
    await _human(ctx, _Y, "two_year.explain")
    raise NotImplementedYet


@practice_tools_router.put(
    f"{_R}/two-year/lines/{{line_key}}/explanation",
    action="variance_explanation.edit",
    response_model=TaxPracticeTwoYearLineOut,
    errors=(409, 501),
)
async def two_year_explanation_route(
    return_id: UUID, line_key: str, body: TaxPracticeExplanationIn, ctx: Ctx, if_match: IfMatch
) -> TaxPracticeTwoYearLineOut:
    await _human(ctx, _Y, "variance_explanation.edit")
    raise NotImplementedYet


@practice_tools_router.post(
    f"{_R}/two-year/lines/{{line_key}}/explanation:accept",
    action="variance_explanation.accept",
    response_model=TaxPracticeTwoYearLineOut,
    errors=(409, 501),
)
async def two_year_accept_route(
    return_id: UUID, line_key: str, body: TaxPracticeAcceptIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeTwoYearLineOut:
    """Human-only, insert-only; 409 `explanation_stale` when the values moved (AC-24, AC-25)."""
    await _human(ctx, _Y, "variance_explanation.accept")
    raise NotImplementedYet


@practice_tools_router.get(
    f"{_R}/two-year.xlsx", action="export.create", response_model=bytes, errors=(501,)
)
async def two_year_export_route(return_id: UUID, ctx: Ctx) -> bytes:
    await _human(ctx, _Y, "export.create")
    raise NotImplementedYet


@practice_tools_router.get(
    "/standards-runs",
    action="standards_run.read",
    response_model=TaxPracticeRunListOut,
    errors=(501,),
)
async def standards_runs_route(
    ctx: Ctx,
    form: Annotated[str | None, Query(max_length=10)] = None,
    status: RunStatus | None = None,
) -> TaxPracticeRunListOut:
    await _on(ctx, _S)
    raise NotImplementedYet


@practice_tools_router.get(
    "/standards-runs/{run_id}",
    action="standards_run.read",
    response_model=TaxPracticeRunOut,
    errors=(501,),
)
async def standards_run_route(run_id: UUID, ctx: Ctx) -> TaxPracticeRunOut:
    await _on(ctx, _S)
    raise NotImplementedYet


@practice_tools_router.get(
    "/standards-runs/{run_id}/items/{work_item_id}/checks",
    action="standards_run.read",
    response_model=TaxPracticeCheckListOut,
    errors=(501,),
)
async def standards_run_checks_route(
    run_id: UUID, work_item_id: UUID, ctx: Ctx
) -> TaxPracticeCheckListOut:
    await _on(ctx, _S)
    raise NotImplementedYet


@practice_tools_router.post(
    "/standards-runs",
    action="standards_run.start",
    response_model=TaxPracticeRunOut,
    status_code=202,
    errors=(409, 501),
)
async def standards_run_start_route(
    body: TaxPracticeRunStartIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeRunOut:
    """Pins the K-02 version; no model is called anywhere in TAX-14 (OQ-3)."""
    await _human(ctx, _S, "standards_run.start")
    raise NotImplementedYet


@practice_tools_router.post(
    "/standards-runs/{run_id}:rerun",
    action="standards_run.start",
    response_model=TaxPracticeRunOut,
    status_code=202,
    errors=(409, 501),
)
async def standards_run_rerun_route(
    run_id: UUID, body: TaxPracticeRerunIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeRunOut:
    await _human(ctx, _S, "standards_run.start")
    raise NotImplementedYet


@practice_tools_router.post(
    "/standards-check-results/{result_id}:confirm",
    action="standards_check.confirm",
    response_model=TaxPracticeCheckOut,
    errors=(409, 501),
)
async def standards_check_confirm_route(
    result_id: UUID, body: TaxPracticeConfirmIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeCheckOut:
    await _human(ctx, _S, "standards_check.confirm")
    raise NotImplementedYet


@practice_tools_router.get(
    "/planning-summary",
    action="planning.read",
    response_model=TaxPracticePlanningSummaryOut,
    errors=(501,),
)
async def planning_summary_route(
    ctx: Ctx, tax_year: int, partner_id: UUID | None = None
) -> TaxPracticePlanningSummaryOut:
    await _on(ctx, _P)
    raise NotImplementedYet


@practice_tools_router.get(
    "/planning-opportunities",
    action="planning.read",
    response_model=TaxPracticeOpportunityListOut,
    errors=(501,),
)
async def planning_opportunities_route(
    ctx: Ctx,
    status: OpportunityStatus | None = None,
    client_id: UUID | None = None,
    work_item_id: UUID | None = None,
    include_dismissed: bool = False,
    cursor: str | None = None,
) -> TaxPracticeOpportunityListOut:
    await _on(ctx, _P)
    raise NotImplementedYet


@practice_tools_router.get(
    "/planning-opportunities/{opportunity_id}",
    action="planning.read",
    response_model=TaxPracticeOpportunityOut,
    errors=(501,),
)
async def planning_opportunity_route(opportunity_id: UUID, ctx: Ctx) -> TaxPracticeOpportunityOut:
    await _on(ctx, _P)
    raise NotImplementedYet


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:prepare-raise",
    action="planning.raise",
    response_model=TaxPracticeRaiseSheetOut,
    errors=(409, 501),
)
async def planning_prepare_raise_route(
    opportunity_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeRaiseSheetOut:
    await _human(ctx, _P, "planning.raise")
    raise NotImplementedYet


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:raise",
    action="planning.raise",
    response_model=TaxPracticeOpportunityOut,
    errors=(409, 501),
)
async def planning_raise_route(
    opportunity_id: UUID, body: TaxPracticeRaiseIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    """Raised only after a person's send through `message.send` (AC-27)."""
    await _human(ctx, _P, "planning.raise")
    raise NotImplementedYet


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:create-project",
    action="planning.create_project",
    response_model=TaxPracticeProjectPrefillOut,
    errors=(409, 501),
)
async def planning_create_project_route(
    opportunity_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeProjectPrefillOut:
    await _human(ctx, _P, "planning.create_project")
    raise NotImplementedYet


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:decline",
    action="planning.dismiss",
    response_model=TaxPracticeOpportunityOut,
    errors=(409, 501),
)
async def planning_decline_route(
    opportunity_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    await _human(ctx, _P, "planning.dismiss")
    raise NotImplementedYet


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:dismiss",
    action="planning.dismiss",
    response_model=TaxPracticeOpportunityOut,
    errors=(409, 501),
)
async def planning_dismiss_route(
    opportunity_id: UUID, body: TaxPracticeDismissIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    await _human(ctx, _P, "planning.dismiss")
    raise NotImplementedYet


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:restore",
    action="planning.dismiss",
    response_model=TaxPracticeOpportunityOut,
    errors=(409, 501),
)
async def planning_restore_route(
    opportunity_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    await _human(ctx, _P, "planning.dismiss")
    raise NotImplementedYet


@practice_tools_router.post(
    "/planning-opportunities",
    action="planning.create",
    response_model=TaxPracticeOpportunityOut,
    status_code=201,
    errors=(409, 501),
)
async def planning_create_route(
    body: TaxPracticeOpportunityCreateIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    await _human(ctx, _P, "planning.create")
    raise NotImplementedYet


@practice_tools_router.post(
    f"{_R}/amendments",
    action="amendment.create",
    response_model=TaxPracticeAmendmentOut,
    status_code=201,
    errors=(409, 501),
)
async def amendment_create_route(
    return_id: UUID, body: TaxPracticeAmendmentCreateIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeAmendmentOut:
    """A new linked return from an accepted original; the original is never changed (AC-28)."""
    await _human(ctx, _A, "amendment.create")
    raise NotImplementedYet


@practice_tools_router.get(
    "/amendments/{amendment_id}",
    action="tax_return.read",
    response_model=TaxPracticeAmendmentOut,
    errors=(501,),
)
async def amendment_route(
    amendment_id: UUID, ctx: Ctx, jurisdiction: Jurisdiction = "federal"
) -> TaxPracticeAmendmentOut:
    await _on(ctx, _A)
    raise NotImplementedYet


@practice_tools_router.put(
    "/amendments/{amendment_id}/explanation",
    action="amendment.edit",
    response_model=TaxPracticeAmendmentOut,
    errors=(409, 501),
)
async def amendment_explanation_route(
    amendment_id: UUID, body: TaxPracticeAmendmentExplanationIn, ctx: Ctx, if_match: IfMatch
) -> TaxPracticeAmendmentOut:
    await _human(ctx, _A, "amendment.edit")
    raise NotImplementedYet


@practice_tools_router.post(
    "/amendments/{amendment_id}/proposals:draft",
    action="amendment.edit",
    response_model=TaxPracticeRunStartedOut,
    status_code=202,
    errors=(409, 501),
)
async def amendment_draft_route(
    amendment_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeRunStartedOut:
    await _human(ctx, _A, "amendment.edit")
    raise NotImplementedYet


@practice_tools_router.post(
    f"{_R}/aars",
    action="aar.create",
    response_model=TaxPracticeAarOut,
    status_code=201,
    errors=(409, 501),
)
async def aar_create_route(
    return_id: UUID, body: TaxPracticeAarCreateIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeAarOut:
    await _human(ctx, _A, "aar.create")
    raise NotImplementedYet


@practice_tools_router.get(
    "/aars/{aar_id}", action="tax_return.read", response_model=TaxPracticeAarOut, errors=(501,)
)
async def aar_route(aar_id: UUID, ctx: Ctx) -> TaxPracticeAarOut:
    await _on(ctx, _A)
    raise NotImplementedYet


@practice_tools_router.post(
    "/aars/{aar_id}/recommendation:draft",
    action="aar.create",
    response_model=TaxPracticeRunStartedOut,
    status_code=202,
    errors=(409, 501),
)
async def aar_recommendation_route(
    aar_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeRunStartedOut:
    """The recommendation is advisory; only the signer's `decision.decide` records the route."""
    await _human(ctx, _A, "aar.create")
    raise NotImplementedYet
