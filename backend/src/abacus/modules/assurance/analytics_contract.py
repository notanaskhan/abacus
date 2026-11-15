"""The audit-analytics and SSARS-workspace contract stubs (A-08-T05; SPEC-657 F5, F8; DEC-5032).
Contracts: `docs/contracts/audit-analytics.md` (AUD-13, AUD-26 analytics) and
`docs/contracts/ssars-workspace.md` (AUD-26).

Analytics sets are code's: change, change %, the dual threshold (percentage **and** amount) and
the tallies come from `workpapers.compute.flux` (A-08-T20); an explanation counts only with a
verified citation (422 `explanation_uncited`); a manager accepts, never the author. Client
questions and SSARS reminders are firm templates a person edits and sends (DV-4). One action per
route: client 404; the action on the work item's engagement; 404 with the flag off
(`audits.analytics` / `audits.ssars_workspace`); then 501 until A-08-T21 / T22.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDITS_ANALYTICS, AUDITS_SSARS_WORKSPACE
from abacus.kernel._statuses import AnalyticsLineStatus, AnalyticsSetStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Money = Annotated[Decimal, classified("confidential")]
Pct = Annotated[Decimal, classified("confidential")]
Stage = Literal["preliminary", "substantive", "final", "review"]
Kind = Literal["audit_flux", "ssars_review"]
SsarsMode = Literal["review", "compilation", "preparation"]


class ExplanationUncited(DomainInvalid):
    """An explanation without a verified citation cannot be saved as Explained (AC-5.3)."""

    code = "explanation_uncited"


class NoReportForPreparation(DomainConflict):
    """AR-C 70: no report for a preparation work item (AC-8.6)."""

    code = "no_report_for_preparation"


# --- analytics -----------------------------------------------------------------------------------


class AnalyticsRunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Annotated[Kind, classified("internal")]
    stage: Annotated[Stage, classified("internal")]
    trial_balance_id: Annotated[UUID, classified("internal")]
    layer: Annotated[Literal["unadjusted", "adjusted"], classified("internal")]
    py_source: Annotated[Literal["prior_engagement", "import"], classified("internal")]


class AnalyticsRunOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    analytics_set_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]


class ThresholdOut(BaseModel):
    """'10% and $116,250' with the materiality it came from and the deciding partner."""

    model_config = ConfigDict(frozen=True)

    pct: Pct
    amount: Money
    materiality_version_id: Annotated[UUID | None, classified("internal")]
    overall_materiality: Annotated[Money | None, classified("confidential")]
    provisional: Annotated[bool, classified("internal")]
    decider_name: Annotated[str | None, classified("confidential")]


class TalliesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    lines: Annotated[int, Field(ge=0), classified("internal")]
    over_threshold: Annotated[int, Field(ge=0), classified("internal")]
    explained: Annotated[int, Field(ge=0), classified("internal")]
    unexplained: Annotated[int, Field(ge=0), classified("internal")]
    tb_balanced: Annotated[bool, classified("internal")]


class ExplanationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    text: Annotated[str, Field(max_length=1000), classified("confidential")]
    citation_ids: Annotated[list[UUID], Field(min_length=1), classified("internal")]
    source: Annotated[Literal["agent", "staff", "client_answer"], classified("internal")]
    suggestion_id: Annotated[UUID | None, classified("internal")]
    authored_by_name: Annotated[str, classified("confidential")]
    client_answered_on: Annotated[date | None, classified("internal")]
    accepted_by_initials: Annotated[str | None, classified("internal")]


class ExpectationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    low_pct: Annotated[Pct | None, classified("confidential")]
    high_pct: Annotated[Pct | None, classified("confidential")]
    basis: Annotated[str, Field(max_length=300), classified("confidential")]


class AnalyticsLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    position: Annotated[int, Field(ge=1), classified("internal")]
    fs_line_key: Annotated[str, classified("internal")]
    caption: Annotated[str, classified("confidential")]
    group_key: Annotated[str, classified("internal")]
    cy: Money
    py: Money
    change: Money
    change_pct: Pct
    evaluated: Annotated[bool, classified("internal")]  # subtotals are derived, not evaluated
    over: Annotated[bool, classified("internal")]
    derived: Annotated[bool, classified("internal")]
    status: Annotated[AnalyticsLineStatus | None, classified("internal")]
    explanation: Annotated[ExplanationOut | None, classified("internal")]
    expectation: Annotated[ExpectationOut | None, classified("internal")]


class AnalyticsSetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[Kind, classified("internal")]
    stage: Annotated[Stage, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[AnalyticsSetStatus, classified("internal")]
    basis_label: Annotated[str, classified("internal")]  # "Unadjusted FY2026 vs audited FY2025"
    threshold: Annotated[ThresholdOut, classified("internal")]
    tallies: Annotated[TalliesOut, classified("internal")]
    lines: Annotated[list[AnalyticsLineOut], classified("internal")]
    engine_version: Annotated[str, classified("internal")]
    inputs_hash: Annotated[str, classified("internal")]
    allowed_actions: Annotated[
        list[
            Literal[
                "analytics.explain",
                "analytics.accept",
                "analytics.configure",
                "client_question.send",
                "analytics.export",
            ]
        ],
        classified("public"),
    ]


class ProvenanceOut(BaseModel):
    """SHL-09: the cell and its formula ('TB!D14')."""

    model_config = ConfigDict(frozen=True)

    cell: Annotated[str, classified("internal")]
    formula: Annotated[str, classified("internal")]
    sources: Annotated[list[str], classified("internal")]


class ExplanationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=1000), classified("confidential")]
    citation_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")]
    suggestion_id: Annotated[UUID | None, classified("internal")] = None


class ExpectationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    low_pct: Annotated[Decimal | None, classified("confidential")] = None
    high_pct: Annotated[Decimal | None, classified("confidential")] = None
    basis: Annotated[str, Field(min_length=1, max_length=300), classified("internal")]
    citation_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")] = []


class AcceptExplanationsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_positions: Annotated[
        list[int], Field(min_length=1, max_length=200), classified("internal")
    ]
    seen_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


class QuestionCardIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_key: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    text: Annotated[
        str, Field(min_length=1, max_length=2000), classified("confidential")
    ]  # the person's edited wording


class ClientQuestionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    line_positions: Annotated[
        list[int], Field(min_length=1, max_length=50), classified("internal")
    ]
    cards: Annotated[
        list[QuestionCardIn], Field(min_length=1, max_length=50), classified("confidential")
    ]
    recipient_contact_id: Annotated[UUID, classified("internal")]


class ClientQuestionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    questionnaire_id: Annotated[UUID, classified("internal")]
    sent_at: Annotated[datetime, classified("internal")]


class PriorYearFigureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fs_line_key: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    amount: Annotated[Decimal, classified("confidential")]
    citation_id: Annotated[UUID, classified("internal")]


class PriorYearFiguresIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[Literal["prior_engagement", "import"], classified("internal")]
    figures: Annotated[
        list[PriorYearFigureIn], Field(max_length=500), classified("confidential")
    ] = []


class PriorYearFiguresOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: Annotated[int, Field(ge=0), classified("internal")]


# --- SSARS ---------------------------------------------------------------------------------------


class RailRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[
        Literal["inquiries", "analytics", "read_fs", "fs", "report", "approval"],
        classified("internal"),
    ]
    label: Annotated[str, classified("internal")]
    state: Annotated[str, classified("internal")]  # a status word from the registry


class InquirySummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    answered: Annotated[int, Field(ge=0), classified("internal")]
    open: Annotated[int, Field(ge=0), classified("internal")]
    questionnaire_id: Annotated[UUID | None, classified("internal")]


class SsarsWorkspaceOut(BaseModel):
    """AUD-26: the mode from the engagement type (read-only), its rail and summaries."""

    model_config = ConfigDict(frozen=True)

    mode: Annotated[SsarsMode, classified("internal")]
    standard: Annotated[Literal["AR-C 90", "AR-C 80", "AR-C 70"], classified("internal")]
    rail: Annotated[list[RailRowOut], classified("internal")]
    analytics_set_id: Annotated[UUID | None, classified("internal")]
    inquiries: Annotated[InquirySummaryOut | None, classified("internal")]
    legend: Annotated[str | None, classified("public")]  # "No assurance is provided." (AR-C 70)
    report_available: Annotated[bool, classified("internal")]
    approval_label: Annotated[str | None, classified("confidential")]


class InquiryProgramIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    methodology_program_id: Annotated[UUID, classified("internal")]
    recipient_contact_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=20), classified("internal")
    ]


class InquiryProgramOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    questionnaire_id: Annotated[UUID, classified("internal")]
    questions: Annotated[int, Field(ge=0), classified("internal")]
    published: Annotated[bool, classified("internal")]


class ReminderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_key: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    text: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]


# --- routes --------------------------------------------------------------------------------------

router = AbacusRouter(prefix="/v1", tags=["audit-analytics"])
_WI = "/work-items/{work_item_id}"
_A = "/analytics-sets/{analytics_set_id}"


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str, flag: Flag) -> None:
    if ctx.client:
        raise NotFound("analytics")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


async def _gate_record(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("analytics")
    if not await flag_enabled(ctx.tenant, AUDITS_ANALYTICS):
        raise NotFound(AUDITS_ANALYTICS.name)


@router.post(
    f"{_WI}/analytics-sets",
    action="analytics.run",
    response_model=AnalyticsRunOut,
    status_code=202,
    errors=(409, 501),
)
async def run_analytics(
    work_item_id: UUID, body: AnalyticsRunIn, ctx: Ctx, _key: IdempotencyKey
) -> AnalyticsRunOut:
    """202: `FluxAnalyticsWorkflow`; a recompute is a new version, never an edit."""
    await _gate(ctx, work_item_id, "analytics.run", AUDITS_ANALYTICS)
    raise NotImplementedYet("A-08-T21")


@router.get(_A, action="analytics.read", response_model=AnalyticsSetOut, errors=(501,))
async def get_analytics_set(analytics_set_id: UUID, ctx: Ctx) -> AnalyticsSetOut:
    await _gate_record(ctx)
    raise NotImplementedYet("A-08-T21")


@router.get(
    f"{_A}/lines/{{position}}/provenance",
    action="analytics.read",
    response_model=ProvenanceOut,
    errors=(501,),
)
async def line_provenance(analytics_set_id: UUID, position: int, ctx: Ctx) -> ProvenanceOut:
    await _gate_record(ctx)
    raise NotImplementedYet("A-08-T21")


@router.put(
    f"{_A}/lines/{{position}}/explanation",
    action="analytics.explain",
    response_model=AnalyticsLineOut,
    errors=(409, 501),
)
async def put_explanation(
    analytics_set_id: UUID, position: int, body: ExplanationIn, ctx: Ctx
) -> AnalyticsLineOut:
    """422 `explanation_uncited` without a verified citation (INV-2)."""
    await _gate_record(ctx)
    raise NotImplementedYet("A-08-T21")


@router.put(
    f"{_A}/lines/{{position}}/expectation",
    action="analytics.configure",
    response_model=AnalyticsLineOut,
    errors=(409, 501),
)
async def put_expectation(
    analytics_set_id: UUID, position: int, body: ExpectationIn, ctx: Ctx
) -> AnalyticsLineOut:
    await _gate_record(ctx)
    raise NotImplementedYet("A-08-T22")


@router.post(
    f"{_A}/explanations/accept",
    action="analytics.accept",
    response_model=AnalyticsSetOut,
    errors=(409, 501),
)
async def accept_explanations(
    analytics_set_id: UUID, body: AcceptExplanationsIn, ctx: Ctx, _key: IdempotencyKey
) -> AnalyticsSetOut:
    """SHL-10; the acceptor is never the explanation's author (I-SEGREGATION)."""
    await _gate_record(ctx)
    raise NotImplementedYet("A-08-T21")


