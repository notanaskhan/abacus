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
from typing import Annotated, Any, Literal, cast
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
    # T-08-T22 (TAX-10's statement grammar): the line's printed reference ("1a", "Sch A 11"), its
    # group band and whether it is a total (stroke rule) or the grand total (double rule).
    line_ref: Annotated[str | None, Field(max_length=24), Internal] = None
    group: Annotated[Literal["income", "deductions", "tax_and_payments"] | None, Internal] = None
    total: Annotated[Literal["total", "grand"] | None, Internal] = None


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
    # T-08-T22 (TAX-10 e, DF-04 x1): an explain run in flight, and why Explain is not offered.
    explaining: Annotated[bool, Internal] = False
    explain_unavailable_reason: Annotated[
        Literal["agents_off_for_taxpayer", "ai_unavailable"] | None, Internal
    ] = None


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
    # T-08-T19 (additive): the default recipients' contacts, in `recipients`' order.
    recipient_contact_ids: Annotated[list[UUID], Internal] = []


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


def _two_year_out(found: object, view: TwoYearFilter) -> TaxPracticeTwoYearOut:
    from abacus.modules.tax.compute.two_year_lines import LINE_GROUPS, LINE_REFS, LINE_TOTALS
    from abacus.modules.tax.two_year_service import Comparison

    c = cast(Comparison, found)

    def pct(cy: Decimal, py: Decimal) -> Decimal | None:
        return None if py == 0 else ((cy - py) * 100 / abs(py)).quantize(Decimal("0.1"))

    lines = [
        TaxPracticeTwoYearLineOut(
            line_key=ln.line.code,
            label=ln.line.label,
            line_ref=LINE_REFS.get(ln.line.code),
            group=cast(Any, LINE_GROUPS.get(ln.line.code)),  # Any: one of the three bands
            total=cast(Any, LINE_TOTALS.get(ln.line.code)),  # Any: "total" or "grand"
            current=ln.line.current,
            prior=ln.line.prior,
            delta=ln.line.delta,
            delta_pct=ln.line.delta_pct,
            flagged=ln.line.flagged,
            below_reason=(
                "below_amount"
                if not ln.line.flagged
                and abs(ln.line.delta) < c.threshold.amount
                and ln.line.delta_pct is not None
                and abs(ln.line.delta_pct) >= c.threshold.pct
                else None
            ),
            state=cast(ExplanationState | None, ln.state),
            explanation=None if ln.explanation is None else ln.explanation.text,
            explanation_version_id=None if ln.explanation is None else ln.explanation.version_id,
            author_kind=None
            if ln.explanation is None
            else cast(Literal["human", "agent"], ln.explanation.author_kind),
            accepted_at=None if ln.explanation is None else ln.explanation.accepted_at,
            values_hash=ln.values_hash,
        )
        for ln in c.lines
        if view == "all" or ln.line.flagged
    ]
    flagged = [ln for ln in c.lines if ln.line.flagged]
    return TaxPracticeTwoYearOut(
        tax_return_id=c.return_id,
        current_summary_id=c.summary_version[:60],
        filter=view,
        threshold=TaxPracticeTwoYearThresholdOut(
            source="variance_policy",
            source_label="Firm variance policy (two-year)",
            version_id=c.threshold_version_id,
            amount=c.threshold.amount,
            percent=c.threshold.pct,
        ),
        lines=lines,
        agi=c.agi,
        agi_delta_pct=pct(c.agi, c.agi_prior),
        total_tax=c.total_tax,
        total_tax_delta_pct=pct(c.total_tax, c.total_tax_prior),
        refund=c.refund,
        prior_refund=c.prior_refund,
        over_threshold=len(flagged),
        accepted=sum(1 for ln in flagged if ln.state == "accepted"),
        explain_available=False,
    )


@practice_tools_router.get(
    f"{_R}/two-year", action="tax_return.read", response_model=TaxPracticeTwoYearOut, errors=(501,)
)
async def two_year_route(
    return_id: UUID, ctx: Ctx, filter: TwoYearFilter = "all"
) -> TaxPracticeTwoYearOut:
    """TAX-10 a/b; 409 `threshold_unavailable` without the firm's two-year variance row,
    `comparison_unavailable` without both years' approved summaries (S51 partials)."""
    await _on(ctx, _Y)
    from abacus.modules.tax.two_year_service import comparison

    return _two_year_out(await comparison(ctx, return_id), filter)


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
    """A person starts the run; 409 `consent_7216_missing` without both consents (AC-23), 409
    `agent_not_available` on a firm whose AI boundary is not cleared (DF-04). T-08-T26 (DEC-5923):
    the run is inline; each flagged line gets a suggestion with verified citations and an agent
    explanation version a reviewer accepts."""
    await _human(ctx, _Y, "two_year.explain")
    from abacus.modules.tax.practice_modes import two_year_explain

    del key  # each start is a new run (the explanations are versions)
    found = await two_year_explain(ctx, return_id, body.line_keys)
    return TaxPracticeRunStartedOut(run_id=found.run_id, started_at=found.started_at)


