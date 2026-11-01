"""The A-04 audit planning contract stub (A-04-T01; TASK-2707; DEC-1757).
Contract: `docs/contracts/audit-planning.md`; screens AUD-05, AUD-07, AUD-08, AUD-09 and AUD-10.

Materiality, the risk register and linkage, the fraud brainstorm, internal control and exceptions,
service organizations and SOC 1 evaluations. Every route is under `/v1/engagements/{eid}`, has one
matrix action and answers, in order: a client principal 404 (INV-4: no portal or API scope admits
an A-04 table, and the crawler finds none of these figures); the action on the engagement (walls
404, independence 403); 404 with its flag off; then 501 `not_implemented` until its task.

- `assurance.materiality`: `/materiality/current`, `/preview`, `/proposals`, `/reassessments`
  (live with A-04-T12).
- `assurance.risk_register`: `/risks/register`, `/risks/linkage`, `/risks/{rid}*`, `/fraud-*`
  (T13, T18, T19).
- `assurance.internal_control`: `/internal-control/*` (T25, T31).
- `assurance.service_orgs`: `/soc-reports/*`; `/service-organizations*` answers with it or
  `workpapers.core` on (T07, T31).

The live SPEC-300 routes in `fieldwork` (`GET` and `PUT /materiality`, `/materiality/versions`,
`/materiality/decide`, `GET` and `POST /risks`, `/risks/{id}/versions`, `/risks/{id}/approve`)
stay on their paths, unflagged; A-04's reads take paths no live route already holds (DEC-1757).

Every figure is computed by code (ADR-050) and sent as a decimal string with `engine_version` and
`inputs_hash`; the browser does no arithmetic. The agent proposes; deciding materiality, the
register, minutes and reliance are a named person's acts through C3 (INV-1). The examples are
Brightwater Hale's Northwind Robotics 401(k) Plan, PY2025, and foot: 16,812,400 x 1.5% = 252,186,
rounded to the nearest 100 half up = 252,200; PM 75% = 189,150; CT 5% = 12,610 (AC3.1).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from abacus.kernel._flags import (
    ASSURANCE_INTERNAL_CONTROL,
    ASSURANCE_MATERIALITY,
    ASSURANCE_RISK_REGISTER,
    ASSURANCE_SERVICE_ORGS,
    WORKPAPERS_CORE,
    WORKPAPERS_DRAFTING,
)
from abacus.kernel._statuses import (
    ControlDesignStatus,
    ControlExceptionDispositionStatus,
    CuecStatus,
    DeficiencySeverityStatus,
    FraudInquiryStatus,
    FraudMinutesStatus,
    MaterialityVersionStatus,
    RiskFraudStatus,
    RiskLinkageStatus,
    RiskRegisterRowStatus,
    RiskSignificanceStatus,
    ServiceOrganizationStatus,
    SocRelianceStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.clock import system_now
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.engagements.api import assurance_item_id, get_ref
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    allowed_actions,
    authorise,
    current_context,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from abacus.modules.assurance.compute.materiality import Option as MaterialityOption
    from abacus.modules.assurance.compute.materiality import Thresholds as MaterialityThresholds
    from abacus.modules.assurance.materiality import MaterialityVersion as MaterialityVersionRow
    from abacus.modules.assurance.risks import RiskRow as RiskRowModel
    from abacus.modules.assurance.service_orgs import ServiceOrganization as ServiceOrganizationRow

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Money = Annotated[Decimal, classified("confidential")]
Pct = Annotated[
    Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4), classified("internal")
]
Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
Basis = Literal["unadjusted", "final"]
BenchmarkUse = Literal["overall", "specific", "considered_for_specific", "not_used"]
Rating = Literal["low", "moderate", "high"]
ControlRating = Literal["low", "moderate", "high", "max"]
Assertion = Literal[
    "existence", "occurrence", "completeness", "rights_obligations", "accuracy", "valuation",
    "cutoff", "classification", "presentation",
]  # fmt: skip
CosoComponent = Literal[
    "control_environment", "risk_assessment", "control_activities", "information_communication",
    "monitoring",
]  # fmt: skip
Proposable = Literal["deficiency", "significant_deficiency", "material_weakness"]
# The person's controls on the record; the screen shows only these.
PlanningAction = Literal[
    "materiality.propose",
    "materiality.reassess",
    "decision.decide",
    "decision.notify",  # Remind (C3 `/v1/decision-cards/{card_id}/notify`)
    "risk.edit",
    "risk.link",
    "risk.route_for_approval",
    "fraud_session.edit",
    "fraud_minutes.approve",
    "control.edit",
    "deficiency.propose_severity",
    "exception.route",
    "service_org.edit",
    "soc_report.evaluate",
    "workpaper.draft",
]
Actions = Annotated[list[PlanningAction], classified("internal")]


class EngineStamp(BaseModel):
    """Which code computed a figure from which inputs (ADR-050)."""

    model_config = ConfigDict(frozen=True)

    engine_name: Annotated[str, classified("internal")]
    engine_version: Annotated[str, classified("internal")]
    inputs_hash: Hash
    computed_at: Annotated[datetime, classified("internal")]


# --- materiality (AUD-07; T08, T12) -------------------------------------------------------------

_NORTHWIND_THRESHOLDS: JsonDict = {
    "basis": "unadjusted",
    "benchmark_key": "net_assets",
    "benchmark_amount": "16812400.00",
    "rate_pct": "1.5000",
    "overall": "252200.00",
    "pm_pct": "75.0000",
    "pm": "189150.00",
    "ct_pct": "5.0000",
    "ct": "12610.00",
    "policy_low_pct": "1.0000",
    "policy_high_pct": "2.0000",
    "stamp": {
        "engine_name": "materiality",
        "engine_version": "1",
        "inputs_hash": "0" * 64,
        "computed_at": "2026-09-14T09:27:00-05:00",
    },
}


class PriorYearOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    year: Annotated[str, classified("internal")]  # "PY2024"
    amount: Money
    # The final, audited overall for that year and the rate it was set at (A-04-T10, R2's
    # "Overall materiality used: PY2024 1.5% = 213,400").
    overall_used: Annotated[Decimal | None, classified("confidential")]
    rate_used_pct: Annotated[Decimal | None, classified("confidential")] = None


class BenchmarkOut(BaseModel):
    """A statement-grammar row: amounts with no "$" (AUD-07 a; R2 prior years)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    amount: Money
    range_low_pct: Pct
    range_high_pct: Pct
    low: Money
    high: Money
    use: Annotated[BenchmarkUse, classified("internal")]
    prior_years: Annotated[list[PriorYearOut], Field(max_length=5), classified("confidential")]
    growth_pct: Annotated[Decimal | None, classified("confidential")]  # vs the first prior year


class ThresholdsOut(BaseModel):
    """Overall, PM and CT from code; PM and CT from the rounded overall (AC3.1, AC3.3)."""

    model_config = ConfigDict(frozen=True, json_schema_extra={"examples": [_NORTHWIND_THRESHOLDS]})

    basis: Annotated[Basis, classified("internal")]
    benchmark_key: Annotated[str, classified("internal")]
    benchmark_amount: Money
    rate_pct: Pct
    overall: Money
    pm_pct: Pct
    pm: Money
    ct_pct: Pct
    ct: Money
    policy_low_pct: Pct
    policy_high_pct: Pct
    stamp: Annotated[EngineStamp, classified("internal")]