@router.post(
    f"{_A}/client-questions",
    action="client_question.send",
    response_model=ClientQuestionsOut,
    status_code=201,
    errors=(409, 501),
)
async def send_client_questions(
    analytics_set_id: UUID, body: ClientQuestionsIn, ctx: Ctx, _key: IdempotencyKey
) -> ClientQuestionsOut:
    """A T-02 questionnaire to POR-05 from firm templates a person edited; a person sends."""
    await _gate_record(ctx)
    raise NotImplementedYet("A-08-T21")


@router.get(f"{_A}/export.xlsx", action="analytics.export", response_model=bytes, errors=(501,))
async def export_analytics(analytics_set_id: UUID, ctx: Ctx) -> Response:
    await _gate_record(ctx)
    raise NotImplementedYet("A-08-T21")


@router.put(
    f"{_WI}/prior-year-figures",
    action="analytics.configure",
    response_model=PriorYearFiguresOut,
    errors=(409, 501),
)
async def put_prior_year_figures(
    work_item_id: UUID, body: PriorYearFiguresIn, ctx: Ctx
) -> PriorYearFiguresOut:
    await _gate(ctx, work_item_id, "analytics.configure", AUDITS_ANALYTICS)
    raise NotImplementedYet("A-08-T21")


@router.get(f"{_WI}/ssars", action="ssars.read", response_model=SsarsWorkspaceOut, errors=(501,))
async def ssars_workspace(work_item_id: UUID, ctx: Ctx) -> SsarsWorkspaceOut:
    await _gate(ctx, work_item_id, "ssars.read", AUDITS_SSARS_WORKSPACE)
    raise NotImplementedYet("A-08-T22")