@practice_tools_router.put(
    f"{_R}/two-year/lines/{{line_key}}/explanation",
    action="variance_explanation.edit",
    response_model=TaxPracticeTwoYearLineOut,
    errors=(409, 501),
)
async def two_year_explanation_route(
    return_id: UUID, line_key: str, body: TaxPracticeExplanationIn, ctx: Ctx, if_match: IfMatch
) -> TaxPracticeTwoYearLineOut:
    """A new insert-only version (S51 partials)."""
    await _human(ctx, _Y, "variance_explanation.edit")
    from abacus.modules.tax.two_year_service import edit_explanation

    found = _two_year_out(await edit_explanation(ctx, return_id, line_key, body.text), "all")
    return next(ln for ln in found.lines if ln.line_key == line_key)


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
    from abacus.modules.tax.two_year_service import accept

    found = _two_year_out(
        await accept(ctx, return_id, line_key, body.explanation_version_id, body.values_hash),
        "all",
    )
    return next(ln for ln in found.lines if ln.line_key == line_key)


@practice_tools_router.get(
    f"{_R}/two-year.xlsx", action="export.create", response_model=bytes, errors=(501,)
)
async def two_year_export_route(return_id: UUID, ctx: Ctx) -> bytes:
    await _human(ctx, _Y, "export.create")
    from abacus.modules.tax.two_year_service import export_xlsx

    return await export_xlsx(ctx, return_id)


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
    """TAX-14's runs (T-08-T14)."""
    await _on(ctx, _S)
    from abacus.modules.tax.standards_runs import runs

    return TaxPracticeRunListOut(
        items=[_run_out(r) for r in await runs(ctx, None, form, status)], next_cursor=None
    )


def _run_out(r: object) -> TaxPracticeRunOut:
    from abacus.modules.tax.standards_runs import RunView

    run = cast(RunView, r)
    items = [
        TaxPracticeRunItemOut(
            work_item_id=i.work_item_id,
            client_name=i.client_name,
            status=cast(Any, i.status),  # Any: a row value
            checks_total=i.checks_total, checks_passed=i.checks_passed, exceptions=i.exceptions,
            linked_issues=i.linked, created_issues=i.created,
            issue_count=i.linked + i.created,
        )
        for i in run.items
    ]  # fmt: skip
    return TaxPracticeRunOut(
        run_id=run.run_id, standard_version_id=run.version_id, standard_label=run.label,
        form=run.form,
        status=cast(Any, run.status),  # Any: a row value
        started_at=cast(Any, run.started_at),  # Any: a row value
        completed_at=cast(Any, run.completed_at),  # Any: a row value
        tiles=TaxPracticeRunTilesOut(
            selected=len(items),
            running=sum(1 for i in items if i.status == "running"),
            passed=sum(1 for i in items if i.status == "passed"),
            exceptions=sum(1 for i in items if i.status == "exceptions"),
            queued=sum(1 for i in items if i.status == "queued"),
        ),
        items=items, allowed_actions=["rerun"],
    )  # fmt: skip