class OptionOut(BaseModel):
    """A card option; `recommended` marks the agent's tag, never a choice (INV-1)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]  # "rate_1_0", "rate_1_5", "custom"
    thresholds: Annotated[ThresholdsOut | None, classified("confidential")]  # null for "custom"
    recommended: Annotated[bool, classified("internal")]


class QualitativeFactorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: Annotated[str, classified("confidential")]
    applies: Annotated[bool, classified("internal")]
    citation_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")]


class ReassessmentOut(BaseModel):
    """The final-basis comparison by code (AUD-07 d: 16,861,000 x 1.5% = 252,900; +700, 0.3%)."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "final_amount": "16861000.00",
                    "at_rate": "252900.00",
                    "difference": "700.00",
                    "difference_pct": "0.3",
                    "conclusion": "no_change",
                }
            ]
        },
    )

    final_amount: Money
    at_rate: Money
    difference: Money
    difference_pct: Annotated[Decimal, classified("confidential")]
    conclusion: Annotated[Literal["no_change", "revised"] | None, classified("internal")]


class ImpactOut(BaseModel):
    """A workpaper to re-run after a revision, computed by code (AUD-07 e)."""

    model_config = ConfigDict(frozen=True)

    workpaper_code: Annotated[str, classified("internal")]
    title: Annotated[str, classified("internal")]
    reason: Annotated[Literal["cites_materiality", "depends_on_step"], classified("internal")]
    preparer_name: Annotated[str | None, classified("internal")]


class PlanningMaterialityVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    status: Annotated[MaterialityVersionStatus, classified("internal")]
    current: Annotated[bool, classified("internal")]
    superseded: Annotated[bool, classified("internal")]
    thresholds: Annotated[ThresholdsOut, classified("confidential")]
    decision_card_id: Annotated[UUID | None, classified("internal")]
    decision_id: Annotated[UUID | None, classified("internal")]
    reassessment: Annotated[ReassessmentOut | None, classified("confidential")]
    impact: Annotated[list[ImpactOut], Field(max_length=200), classified("internal")]
    # "Marcus Delaney via Agent" for a proposal the agent prepared (INV-5).
    created_by_name: Annotated[str, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class MaterialityRecordOut(BaseModel):
    """`GET …/materiality/current`: the A-04 record AUD-07 renders (T12)."""

    model_config = ConfigDict(frozen=True)

    current: Annotated[PlanningMaterialityVersionOut | None, classified("confidential")]
    versions: Annotated[list[PlanningMaterialityVersionOut], classified("confidential")]
    benchmarks: Annotated[list[BenchmarkOut], classified("confidential")]
    qualitative_factors: Annotated[list[QualitativeFactorOut], classified("confidential")]
    policy_version_id: Annotated[UUID | None, classified("internal")]
    pending_card_id: Annotated[UUID | None, classified("internal")]
    allowed_actions: Actions
    # A-04-T10 (DEC-1851), additive: the benchmarks' period end ("unadjusted at 12/31/2025"), the
    # caption's sentences under the table and the specific-materiality line, each written by the
    # service from code facts (the TB lines it read, the prior years); never model text.
    period_end: Annotated[date | None, classified("internal")] = None
    benchmark_caption: Annotated[list[str], Field(max_length=4), classified("confidential")] = (
        Field(default_factory=list)
    )
    specific_note: Annotated[str | None, classified("confidential")] = None


class MaterialityPreviewIn(BaseModel):
    """The slider and steppers: thresholds from code, inside the K-02 policy (AC3.3)."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"benchmark_key": "net_assets", "rate_pct": "1.5", "pm_pct": "75", "ct_pct": "5"}
            ]
        },
    )

    basis: Annotated[Basis, classified("internal")] = "unadjusted"
    benchmark_key: Annotated[str, Field(pattern=r"^[a-z_]{1,64}$"), classified("internal")]
    rate_pct: Pct
    pm_pct: Pct
    ct_pct: Pct


class MaterialityProposalIn(BaseModel):
    """`tb_snapshot_id` names the engagement's trial balance (C9) read at the Unadjusted layer.
    `rate_pct` adds a rate the proposer typed, inside the firm range, as a third option (A-04-T12,
    DEC-1950: the card's options are fixed when it is raised)."""

    model_config = ConfigDict(extra="forbid")

    tb_snapshot_id: Annotated[UUID, classified("internal")]
    benchmark_key: Annotated[str, Field(pattern=r"^[a-z_]{1,64}$"), classified("internal")]
    recommend: Annotated[bool, classified("internal")] = False  # a recommendation run, if allowed
    rate_pct: Pct | None = None


class MaterialityProposalOut(BaseModel):
    """The proposed version and its `planning_materiality` card (reserved to the EP)."""

    model_config = ConfigDict(frozen=True)

    version: Annotated[PlanningMaterialityVersionOut, classified("confidential")]
    decision_card_id: Annotated[UUID, classified("internal")]
    options: Annotated[list[OptionOut], classified("confidential")]


class ReassessmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tb_snapshot_id: Annotated[UUID, classified("internal")]  # the Final layer


class ReassessmentRaisedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_card_id: Annotated[UUID, classified("internal")]
    reassessment: Annotated[ReassessmentOut, classified("confidential")]


# --- the risk register and linkage (AUD-08; T13, T18) --------------------------------------------


class InherentFactorOut(BaseModel):
    """A SAS 145 inherent risk factor and its rating."""

    model_config = ConfigDict(frozen=True)

    factor: Annotated[
        Literal["susceptibility_to_fraud", "change", "complexity", "subjectivity", "uncertainty"],
        classified("internal"),
    ]
    rating: Annotated[Rating, classified("internal")]


class RegisterRiskOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    code: Annotated[str, Field(pattern=r"^R[0-9]{1,3}$"), classified("internal")]
    level: Annotated[Literal["financial_statement", "assertion"], classified("internal")]
    area_key: Annotated[str, classified("internal")]
    area_label: Annotated[str, classified("internal")]
    assertions: Annotated[list[Assertion], classified("internal")]
    inherent_risk: Annotated[Rating, classified("internal")]
    control_risk: Annotated[ControlRating, classified("internal")]
    rmm: Annotated[Rating, classified("internal")]  # by code from the firm's rmm_matrix
    rmm_policy_version_id: Annotated[UUID | None, classified("internal")]
    significance: Annotated[RiskSignificanceStatus, classified("internal")]
    fraud: Annotated[RiskFraudStatus, classified("internal")]
    presumption_kind: Annotated[
        Literal["none", "management_override", "revenue_recognition"], classified("internal")
    ]
    inherent_factors: Annotated[list[InherentFactorOut], classified("internal")]
    status: Annotated[RiskRegisterRowStatus, classified("internal")]
    unaddressed: Annotated[bool, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    content_hash: Hash
    allowed_actions: Actions


class TallyOut(BaseModel):
    """Counted from the rows by code (AC4.1: 10 · 2 (+1 proposed) · 2 · 3 · 1 · Pending)."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "risks": 10,
                    "significant": 2,
                    "significant_proposed": 1,
                    "fraud": 2,
                    "high_rmm": 3,
                    "unaddressed": 1,
                    "ep_approval": "pending",
                }
            ]
        },
    )

    risks: Annotated[int, Field(ge=0), classified("internal")]
    significant: Annotated[int, Field(ge=0), classified("internal")]
    significant_proposed: Annotated[int, Field(ge=0), classified("internal")]
    fraud: Annotated[int, Field(ge=0), classified("internal")]
    high_rmm: Annotated[int, Field(ge=0), classified("internal")]
    unaddressed: Annotated[int, Field(ge=0), classified("internal")]
    ep_approval: Annotated[Literal["pending", "approved", "changed"], classified("internal")]


class RegisterOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tally: Annotated[TallyOut, classified("internal")]
    risks: Annotated[list[RegisterRiskOut], classified("confidential")]
    register_hash: Hash
    approved_card_id: Annotated[UUID | None, classified("internal")]
    allowed_actions: Actions


class RiskVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, Field(ge=1), classified("internal")]
    at: Annotated[datetime, classified("internal")]
    by_name: Annotated[str, classified("internal")]  # "Marcus Delaney via Agent" (INV-5)


class RiskDrawerOut(BaseModel):
    """The O2 drawer `?ov=risk:<code>`: factors, rationale, citations and versions (AUD-08 b)."""

    model_config = ConfigDict(frozen=True)

    risk: Annotated[RegisterRiskOut, classified("confidential")]
    rationale: Annotated[str | None, Field(max_length=20_000), classified("confidential")]
    rationale_suggestion_id: Annotated[UUID | None, classified("internal")]
    citation_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")]
    versions: Annotated[list[RiskVersionOut], classified("internal")]
    routed_to_name: Annotated[str | None, classified("internal")]
    routed_at: Annotated[datetime | None, classified("internal")]


class RiskCreateIn(BaseModel):
    """A new risk (A-04-T13, additive): its code is the next one, RMM is the firm matrix's."""

    model_config = ConfigDict(extra="forbid")

    level: Annotated[Literal["financial_statement", "assertion"], classified("internal")]
    area_label: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    assertions: Annotated[list[Assertion], Field(max_length=12), classified("internal")]
    inherent_risk: Annotated[Rating, classified("internal")]
    control_risk: Annotated[ControlRating, classified("internal")]
    presumption_kind: Annotated[
        Literal["none", "management_override", "revenue_recognition"], classified("internal")
    ] = "none"
    inherent_factors: Annotated[
        list[InherentFactorOut], Field(max_length=5), classified("internal")
    ] = Field(default_factory=list)
    rationale: Annotated[str | None, Field(max_length=4_000), classified("confidential")] = None


class RiskEditIn(BaseModel):
    """Field edits through `review.api.record_value`; a rebuttal of management override is 422
    `presumption_not_rebuttable` (AC4.5)."""

    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=1), classified("internal")]
    assertions: Annotated[list[Assertion] | None, classified("internal")] = None
    inherent_risk: Annotated[Rating | None, classified("internal")] = None
    control_risk: Annotated[ControlRating | None, classified("internal")] = None
    inherent_factors: Annotated[list[InherentFactorOut] | None, classified("internal")] = None
    rationale: Annotated[str | None, Field(max_length=20_000), classified("confidential")] = None
    significance: Annotated[
        Literal["proposed", "not_significant"] | None, classified("internal")
    ] = None
    fraud: Annotated[Literal["rebuttal_proposed"] | None, classified("internal")] = None
    reason: Annotated[
        str | None, Field(min_length=1, max_length=2_000), classified("confidential")
    ] = None


class LinkTargetOut(BaseModel):
    """A response column; `registered: false` renders a planned link, never a dead click."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["program_step", "workpaper", "procedure"], classified("internal")]
    ref: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    registered: Annotated[bool, classified("internal")]


class LinkCellOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    risk_code: Annotated[str, classified("internal")]
    target_ref: Annotated[str, classified("internal")]
    state: Annotated[RiskLinkageStatus, classified("internal")]


class LinkageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    risk_codes: Annotated[list[str], classified("internal")]
    targets: Annotated[list[LinkTargetOut], classified("internal")]
    cells: Annotated[list[LinkCellOut], classified("internal")]


class ResponseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_kind: Annotated[
        Literal["program_step", "workpaper", "procedure"], classified("internal")
    ]
    target_ref: Annotated[str, Field(min_length=1, max_length=128), classified("internal")]


class ApprovalRequestOut(BaseModel):
    """One `significant_risk` card over every pending significance and rebuttal proposal."""

    model_config = ConfigDict(frozen=True)

    decision_card_id: Annotated[UUID, classified("internal")]
    subject_codes: Annotated[list[str], Field(min_length=1), classified("internal")]


class CoverageOut(BaseModel):
    """Material areas from C9 mapping against assessed risks, by code (AC4.7: 10 of 10, R8)."""

    model_config = ConfigDict(frozen=True)

    material_areas: Annotated[int, Field(ge=0), classified("internal")]
    covered: Annotated[int, Field(ge=0), classified("internal")]
    unaddressed_codes: Annotated[list[str], classified("internal")]
    wording_run_id: Annotated[UUID | None, classified("internal")]  # only with workpapers.drafting


class RiskDraftIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: Annotated[
        list[Literal["rationale", "assertions", "response"]],
        Field(min_length=1),
        classified("internal"),
    ]


class RunStartedOut(BaseModel):
    """202: suggestions arrive pending; nothing changes until a person adopts (AC4.7)."""

    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]
    status: Annotated[Literal["queued"], classified("internal")] = "queued"


# --- the fraud brainstorm (AUD-05 b; T19) --------------------------------------------------------


class AttendeeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    initials: Annotated[str, classified("internal")]


class ExclusionOut(BaseModel):
    """ "Thomas Whitcombe · excluded (EQR)"."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    reason: Annotated[Literal["eqr", "independence", "other"], classified("internal")]


class DiscussionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_key: Annotated[str, classified("internal")]
    summary: Annotated[str, Field(max_length=5_000), classified("confidential")]


class FraudSessionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    held_at: Annotated[datetime | None, classified("internal")]
    medium: Annotated[Literal["in_person", "video", "call"] | None, classified("internal")]
    led_by: Annotated[AttendeeOut | None, classified("internal")]
    attendees: Annotated[list[AttendeeOut], classified("internal")]
    excluded: Annotated[list[ExclusionOut], classified("internal")]
    discussion: Annotated[list[DiscussionOut], classified("confidential")]
    minutes_text: Annotated[str | None, Field(max_length=50_000), classified("confidential")]
    minutes_hash: Annotated[str | None, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    minutes_status: Annotated[FraudMinutesStatus, classified("internal")]
    minutes_source: Annotated[
        Literal["human", "adopted_suggestion"] | None, classified("internal")
    ]
    approved_by_name: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")]
    row_version: Annotated[int, Field(ge=1), classified("internal")]
    allowed_actions: Actions


class ExclusionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: Annotated[UUID, classified("internal")]
    reason: Annotated[Literal["eqr", "independence", "other"], classified("internal")]


class FraudSessionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=0), classified("internal")]
    held_at: Annotated[datetime | None, classified("internal")] = None
    medium: Annotated[Literal["in_person", "video", "call"] | None, classified("internal")] = None
    led_by_user_id: Annotated[UUID | None, classified("internal")] = None
    attendee_user_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")] = []
    excluded: Annotated[list[ExclusionIn], Field(max_length=20), classified("internal")] = []