@router.post(
    f"{_WI}/ssars/inquiries",
    action="ssars.inquiry_manage",
    response_model=InquiryProgramOut,
    status_code=201,
    errors=(409, 501),
)
async def build_inquiries(
    work_item_id: UUID, body: InquiryProgramIn, ctx: Ctx, _key: IdempotencyKey
) -> InquiryProgramOut:
    """The inquiry program from methodology content to a questionnaire."""
    await _gate(ctx, work_item_id, "ssars.inquiry_manage", AUDITS_SSARS_WORKSPACE)
    raise NotImplementedYet("A-08-T22")


@router.post(
    f"{_WI}/ssars/publish",
    action="ssars.inquiry_manage",
    response_model=InquiryProgramOut,
    errors=(409, 501),
)
async def publish_inquiries(
    work_item_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> InquiryProgramOut:
    await _gate(ctx, work_item_id, "ssars.inquiry_manage", AUDITS_SSARS_WORKSPACE)
    raise NotImplementedYet("A-08-T22")


@router.post(
    f"{_WI}/ssars/remind",
    action="client_question.send",
    response_model=ClientQuestionsOut,
    errors=(409, 501),
)
async def remind(
    work_item_id: UUID, body: ReminderIn, ctx: Ctx, _key: IdempotencyKey
) -> ClientQuestionsOut:
    """A templated reminder a person edits and sends (DV-4)."""
    await _gate(ctx, work_item_id, "client_question.send", AUDITS_SSARS_WORKSPACE)
    raise NotImplementedYet("A-08-T22")