@practice_tools_router.get(
    "/standards-runs/{run_id}",
    action="standards_run.read",
    response_model=TaxPracticeRunOut,
    errors=(501,),
)
async def standards_run_route(run_id: UUID, ctx: Ctx) -> TaxPracticeRunOut:
    await _on(ctx, _S)
    from abacus.modules.tax.standards_runs import runs

    found = await runs(ctx, run_id)
    if not found:
        raise NotFound("standards_run")
    return _run_out(found[0])


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
    from abacus.modules.tax.standards_runs import checks

    out: list[TaxPracticeCheckOut] = []
    for c in await checks(ctx, run_id, work_item_id):
        key = str(c["check_key"])
        out.append(
            TaxPracticeCheckOut(
                result_id=cast(UUID, c["id"]), check_key=key, display_code=key.split("/")[-1],
                title=key.split("/")[-1],
                outcome=cast(Any, c["confirmed"] or c["outcome"]),  # Any: a row value
                difference=cast(Any, c["difference"]),  # Any: a row value
                linked_issue_id=cast(Any, c["linked_issue_id"]),  # Any: a row value
                created_issue_id=cast(Any, c["created_issue_id"]),  # Any: a row value
                allowed_actions=(
                    ["confirm"] if c["outcome"] == "manual_pending" and not c["confirmed"] else []
                ),
            )
        )  # fmt: skip
    return TaxPracticeCheckListOut(items=out)


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
    from abacus.modules.tax.standards_runs import start

    del key  # the run is keyed by its id; a retried POST starts a new run (TAX-14 allows it)
    run_id = await start(ctx, body.standard_version_id, list(body.return_ids))
    return await standards_run_route(run_id, ctx)


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
    from abacus.modules.tax.standards_runs import rerun

    del key
    new_id = await rerun(ctx, run_id, list(body.return_ids))
    return await standards_run_route(new_id, ctx)