class MinutesIn(BaseModel):
    """Minutes written by a person, or a pending suggestion adopted (never both)."""

    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=1), classified("internal")]
    text: Annotated[
        str | None, Field(min_length=1, max_length=50_000), classified("confidential")
    ] = None
    adopt_suggestion_id: Annotated[UUID | None, classified("internal")] = None


class MinutesApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minutes_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


class FraudInquiryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    respondent_name: Annotated[str, classified("confidential")]
    questionnaire_id: Annotated[UUID, classified("internal")]
    sent: Annotated[bool, classified("internal")]  # a draft until a person sends it (AC2.5)
    status: Annotated[FraudInquiryStatus, classified("internal")]
    answered_at: Annotated[datetime | None, classified("internal")]


class FraudInquiryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    respondent_contact_id: Annotated[UUID | None, classified("internal")] = None
    governance_body_ref: Annotated[str | None, Field(max_length=128), classified("internal")] = (
        None
    )
    questionnaire_template_id: Annotated[UUID, classified("internal")]


# --- internal control and exceptions (AUD-09; T25, T31) ------------------------------------------


class ProcessOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    process_name: Annotated[str, classified("confidential")]
    walkthrough_on: Annotated[date | None, classified("internal")]
    design: Annotated[ControlDesignStatus, classified("internal")]
    implementation: Annotated[
        Literal["implemented", "not_implemented", "not_assessed"], classified("internal")
    ]
    reliance: Annotated[Literal["none", "via_soc1", "tested"], classified("internal")]
    service_organization_id: Annotated[UUID | None, classified("internal")]
    row_version: Annotated[int, Field(ge=1), classified("internal")]


class ProcessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=1), classified("internal")]
    design: Annotated[ControlDesignStatus | None, classified("internal")] = None
    implementation: Annotated[
        Literal["implemented", "not_implemented", "not_assessed"] | None, classified("internal")
    ] = None
    reliance: Annotated[Literal["none", "via_soc1", "tested"] | None, classified("internal")] = (
        None
    )
    walkthrough_on: Annotated[date | None, classified("internal")] = None


class ControlExceptionOut(BaseModel):
    """A row of the Exceptions sheet; `address` is "Exceptions!D2". No concluded severity: that is
    A-06's record and reads through it (AC6.3, AC6.7)."""

    model_config = ConfigDict(frozen=True)

    sheet_row: Annotated[int, Field(ge=2), classified("internal")]
    address: Annotated[str, classified("internal")]
    matter: Annotated[str, classified("confidential")]
    description: Annotated[str, classified("confidential")]
    proposed_severity: Annotated[Proposable | None, classified("internal")]
    concluded_severity: Annotated[DeficiencySeverityStatus | None, classified("internal")]
    disposition: Annotated[ControlExceptionDispositionStatus, classified("internal")]
    coso_component: Annotated[CosoComponent, classified("internal")]
    misstatement_candidate_amount: Annotated[Decimal | None, classified("confidential")]
    routed_kind: Annotated[Literal["finding", "misstatement"] | None, classified("internal")]
    routed_ref: Annotated[UUID | None, classified("internal")]
    suggestion_id: Annotated[UUID | None, classified("internal")]
    citation_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")]
    allowed_actions: Actions


class ProposedSeverityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposed_severity: Annotated[Proposable, classified("internal")]
    reason: Annotated[
        str | None, Field(min_length=1, max_length=2_000), classified("confidential")
    ] = None


class RoutedOut(BaseModel):
    """The finding or misstatement candidate and the row's `routed_ref`, in one unit of work."""

    model_config = ConfigDict(frozen=True)

    routed_kind: Annotated[Literal["finding", "misstatement"], classified("internal")]
    routed_ref: Annotated[UUID, classified("internal")]


class RequestDraftOut(BaseModel):
    """A C5 request **draft** (SHL-14 prefill); a person sends it."""

    model_config = ConfigDict(frozen=True)

    draft_id: Annotated[UUID, classified("internal")]
    request_item_ids: Annotated[list[UUID], classified("internal")]


# --- service organizations and SOC 1 (AUD-10; T07, T31) -----------------------------------------


class SubserviceOrgOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("confidential")]
    treatment: Annotated[Literal["carve_out", "inclusive"], classified("internal")]


class ServiceOrganizationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]  # "Keystone Retirement Services"
    services: Annotated[str, classified("confidential")]
    relevant: Annotated[bool, classified("internal")]
    evidence_type: Annotated[
        Literal["soc1_type2", "soc1_type1", "certification", "tested_directly", "none"],
        classified("internal"),
    ]
    status: Annotated[ServiceOrganizationStatus, classified("internal")]
    subservice_orgs: Annotated[list[SubserviceOrgOut], classified("confidential")]
    soc_report_id: Annotated[UUID | None, classified("internal")]
    row_version: Annotated[int, Field(ge=1), classified("internal")]
    allowed_actions: Actions


class ServiceOrganizationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    services: Annotated[str, Field(min_length=1, max_length=1_000), classified("confidential")]
    relevant: Annotated[bool, classified("internal")]
    evidence_type: Annotated[
        Literal["soc1_type2", "soc1_type1", "certification", "tested_directly", "none"],
        classified("internal"),
    ]


class ServiceOrganizationPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=1), classified("internal")]
    services: Annotated[
        str | None, Field(min_length=1, max_length=1_000), classified("confidential")
    ] = None
    relevant: Annotated[bool | None, classified("internal")] = None
    evidence_type: Annotated[
        Literal["soc1_type2", "soc1_type1", "certification", "tested_directly", "none"] | None,
        classified("internal"),
    ] = None


class SocGapOut(BaseModel):
    """The uncovered period by code from the adopted period (AC7.1: Oct 1 to Dec 31, 2025, 92)."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {"start": "2025-10-01", "end": "2025-12-31", "days": 92, "bridged": False}
            ]
        },
    )

    start: Annotated[date | None, classified("internal")]
    end: Annotated[date | None, classified("internal")]
    days: Annotated[int, Field(ge=0), classified("internal")]
    bridged: Annotated[bool, classified("internal")]  # a bridge letter received
    stamp: Annotated[EngineStamp | None, classified("internal")] = None


class SocExceptionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    co_ref: Annotated[str, classified("internal")]
    description: Annotated[str, classified("confidential")]
    impact: Annotated[Literal["low", "high"], classified("internal")]
    impact_rationale: Annotated[str | None, classified("confidential")]
    routed_ref: Annotated[UUID | None, classified("internal")]


class CuecOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    n: Annotated[int, Field(ge=1), classified("internal")]
    text: Annotated[str, classified("confidential")]
    control_activity_id: Annotated[UUID | None, classified("internal")]
    status: Annotated[CuecStatus, classified("internal")]
    page_citation_id: Annotated[UUID | None, classified("internal")]


class SocReportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    service_organization_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    service_auditor_name: Annotated[str | None, classified("confidential")]
    report_type: Annotated[Literal["type_1", "type_2"] | None, classified("internal")]
    opinion: Annotated[
        Literal["unmodified", "qualified", "adverse", "disclaimer"] | None, classified("internal")
    ]
    period_start: Annotated[date | None, classified("internal")]
    period_end: Annotated[date | None, classified("internal")]
    report_date: Annotated[date | None, classified("internal")]
    objectives_total: Annotated[int | None, Field(ge=0), classified("internal")]
    objectives_relevant: Annotated[int | None, Field(ge=0), classified("internal")]
    gap: Annotated[SocGapOut, classified("internal")]
    exceptions: Annotated[list[SocExceptionOut], classified("confidential")]
    cuecs: Annotated[list[CuecOut], classified("confidential")]
    cuecs_evidenced: Annotated[int, Field(ge=0), classified("internal")]
    reliance_state: Annotated[SocRelianceStatus, classified("internal")]
    reliance_card_id: Annotated[UUID | None, classified("internal")]
    row_version: Annotated[int, Field(ge=1), classified("internal")]
    allowed_actions: Actions


class SocReportPatchIn(BaseModel):
    """Adopt the evaluation's facts; the gap is recomputed by code, never read from model text."""

    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=1), classified("internal")]
    report_type: Annotated[Literal["type_1", "type_2"] | None, classified("internal")] = None
    opinion: Annotated[
        Literal["unmodified", "qualified", "adverse", "disclaimer"] | None, classified("internal")
    ] = None
    period_start: Annotated[date | None, classified("internal")] = None
    period_end: Annotated[date | None, classified("internal")] = None
    report_date: Annotated[date | None, classified("internal")] = None


class CuecPatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: Annotated[int, Field(ge=1), classified("internal")]
    control_activity_id: Annotated[UUID | None, classified("internal")] = None
    evidence_version_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")] = []


class SocRequestsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Annotated[Literal["bridge_letter", "cuec_evidence"], classified("internal")]
    cuec_ns: Annotated[list[int], Field(max_length=50), classified("internal")] = []


class RelianceRequestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_card_id: Annotated[UUID, classified("internal")]


# --- the gate and the routes ---------------------------------------------------------------------