@practice_tools_router.post(
    "/standards-check-results/{result_id}:confirm",
    action="standards_check.confirm",
    response_model=TaxPracticeCheckOut,
    errors=(409, 501),
)
async def standards_check_confirm_route(
    result_id: UUID, body: TaxPracticeConfirmIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeCheckOut:
    """A reviewer's confirmation of a manual item, once (409 `check_already_confirmed`)."""
    await _human(ctx, _S, "standards_check.confirm")
    from abacus.modules.tax.standards_runs import confirm

    del key
    await confirm(ctx, result_id, body.outcome, body.note)
    return TaxPracticeCheckOut(
        result_id=result_id, check_key="", display_code="", title="", outcome=body.outcome
    )


def _opportunity_out(
    found: object, *, envelope: UUID | None, actions: list[str]
) -> TaxPracticeOpportunityOut:
    from abacus.modules.tax.planning.service import Opportunity

    o = cast(Opportunity, found)
    return TaxPracticeOpportunityOut(
        opportunity_id=o.id,
        client_id=o.client_id,
        client_name=o.client_name,
        work_item_id=o.work_item_id,
        rule_key=o.rule_key,
        category=o.category,
        title=o.title,
        status=o.status,
        est_savings=o.est_savings,
        rationale=o.rationale,
        rationale_source=o.rationale_source,
        consent_envelope_id=envelope,
        raised_at=o.raised_at,
        project_engagement_id=o.project_engagement_id,
        row_version=o.row_version,
        allowed_actions=actions,
    )


async def _opportunity(ctx: AuthContext, opportunity_id: UUID) -> TaxPracticeOpportunityOut:
    from abacus.modules.tax.planning import service as ps

    found = await ps.opportunity(ctx, opportunity_id)
    return _opportunity_out(
        found,
        envelope=await ps.consent_envelope(ctx.tenant, found),
        actions=await ps.allowed(ctx, found),
    )


@practice_tools_router.get(
    "/planning-summary",
    action="planning.read",
    response_model=TaxPracticePlanningSummaryOut,
)
async def planning_summary_route(
    ctx: Ctx, tax_year: int, partner_id: UUID | None = None
) -> TaxPracticePlanningSummaryOut:
    """T-08-T19 (DEC-5916): the strip, by code over the viewer's visible returns (AC-27)."""
    await _on(ctx, _P)
    from abacus.modules.tax.planning import service as ps

    found = await ps.summary(ctx, tax_year, partner_id)
    return TaxPracticePlanningSummaryOut(
        tax_year=found.tax_year,
        clients_to_contact=found.clients_to_contact,
        est_savings=found.est_savings,
        talking_points=found.talking_points,
        consent_blocked=found.consent_blocked,
        opportunities=found.opportunities,
        clients=found.clients,
    )


_PAGE = 50


@practice_tools_router.get(
    "/planning-opportunities",
    action="planning.read",
    response_model=TaxPracticeOpportunityListOut,
)
async def planning_opportunities_route(
    ctx: Ctx,
    status: OpportunityStatus | None = None,
    client_id: UUID | None = None,
    work_item_id: UUID | None = None,
    include_dismissed: bool = False,
    cursor: str | None = None,
) -> TaxPracticeOpportunityListOut:
    """The queue (TAX-15 a, e, f): keyset on the opportunity id, 50 a page; `total` counts
    every match ("Showing 9 of 71")."""
    await _on(ctx, _P)
    from abacus.modules.tax.planning import service as ps

    found = await ps.opportunities(
        ctx, status=status, client_id=client_id, work_item_id=work_item_id,
        include_dismissed=include_dismissed,
    )  # fmt: skip
    ordered = sorted(found, key=lambda o: str(o.id))
    after = [o for o in ordered if cursor is None or str(o.id) > cursor]
    page = after[:_PAGE]
    items = [
        _opportunity_out(
            o, envelope=await ps.consent_envelope(ctx.tenant, o), actions=await ps.allowed(ctx, o)
        )
        for o in page
    ]
    more = len(after) > _PAGE
    return TaxPracticeOpportunityListOut(
        items=items, total=len(found), next_cursor=str(page[-1].id) if more and page else None
    )


@practice_tools_router.get(
    "/planning-opportunities/{opportunity_id}",
    action="planning.read",
    response_model=TaxPracticeOpportunityOut,
)
async def planning_opportunity_route(opportunity_id: UUID, ctx: Ctx) -> TaxPracticeOpportunityOut:
    await _on(ctx, _P)
    return await _opportunity(ctx, opportunity_id)


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:prepare-raise",
    action="planning.raise",
    response_model=TaxPracticeRaiseSheetOut,
    errors=(409,),
)
async def planning_prepare_raise_route(
    opportunity_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeRaiseSheetOut:
    """The send sheet on the firm's "Planning conversation" template (DEC-79; P-25 is not
    accepted, so no agent draft); nothing is sent. 409 `planning_template_missing`."""
    await _human(ctx, _P, "planning.raise")
    from abacus.modules.tax.planning import service as ps

    del key  # a read: repeating it changes nothing
    sheet = await ps.prepare_raise(ctx, opportunity_id)
    return TaxPracticeRaiseSheetOut(
        template_id=sheet.template_version_id,
        subject=sheet.subject,
        body=sheet.body,
        draft_from_agent=False,
        recipients=[name for _c, name in sheet.recipients],
        recipient_contact_ids=[c for c, _name in sheet.recipients],
    )


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:raise",
    action="planning.raise",
    response_model=TaxPracticeOpportunityOut,
    errors=(409,),
)
async def planning_raise_route(
    opportunity_id: UUID, body: TaxPracticeRaiseIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    """Raised only after a person's send through `message.send` (AC-27); a retry of a raised
    opportunity answers it unchanged."""
    await _human(ctx, _P, "planning.raise")
    from abacus.modules.tax.planning import service as ps

    del key
    await ps.raise_with_client(
        ctx, opportunity_id, subject=body.subject, body=body.body,
        recipient_contact_ids=body.recipient_contact_ids,
    )  # fmt: skip
    return await _opportunity(ctx, opportunity_id)


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:create-project",
    action="planning.create_project",
    response_model=TaxPracticeProjectPrefillOut,
    errors=(409,),
)
async def planning_create_project_route(
    opportunity_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeProjectPrefillOut:
    """ENG-03's prefill; the opportunity becomes Accepted when the engagement is created."""
    await _human(ctx, _P, "planning.create_project")
    from abacus.modules.tax.planning import service as ps

    del key
    found = await ps.create_project(ctx, opportunity_id)
    return TaxPracticeProjectPrefillOut(
        engagement_name=found.engagement_name,
        owner_user_id=found.owner_user_id,
        client_id=found.client_id,
        source_ref=found.source_ref,
    )


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:decline",
    action="planning.dismiss",
    response_model=TaxPracticeOpportunityOut,
    errors=(409,),
)
async def planning_decline_route(
    opportunity_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    await _human(ctx, _P, "planning.dismiss")
    from abacus.modules.tax.planning import service as ps

    del key
    await ps.decline(ctx, opportunity_id)
    return await _opportunity(ctx, opportunity_id)


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:dismiss",
    action="planning.dismiss",
    response_model=TaxPracticeOpportunityOut,
    errors=(409,),
)
async def planning_dismiss_route(
    opportunity_id: UUID, body: TaxPracticeDismissIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    await _human(ctx, _P, "planning.dismiss")
    from abacus.modules.tax.planning import service as ps

    del key
    await ps.dismiss(ctx, opportunity_id, body.reason, body.note)
    return await _opportunity(ctx, opportunity_id)


@practice_tools_router.post(
    "/planning-opportunities/{opportunity_id}:restore",
    action="planning.dismiss",
    response_model=TaxPracticeOpportunityOut,
    errors=(409,),
)
async def planning_restore_route(
    opportunity_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    await _human(ctx, _P, "planning.dismiss")
    from abacus.modules.tax.planning import service as ps

    del key
    await ps.restore(ctx, opportunity_id)
    return await _opportunity(ctx, opportunity_id)


@practice_tools_router.post(
    "/planning-opportunities",
    action="planning.create",
    response_model=TaxPracticeOpportunityOut,
    status_code=201,
    errors=(409,),
)
async def planning_create_route(
    body: TaxPracticeOpportunityCreateIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeOpportunityOut:
    """TXT-03's "Add to planning" or a TXP-01 memo item: Open, no model (AC5.7). The same
    source item answers its existing opportunity."""
    await _human(ctx, _P, "planning.create")
    from abacus.modules.tax.planning import service as ps

    del key
    found = await ps.create_manual(
        ctx, body.work_item_id, body.title, body.source, body.source_ref
    )
    return await _opportunity(ctx, found.id)


@practice_tools_router.post(
    f"{_R}/amendments",
    action="amendment.create",
    response_model=TaxPracticeAmendmentOut,
    status_code=201,
    errors=(409,),
)
async def amendment_create_route(
    return_id: UUID, body: TaxPracticeAmendmentCreateIn, ctx: Ctx, key: IdempotencyKey
) -> TaxPracticeAmendmentOut:
    """A new linked return from an accepted original; the original is never changed (AC-28)."""
    await _human(ctx, _A, "amendment.create")
    from abacus.modules.tax import amendments

    del key  # one open amendment per original: a replay answers 409 `amendment_exists`
    made = await amendments.create(
        ctx, return_id, kind=body.kind, jurisdictions=list(body.jurisdictions)
    )
    return await _amendment(ctx, made, body.jurisdictions[0])


async def _amendment(
    ctx: AuthContext, amendment_id: UUID, jurisdiction: str
) -> TaxPracticeAmendmentOut:
    """TAX-16's read: code's lines per jurisdiction (ADR-050), labelled `engine` (DEC-77)."""
    from abacus.modules.tax import amendments

    found = await amendments.view(ctx, amendment_id, jurisdiction)
    name = None
    if found.explanation_author is not None:
        from abacus.modules.identity.api import display_names

        name = (await display_names([found.explanation_author])).get(found.explanation_author)
    return TaxPracticeAmendmentOut(
        amendment_id=found.amendment_id,
        kind=cast(AmendmentKind, found.kind),
        work_item_id=found.work_item_id,
        original_work_item_id=found.original_work_item_id,
        jurisdiction=cast(Jurisdiction, jurisdiction),
        jurisdictions=[cast(Jurisdiction, j) for j in found.jurisdictions],
        lines=[
            TaxPracticeAmendmentLineOut(
                line_key=ln.line_key, label=ln.label, as_filed=ln.as_filed,
                as_amended=ln.as_amended, change=ln.change, value_source="engine",
            )
            for ln in found.amended.lines
        ],
        total_change=found.amended.total_change,
        refund_due=found.amended.refund_due,
        balance_due=found.amended.balance_due,
        explanation=found.explanation,
        explanation_author=name,
        status=cast(Literal["draft", "approved", "filed"], found.status),
        original_superseded=found.original_superseded,
        row_version=found.row_version,
    )  # fmt: skip


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
    return await _amendment(ctx, amendment_id, jurisdiction)


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
    from abacus.modules.tax import amendments

    seen = int(if_match.strip('"W/')) if if_match.strip('"W/').isdigit() else 0
    await amendments.explain(ctx, amendment_id, body.text, seen)
    return await _amendment(ctx, amendment_id, "federal")


@practice_tools_router.post(
    "/amendments/{amendment_id}/routing",
    action="amendment.edit",
    response_model=TaxPracticeAmendmentOut,
    errors=(409,),
)
async def amendment_route_for_approval_route(
    amendment_id: UUID, ctx: Ctx
) -> TaxPracticeAmendmentOut:
    """T-08-T30 (additive): "Route for approval…" asks the signer (C16, HOME-02); the approval is
    the amendment return's final approval (`tax/approval.py`)."""
    await _human(ctx, _A, "amendment.edit")
    from abacus.modules.tax import amendments

    await amendments.route_for_approval(ctx, amendment_id)
    return await _amendment(ctx, amendment_id, "federal")


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