async def _gate(
    ctx: AuthContext, engagement_id: UUID, action: str, *flags: Flag, any_of: bool = False
) -> None:
    """Client 404; the action on the engagement; the flags (all of them, or any with any_of)."""
    if ctx.client:
        raise NotFound("audit planning")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    states = [await flag_enabled(ctx.tenant, f) for f in flags]
    if not (any(states) if any_of else all(states)):
        raise NotFound(flags[0].name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


async def _org_actions(ctx: AuthContext, engagement_id: UUID) -> list[PlanningAction]:
    ref = await get_ref(ctx, engagement_id)
    can = await allowed_actions(ctx, ref.resource(), ("service_org.edit",))
    return ["service_org.edit"] if "service_org.edit" in can else []


def _org_out(o: ServiceOrganizationRow, actions: list[PlanningAction]) -> ServiceOrganizationOut:
    """A row as AUD-04 and AUD-10 read it; the edit actions are the reader's (A-04-T07)."""
    return ServiceOrganizationOut(
        id=o.id,
        name=o.name,
        services=o.services,
        relevant=o.relevant,
        evidence_type=cast(
            Literal["soc1_type2", "soc1_type1", "certification", "tested_directly", "none"],
            o.evidence_type,
        ),
        status=cast(ServiceOrganizationStatus, o.status),
        subservice_orgs=[
            SubserviceOrgOut(
                name=str(s["name"]),
                treatment=cast(Literal["carve_out", "inclusive"], s["treatment"]),
            )
            for s in o.subservice_orgs
        ],
        soc_report_id=o.soc_report_id,
        row_version=o.row_version,
        allowed_actions=actions,
    )


router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["assurance"])
_RR = ASSURANCE_RISK_REGISTER
_IC = ASSURANCE_INTERNAL_CONTROL
_SO = ASSURANCE_SERVICE_ORGS
_MAT = ASSURANCE_MATERIALITY


def _thresholds_out(t: MaterialityThresholds, computed_at: datetime) -> ThresholdsOut:
    return ThresholdsOut(
        basis=t.basis,
        benchmark_key=t.benchmark_key,
        benchmark_amount=t.benchmark_amount,
        rate_pct=t.rate_pct,
        overall=t.overall,
        pm_pct=t.pm_pct,
        pm=t.pm,
        ct_pct=t.ct_pct,
        ct=t.ct,
        policy_low_pct=t.policy_low_pct,
        policy_high_pct=t.policy_high_pct,
        stamp=EngineStamp(
            engine_name=t.stamp.engine_name,
            engine_version=t.stamp.engine_version,
            inputs_hash=t.stamp.inputs_hash,
            computed_at=computed_at,
        ),
    )


def _version_out(
    v: MaterialityVersionRow, newest: UUID | None, names: dict[UUID, str]
) -> PlanningMaterialityVersionOut:
    from abacus.modules.assurance import materiality

    found = v.reassessment
    reassessment = (
        None
        if found is None
        else ReassessmentOut(
            final_amount=Decimal(str(found["final_amount"])),
            at_rate=Decimal(str(found["at_rate"])),
            difference=Decimal(str(found["difference"])),
            difference_pct=Decimal(str(found["difference_pct"])),
            conclusion=cast(Literal["no_change", "revised"] | None, found.get("conclusion")),
        )
    )
    impact = [] if v.impact is None else cast(list[dict[str, object]], v.impact.get("items", []))
    name = names.get(v.created_by_user_id, "")
    return PlanningMaterialityVersionOut(
        version_no=v.version_no,
        status=cast(MaterialityVersionStatus, v.status),
        current=v.id == newest,
        superseded=v.id != newest,
        thresholds=_thresholds_out(materiality.thresholds_of(v), v.computed_at),
        decision_card_id=v.decision_card_id,
        decision_id=v.decision_id,
        reassessment=reassessment,
        impact=[
            ImpactOut(
                workpaper_code=str(i["workpaper_code"]),
                title=str(i["title"]),
                reason=cast(Literal["cites_materiality", "depends_on_step"], i["reason"]),
                preparer_name=names.get(UUID(str(i["preparer_user_id"])))
                if i.get("preparer_user_id")
                else None,
            )
            for i in impact
        ],
        created_by_name=f"{name} via Agent" if v.created_by_kind == "agent" else name,
        created_at=v.created_at,
    )


def _options_out(options: Sequence[MaterialityOption], computed_at: datetime) -> list[OptionOut]:
    return [
        OptionOut(
            key=o.key,
            thresholds=None
            if o.thresholds is None
            else _thresholds_out(o.thresholds, computed_at),
            recommended=False,  # the agent's tag arrives with A-04-T15 (INV-1: never a choice)
        )
        for o in options
    ]


@router.get(
    "/materiality/current",
    action="materiality.read",
    response_model=MaterialityRecordOut,
)
async def materiality_current_route(engagement_id: UUID, ctx: Ctx) -> MaterialityRecordOut:
    """Versions, the current one, benchmarks with prior years, factors, policy range (T12)."""
    await _gate(ctx, engagement_id, "materiality.read", _MAT)
    from abacus.modules.assurance import materiality

    found = await materiality.record(ctx, engagement_id)
    newest = found.versions[-1].id if found.versions else None
    versions = [_version_out(v, newest, found.names) for v in found.versions]
    priors = {p.year: p for p in found.priors}
    return MaterialityRecordOut(
        current=versions[-1] if versions else None,
        versions=versions,
        benchmarks=[
            BenchmarkOut(
                key=b.key,
                label=b.label,
                amount=b.amount,
                range_low_pct=b.range_low_pct,
                range_high_pct=b.range_high_pct,
                low=b.low,
                high=b.high,
                use=cast(BenchmarkUse, b.use),
                prior_years=[
                    PriorYearOut(
                        year=p.year,
                        amount=p.amount,
                        overall_used=p.overall_used,
                        rate_used_pct=priors[p.year].rate_used_pct if p.year in priors else None,
                    )
                    for p in b.prior_years
                ],
                growth_pct=b.growth_pct,
            )
            for b in found.benchmarks
        ],
        qualitative_factors=[],
        policy_version_id=found.policy_version_id,
        pending_card_id=found.pending_card_id,
        allowed_actions=cast(list[PlanningAction], found.actions),
        period_end=found.period_end,
        benchmark_caption=found.caption,
        specific_note=None,
    )


@router.post(
    "/materiality/preview",
    action="materiality.read",
    response_model=ThresholdsOut,
    errors=(409,),
)
async def materiality_preview_route(
    engagement_id: UUID, body: MaterialityPreviewIn, ctx: Ctx
) -> ThresholdsOut:
    """Thresholds by code for the slider and steppers; writes nothing; 409 `outside_policy`
    outside the K-02 range (T08, T12)."""
    await _gate(ctx, engagement_id, "materiality.read", _MAT)
    from abacus.modules.assurance import materiality

    found = await materiality.preview(
        ctx,
        engagement_id,
        basis=body.basis,
        key=body.benchmark_key,
        rate_pct=body.rate_pct,
        pm_pct=body.pm_pct,
        ct_pct=body.ct_pct,
    )
    return _thresholds_out(found, system_now())


@router.post(
    "/materiality/proposals",
    action="materiality.propose",
    response_model=MaterialityProposalOut,
    status_code=201,
    errors=(409,),
)
async def materiality_proposal_route(
    engagement_id: UUID, body: MaterialityProposalIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MaterialityProposalOut:
    """Compute the options and raise the `planning_materiality` card; the agent's recommendation
    is a tag on an option, never a choice (T12, T15). 409 `proposal_pending`."""
    await _gate(ctx, engagement_id, "materiality.propose", _MAT)
    from abacus.modules.assurance import materiality

    found = await materiality.propose(
        ctx,
        engagement_id,
        tb_id=body.tb_snapshot_id,
        key=body.benchmark_key,
        rate_pct=body.rate_pct,
    )
    record = await materiality.record(ctx, engagement_id)
    newest = record.versions[-1].id if record.versions else None
    return MaterialityProposalOut(
        version=_version_out(found.version, newest, record.names),
        decision_card_id=found.card_id,
        options=_options_out(found.options, found.version.computed_at),
    )


@router.post(
    "/materiality/reassessments",
    action="materiality.reassess",
    response_model=ReassessmentRaisedOut,
    status_code=201,
    errors=(409,),
)
async def materiality_reassess_route(
    engagement_id: UUID, body: ReassessmentIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ReassessmentRaisedOut:
    """Final-basis compute and the reassessment card: No change or Revise (AC3.6, AC3.7; T12);
    409 `nothing_decided`, `proposal_pending`, `layer_unavailable` before an adjustment source."""
    await _gate(ctx, engagement_id, "materiality.reassess", _MAT)
    from abacus.modules.assurance import materiality

    found = await materiality.reassess(ctx, engagement_id, tb_id=body.tb_snapshot_id)
    r = found.reassessment
    return ReassessmentRaisedOut(
        decision_card_id=found.card_id,
        reassessment=ReassessmentOut(
            final_amount=r.final_amount,
            at_rate=r.at_rate,
            difference=r.difference,
            difference_pct=r.difference_pct,
            conclusion=None,
        ),
    )


def _risk_out(r: RiskRowModel, linked: bool, actions: list[str]) -> RegisterRiskOut:
    return RegisterRiskOut(
        id=r.id,
        code=r.code,
        level=cast(Literal["financial_statement", "assertion"], r.level),
        area_key=r.area_key,
        area_label=r.area_label,
        assertions=cast(list[Assertion], list(r.assertions)),
        inherent_risk=cast(Rating, r.inherent_risk),
        control_risk=cast(ControlRating, r.control_risk),
        rmm=cast(Rating, r.rmm),
        rmm_policy_version_id=r.rmm_policy_version_id,
        significance=cast(RiskSignificanceStatus, r.significance),
        fraud=cast(RiskFraudStatus, r.fraud),
        presumption_kind=cast(
            Literal["none", "management_override", "revenue_recognition"], r.presumption_kind
        ),
        inherent_factors=[
            InherentFactorOut.model_validate({"factor": f["factor"], "rating": f["rating"]})
            for f in r.inherent_factors
        ],
        status=cast(RiskRegisterRowStatus, r.status),
        unaddressed=not linked,
        version_no=r.version_no,
        content_hash=r.content_hash,
        allowed_actions=cast(list[PlanningAction], actions),
    )


async def _drawer_out(ctx: AuthContext, engagement_id: UUID, risk_id: UUID) -> RiskDrawerOut:
    from abacus.modules.assurance import risks

    found = await risks.drawer(ctx, engagement_id, risk_id)
    return RiskDrawerOut(
        risk=_risk_out(found.risk, found.linked, found.actions),
        rationale=found.risk.rationale,
        rationale_suggestion_id=found.rationale_suggestion_id,
        citation_ids=list(found.citation_ids),
        versions=[
            RiskVersionOut(version_no=v.version_no, at=v.at, by_name=v.by_name)
            for v in found.versions
        ],
        routed_to_name=None,  # the significant_risk card (A-04-T18)
        routed_at=None,
    )


async def _linkage_out(ctx: AuthContext, engagement_id: UUID) -> LinkageOut:
    from abacus.modules.assurance import risks

    found = await risks.linkage(ctx, engagement_id)
    return LinkageOut(
        risk_codes=found.codes,
        targets=[
            LinkTargetOut(
                kind=cast(Literal["program_step", "workpaper", "procedure"], t.kind),
                ref=t.ref,
                label=t.label,
                registered=t.registered,
            )
            for t in found.targets
        ],
        cells=[
            LinkCellOut(risk_code=c, target_ref=ref, state=cast(RiskLinkageStatus, st))
            for c, ref, st in found.cells
        ],
    )


@router.get("/risks/register", action="risk.read", response_model=RegisterOut)
async def risk_register_route(engagement_id: UUID, ctx: Ctx) -> RegisterOut:
    """The register with its code tally; no "$" anywhere (AC4.1; T13)."""
    await _gate(ctx, engagement_id, "risk.read", _RR)
    from abacus.modules.assurance import risks

    found = await risks.register(ctx, engagement_id)
    t = found.tally
    return RegisterOut(
        tally=TallyOut(
            risks=t.risks,
            significant=t.significant,
            significant_proposed=t.significant_proposed,
            fraud=t.fraud,
            high_rmm=t.high_rmm,
            unaddressed=t.unaddressed,
            ep_approval=t.ep_approval,
        ),
        risks=[_risk_out(r, r.id in found.linked, found.actions) for r in found.rows],
        register_hash=found.register_hash,
        approved_card_id=next(
            (r.approved_card_id for r in found.rows if r.approved_card_id is not None), None
        ),
        allowed_actions=cast(list[PlanningAction], found.actions),
    )


@router.post(
    "/risks/register",
    action="risk.edit",
    response_model=RiskDrawerOut,
    status_code=201,
    errors=(409,),
)
async def risk_create_route(
    engagement_id: UUID, body: RiskCreateIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RiskDrawerOut:
    """Add a risk: the next code, RMM by code from the firm's matrix; a presumed fraud risk is
    significant by rule (T13). 409 `rmm_matrix_missing`."""
    await _gate(ctx, engagement_id, "risk.edit", _RR)
    from abacus.modules.assurance import risks

    created = await risks.create(
        ctx,
        engagement_id,
        risks.NewRisk(
            level=body.level,
            area_label=body.area_label,
            assertions=body.assertions,
            inherent_risk=body.inherent_risk,
            control_risk=body.control_risk,
            presumption_kind=body.presumption_kind,
            inherent_factors=[(f.factor, f.rating) for f in body.inherent_factors],
            rationale=body.rationale,
        ),
    )
    return await _drawer_out(ctx, engagement_id, created.id)


@router.get("/risks/linkage", action="risk.read", response_model=LinkageOut)
async def risk_linkage_route(engagement_id: UUID, ctx: Ctx) -> LinkageOut:
    """Risks against responses; targets A-05 has not registered are planned (AC4.6; T13)."""
    await _gate(ctx, engagement_id, "risk.read", _RR)
    return await _linkage_out(ctx, engagement_id)


@router.post(
    "/risks/approval-requests",
    action="risk.route_for_approval",
    response_model=ApprovalRequestOut,
    status_code=201,
    errors=(409, 501),
)
async def risk_approval_request_route(
    engagement_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ApprovalRequestOut:
    """One `significant_risk` card over every pending proposal; 409 `nothing_pending` (T18)."""
    await _gate(ctx, engagement_id, "risk.route_for_approval", _RR)
    _not_yet()


@router.post("/risks/coverage", action="risk.read", response_model=CoverageOut)
async def risk_coverage_route(engagement_id: UUID, ctx: Ctx) -> CoverageOut:
    """The coverage check by code; the agent's wording only with `workpapers.drafting` (T13)."""
    await _gate(ctx, engagement_id, "risk.read", _RR)
    from abacus.modules.assurance import materiality, risks

    item = await assurance_item_id(ctx.tenant, engagement_id)
    standing = (
        materiality.in_force(await materiality.versions_of(ctx.tenant, item))
        if item is not None
        else None
    )
    found = await risks.coverage(
        ctx, engagement_id, performance=standing.pm if standing is not None else None
    )
    return CoverageOut(
        material_areas=found.material_areas,
        covered=found.covered,
        unaddressed_codes=found.unaddressed_codes,
        wording_run_id=None,
    )


@router.get("/risks/{risk_id}", action="risk.read", response_model=RiskDrawerOut)
async def risk_drawer_route(engagement_id: UUID, risk_id: UUID, ctx: Ctx) -> RiskDrawerOut:
    """The drawer: SAS 145 factors, rationale, citations, versions (AC4.3; T13)."""
    await _gate(ctx, engagement_id, "risk.read", _RR)
    return await _drawer_out(ctx, engagement_id, risk_id)


@router.patch("/risks/{risk_id}", action="risk.edit", response_model=RiskDrawerOut, errors=(409,))
async def risk_edit_route(
    engagement_id: UUID,
    risk_id: UUID,
    body: RiskEditIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> RiskDrawerOut:
    """Edit fields through `record_value`; RMM recomputed by code; 409 `version_conflict`; 422
    `presumption_not_rebuttable` on management override (AC4.5; T13)."""
    await _gate(ctx, engagement_id, "risk.edit", _RR)
    from abacus.modules.assurance import risks

    await risks.edit(
        ctx,
        engagement_id,
        risk_id,
        risks.Edit(
            assertions=body.assertions,
            inherent_risk=body.inherent_risk,
            control_risk=body.control_risk,
            inherent_factors=None
            if body.inherent_factors is None
            else [(f.factor, f.rating) for f in body.inherent_factors],
            rationale=body.rationale,
            significance=body.significance,
            fraud=body.fraud,
        ),
        expected_version=body.expected_version,
        reason=body.reason,
    )
    return await _drawer_out(ctx, engagement_id, risk_id)


@router.post(
    "/risks/{risk_id}/responses",
    action="risk.link",
    response_model=LinkageOut,
    status_code=201,
    errors=(409,),
)
async def risk_link_route(
    engagement_id: UUID,
    risk_id: UUID,
    body: ResponseIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> LinkageOut:
    """Link a response; 409 `already_linked` (T13)."""
    await _gate(ctx, engagement_id, "risk.link", _RR)
    from abacus.modules.assurance import risks

    await risks.link(
        ctx, engagement_id, risk_id, target_kind=body.target_kind, target_ref=body.target_ref
    )
    return await _linkage_out(ctx, engagement_id)


@router.delete(
    "/risks/{risk_id}/responses", action="risk.link", response_model=LinkageOut, errors=(409,)
)
async def risk_unlink_route(
    engagement_id: UUID,
    risk_id: UUID,
    ctx: Ctx,
    target_kind: Literal["program_step", "workpaper", "procedure"],
    target_ref: Annotated[str, Query(min_length=1, max_length=128)],
) -> LinkageOut:
    """Unlink a response (the linkage row is closed, not deleted); 409 `not_linked` (T13)."""
    await _gate(ctx, engagement_id, "risk.link", _RR)
    from abacus.modules.assurance import risks

    await risks.unlink(ctx, engagement_id, risk_id, target_kind=target_kind, target_ref=target_ref)
    return await _linkage_out(ctx, engagement_id)


@router.post(
    "/risks/{risk_id}/drafts",
    action="workpaper.draft",
    response_model=RunStartedOut,
    status_code=202,
    errors=(409, 501),
)
async def risk_draft_route(
    engagement_id: UUID,
    risk_id: UUID,
    body: RiskDraftIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> RunStartedOut:
    """Single-field Draft with agent: pending suggestions only (AC4.7; T11)."""
    await _gate(ctx, engagement_id, "workpaper.draft", _RR)
    await _gate(ctx, engagement_id, "workpaper.draft", WORKPAPERS_DRAFTING)
    _not_yet()


@router.get(
    "/fraud-brainstorm", action="fraud_session.read", response_model=FraudSessionOut, errors=(501,)
)
async def fraud_session_route(engagement_id: UUID, ctx: Ctx) -> FraudSessionOut:
    """The session: date, medium, leader, attendees and exclusions with reasons (AC2.4; T19)."""
    await _gate(ctx, engagement_id, "fraud_session.read", _RR)
    _not_yet()


@router.put(
    "/fraud-brainstorm",
    action="fraud_session.edit",
    response_model=FraudSessionOut,
    errors=(409, 501),
)
async def fraud_session_edit_route(
    engagement_id: UUID, body: FraudSessionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FraudSessionOut:
    """Record the session; audited `fraud_session.recorded` (T19)."""
    await _gate(ctx, engagement_id, "fraud_session.edit", _RR)
    _not_yet()


@router.put(
    "/fraud-brainstorm/minutes",
    action="fraud_session.edit",
    response_model=FraudSessionOut,
    errors=(409, 501),
)
async def fraud_minutes_route(
    engagement_id: UUID, body: MinutesIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FraudSessionOut:
    """Write the minutes or adopt a suggestion; either resets approval (T19)."""
    await _gate(ctx, engagement_id, "fraud_session.edit", _RR)
    _not_yet()


@router.post(
    "/fraud-brainstorm/minutes/approve",
    action="fraud_minutes.approve",
    response_model=FraudSessionOut,
    errors=(409, 501),
)
async def fraud_minutes_approve_route(
    engagement_id: UUID, body: MinutesApproveIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FraudSessionOut:
    """The EP approves the minutes at their hash: matrix, `require_live_human`, the DB CHECK,
    FRAUD-MINUTES-001 and the audit event; 409 `minutes_changed` (AC2.4; T19)."""
    await _gate(ctx, engagement_id, "fraud_minutes.approve", _RR)
    _not_yet()


@router.get(
    "/fraud-inquiries",
    action="fraud_session.read",
    response_model=ListPage[FraudInquiryOut],
    errors=(501,),
)
async def fraud_inquiries_route(engagement_id: UUID, ctx: Ctx) -> ListPage[FraudInquiryOut]:
    """Inquiries with their computed status (T19)."""
    await _gate(ctx, engagement_id, "fraud_session.read", _RR)
    _not_yet()


@router.post(
    "/fraud-inquiries",
    action="fraud_inquiry.request",
    response_model=FraudInquiryOut,
    status_code=201,
    errors=(409, 501),
)
async def fraud_inquiry_create_route(
    engagement_id: UUID, body: FraudInquiryIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FraudInquiryOut:
    """A POR-05 questionnaire **draft** from a firm template through C5; Dana sees it only after a
    person sends it (AC2.5; T19)."""
    await _gate(ctx, engagement_id, "fraud_inquiry.request", _RR)
    _not_yet()


@router.get(
    "/internal-control/processes",
    action="control.read",
    response_model=ListPage[ProcessOut],
    errors=(501,),
)
async def processes_route(engagement_id: UUID, ctx: Ctx) -> ListPage[ProcessOut]:
    """Processes with walkthrough, design, implementation and reliance (AC6.6; T25)."""
    await _gate(ctx, engagement_id, "control.read", _IC)
    _not_yet()


@router.get(
    "/internal-control/processes/{process_id}",
    action="control.read",
    response_model=ProcessOut,
    errors=(501,),
)
async def process_route(engagement_id: UUID, process_id: UUID, ctx: Ctx) -> ProcessOut:
    await _gate(ctx, engagement_id, "control.read", _IC)
    _not_yet()


@router.put(
    "/internal-control/processes/{process_id}",
    action="control.edit",
    response_model=ProcessOut,
    errors=(409, 501),
)
async def process_edit_route(
    engagement_id: UUID,
    process_id: UUID,
    body: ProcessIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ProcessOut:
    """Record design, implementation, reliance or a walkthrough; audited (T25)."""
    await _gate(ctx, engagement_id, "control.edit", _IC)
    _not_yet()


@router.get(
    "/internal-control/exceptions",
    action="control.read",
    response_model=ListPage[ControlExceptionOut],
    errors=(501,),
)
async def control_exceptions_route(engagement_id: UUID, ctx: Ctx) -> ListPage[ControlExceptionOut]:
    """The Exceptions sheet with Sheet!Cell addresses (AC6.2; T25)."""
    await _gate(ctx, engagement_id, "control.read", _IC)
    _not_yet()


@router.patch(
    "/internal-control/exceptions/{sheet_row}/proposed-severity",
    action="deficiency.propose_severity",
    response_model=ControlExceptionOut,
    errors=(409, 501),
)
async def exception_propose_severity_route(
    engagement_id: UUID,
    sheet_row: Annotated[int, Path(ge=2)],
    body: ProposedSeverityIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ControlExceptionOut:
    """A proposal only; concluding severity is reserved to the engagement partner (AC6.3; T25)."""
    await _gate(ctx, engagement_id, "deficiency.propose_severity", _IC)
    _not_yet()


@router.post(
    "/internal-control/exceptions/{sheet_row}/send-to-findings",
    action="exception.route",
    response_model=RoutedOut,
    errors=(409, 501, 503),
)
async def send_to_findings_route(
    engagement_id: UUID,
    sheet_row: Annotated[int, Path(ge=2)],
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> RoutedOut:
    """Through A-06's registered router; 503 `route_not_available` until it registers (AC6.4)."""
    await _gate(ctx, engagement_id, "exception.route", _IC)
    _not_yet()


@router.post(
    "/internal-control/exceptions/{sheet_row}/convert-to-misstatement",
    action="exception.route",
    response_model=RoutedOut,
    errors=(409, 501, 503),
)
async def convert_to_misstatement_route(
    engagement_id: UUID,
    sheet_row: Annotated[int, Path(ge=2)],
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> RoutedOut:
    """An AUD-16 candidate the same way; 409 `no_amount` without one (AC6.4)."""
    await _gate(ctx, engagement_id, "exception.route", _IC)
    _not_yet()


@router.post(
    "/internal-control/exceptions/{sheet_row}/request-evidence",
    action="request_item.create",
    response_model=RequestDraftOut,
    status_code=201,
    errors=(501,),
)
async def exception_request_evidence_route(
    engagement_id: UUID,
    sheet_row: Annotated[int, Path(ge=2)],
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> RequestDraftOut:
    """An SHL-14 prefill as a C5 draft; nothing is sent (AC6.4; T31)."""
    await _gate(ctx, engagement_id, "request_item.create", _IC)
    _not_yet()


@router.get(
    "/service-organizations",
    action="service_org.read",
    response_model=ListPage[ServiceOrganizationOut],
)
async def service_orgs_route(engagement_id: UUID, ctx: Ctx) -> ListPage[ServiceOrganizationOut]:
    """The inventory shared by AUD-04 and AUD-10 (T07)."""
    await _gate(ctx, engagement_id, "service_org.read", _SO, WORKPAPERS_CORE, any_of=True)
    from abacus.modules.assurance import service_orgs

    actions = await _org_actions(ctx, engagement_id)
    rows = [_org_out(o, actions) for o in await service_orgs.organizations(ctx, engagement_id)]
    return ListPage(items=rows, total=len(rows))


@router.post(
    "/service-organizations",
    action="service_org.edit",
    response_model=ServiceOrganizationOut,
    status_code=201,
    errors=(409,),
)
async def service_org_create_route(
    engagement_id: UUID, body: ServiceOrganizationIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ServiceOrganizationOut:
    """Add a service organization; 409 `duplicate_name` (T07)."""
    await _gate(ctx, engagement_id, "service_org.edit", _SO, WORKPAPERS_CORE, any_of=True)
    from abacus.modules.assurance import service_orgs

    return _org_out(
        await service_orgs.add(
            ctx,
            engagement_id,
            name=body.name,
            services=body.services,
            relevant=body.relevant,
            evidence_type=body.evidence_type,
        ),
        await _org_actions(ctx, engagement_id),
    )


@router.get(
    "/service-organizations/{service_org_id}",
    action="service_org.read",
    response_model=ServiceOrganizationOut,
)
async def service_org_route(
    engagement_id: UUID, service_org_id: UUID, ctx: Ctx
) -> ServiceOrganizationOut:
    await _gate(ctx, engagement_id, "service_org.read", _SO, WORKPAPERS_CORE, any_of=True)
    from abacus.modules.assurance import service_orgs

    return _org_out(
        await service_orgs.organization(ctx, engagement_id, service_org_id),
        await _org_actions(ctx, engagement_id),
    )


@router.patch(
    "/service-organizations/{service_org_id}",
    action="service_org.edit",
    response_model=ServiceOrganizationOut,
    errors=(409,),
)
async def service_org_edit_route(
    engagement_id: UUID,
    service_org_id: UUID,
    body: ServiceOrganizationPatchIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ServiceOrganizationOut:
    await _gate(ctx, engagement_id, "service_org.edit", _SO, WORKPAPERS_CORE, any_of=True)
    from abacus.modules.assurance import service_orgs

    return _org_out(
        await service_orgs.edit(
            ctx,
            engagement_id,
            service_org_id,
            expected_version=body.expected_version,
            services=body.services,
            relevant=body.relevant,
            evidence_type=body.evidence_type,
        ),
        await _org_actions(ctx, engagement_id),
    )


@router.get(
    "/soc-reports/{soc_report_id}",
    action="service_org.read",
    response_model=SocReportOut,
    errors=(501,),
)
async def soc_report_route(engagement_id: UUID, soc_report_id: UUID, ctx: Ctx) -> SocReportOut:
    """The evaluation with its computed gap and CUECs (AC7.1; T31)."""
    await _gate(ctx, engagement_id, "service_org.read", _SO)
    _not_yet()


@router.patch(
    "/soc-reports/{soc_report_id}",
    action="soc_report.evaluate",
    response_model=SocReportOut,
    errors=(409, 501),
)
async def soc_report_edit_route(
    engagement_id: UUID,
    soc_report_id: UUID,
    body: SocReportPatchIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> SocReportOut:
    """Record the report's facts; the gap is recomputed by code (AC7.6; T31)."""
    await _gate(ctx, engagement_id, "soc_report.evaluate", _SO)
    _not_yet()


@router.patch(
    "/soc-reports/{soc_report_id}/cuecs/{n}",
    action="soc_report.evaluate",
    response_model=SocReportOut,
    errors=(409, 501),
)
async def cuec_edit_route(
    engagement_id: UUID,
    soc_report_id: UUID,
    n: Annotated[int, Path(ge=1)],
    body: CuecPatchIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> SocReportOut:
    """Map a CUEC to a control and its evidence; Evidenced once evidence is cited (T31)."""
    await _gate(ctx, engagement_id, "soc_report.evaluate", _SO)
    _not_yet()


@router.post(
    "/soc-reports/{soc_report_id}/drafts",
    action="workpaper.draft",
    response_model=RunStartedOut,
    status_code=202,
    errors=(409, 501),
)
async def soc_report_draft_route(
    engagement_id: UUID, soc_report_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RunStartedOut:
    """The SOC 1 reader run (mode `soc1`): suggestions with page citations (AC7.6; T35)."""
    await _gate(ctx, engagement_id, "workpaper.draft", _SO)
    await _gate(ctx, engagement_id, "workpaper.draft", WORKPAPERS_DRAFTING)
    _not_yet()


@router.post(
    "/soc-reports/{soc_report_id}/requests",
    action="request_item.create",
    response_model=RequestDraftOut,
    status_code=201,
    errors=(501,),
)
async def soc_report_requests_route(
    engagement_id: UUID,
    soc_report_id: UUID,
    body: SocRequestsIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> RequestDraftOut:
    """Request **drafts**: a bridge letter (POR-14) or CUEC evidence (POR-03) (AC7.4; T31)."""
    await _gate(ctx, engagement_id, "request_item.create", _SO)
    _not_yet()


@router.post(
    "/soc-reports/{soc_report_id}/reliance-requests",
    action="soc_report.evaluate",
    response_model=RelianceRequestOut,
    status_code=201,
    errors=(409, 501),
)
async def reliance_request_route(
    engagement_id: UUID, soc_report_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RelianceRequestOut:
    """Raise the `service_org_reliance` card (the EP decides, DEC-83); 409 `gap_open` and
    `cuec_evidence_missing`; never an agent's (AC7.2; T31)."""
    await _gate(ctx, engagement_id, "soc_report.evaluate", _SO)
    _not_yet()
