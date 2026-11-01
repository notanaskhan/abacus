"""The A-06 completion contract stub (A-06-T05; SPEC-642; DEC-1965).
Contract: `docs/contracts/completion.md`; screens AUD-15 (findings), AUD-16 a, e, f (SUM).

Findings rooted on P-04 issues, deficiencies, misstatements, the code-computed SUM and its frozen
snapshots, and minimal consultations. Every route is under `/v1/work-items/{work_item_id}` or a
record's own path, has one matrix action and answers, in order: a client principal 404 (INV-4);
the action on the work item's engagement (walls 404, independence 403); 404 with
`assurance.completion` off; then 501 `not_implemented` until its task (A-06-T09 to T13).

Every figure is code's (ADR-050): projections from `sampling.compute`, the SUM from
`assurance/compute/sum.py`. Severity and the SUM conclusion are the engagement partner's C3 cards
(`deficiency_severity`, `sum_conclusion`), never an endpoint here (INV-1).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import ASSURANCE_COMPLETION
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Money = Annotated[Decimal, classified("confidential")]
Text = Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
CompletionAction = Literal[
    "finding.update",
    "finding.convert",
    "finding.resolve",
    "finding.mark_not_applicable",
    "finding.request_decision",
    "misstatement.update",
    "misstatement.pass_to_sum",
    "sum.update_factors",
    "sum.request_conclusion",
    "sum.snapshot",
    "sum.export",
]
Actions = Annotated[list[CompletionAction], classified("internal")]
Severity = Literal["deficiency", "significant_deficiency", "material_weakness"]
Coso = Literal[
    "control_environment", "risk_assessment", "control_activities", "information_communication",
    "monitoring",
]  # fmt: skip
MisstatementStatus = Literal[
    "candidate", "confirmed", "below_ct", "proposed_to_client", "booked", "passed_on_sum"
]
DeficiencyStatus = Literal["exception_for_resolution", "proposed", "concluded", "communicated"]
ColumnSet = Literal["ebp_net_assets", "commercial"]


# --- findings (AUD-15) ---------------------------------------------------------------------------


class FindingRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    ref: Annotated[str, Field(pattern=r"^F-[0-9]{2,4}$"), classified("internal")]
    title: Annotated[str, classified("confidential")]
    kind: Annotated[
        Literal["control_deficiency", "misstatement", "compliance", "other"],
        classified("internal"),
    ]
    route: Annotated[
        Literal["under_evaluation", "converted_to_misstatement", "converted_to_deficiency"],
        classified("internal"),
    ]
    deficiency_status: Annotated[DeficiencyStatus | None, classified("internal")]
    severity_proposed: Annotated[Severity | None, classified("internal")]
    severity_concluded: Annotated[Severity | None, classified("internal")]
    coso_component: Annotated[Coso | None, classified("internal")]
    workpaper_ref: Annotated[str | None, classified("internal")]  # "EBP-04"
    # "Marcus Delaney via Agent" for an agent-raised finding (INV-5).
    created_by_name: Annotated[str, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class FindingDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding: Annotated[FindingRowOut, classified("confidential")]
    issue_id: Annotated[UUID, classified("internal")]
    # Agent text through AgentText only; shown with its verified citations (INV-2).
    why_surfaced: Annotated[str | None, Field(max_length=4000), classified("confidential")]
    citation_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")]
    evaluation: Annotated[dict[str, str], classified("confidential")]
    decision_card_id: Annotated[UUID | None, classified("internal")]
    allowed_actions: Actions


class FindingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    kind: Annotated[
        Literal["control_deficiency", "misstatement", "compliance", "other"],
        classified("internal"),
    ]
    coso_component: Annotated[Coso | None, classified("internal")] = None
    citation_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")] = Field(
        default_factory=list
    )


class ConvertToMisstatementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Annotated[Literal["factual", "judgmental", "projected"], classified("internal")]
    amount: Money | None = None  # null for projected: the projection is code's
    projection_ref: Annotated[UUID | None, classified("internal")] = None
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class ReasonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,59}$"), classified("internal")]
    note: Text | None = None


class DecisionRaisedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_card_id: Annotated[UUID, classified("internal")]


# --- misstatements and the SUM (AUD-16 a, e, f) --------------------------------------------------


class MisstatementOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    ref: Annotated[str, classified("internal")]  # AJE-1, PAJE-1, BCT-1, PY-1
    origin_ref: Annotated[str | None, classified("internal")]
    type: Annotated[Literal["factual", "judgmental", "projected"], classified("internal")]
    nature: Annotated[Literal["misstatement", "reclassification"], classified("internal")]
    status: Annotated[MisstatementStatus, classified("internal")]
    amount: Money
    finding_ref: Annotated[str | None, classified("internal")]
    proposed_entry_ref: Annotated[str | None, classified("internal")]
    allowed_actions: Actions


class SumOut(BaseModel):
    """Code's SUM (AC-6): the browser renders these numbers and computes none of them."""

    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
            "examples": [
                {
                    "column_set": "ebp_net_assets",
                    "rollover": "34150.00",
                    "iron_curtain": "22250.00",
                    "aggregate": "34150.00",
                    "pct_of_pm": "18.1",
                    "fill_pct_of_overall": "13.5",
                    "ct_tick_pct": "5.0",
                    "pm_tick_pct": "75.0",
                    "approaching_pm": False,
                    "above_pm": False,
                    "engine_version": "1",
                    "inputs_hash": "0" * 64,
                }
            ]
        },
    )

    column_set: Annotated[ColumnSet, classified("internal")]
    rollover: Money
    iron_curtain: Money
    aggregate: Money
    pct_of_pm: Annotated[Decimal, classified("confidential")]
    fill_pct_of_overall: Annotated[Decimal, classified("confidential")]
    ct_tick_pct: Annotated[Decimal, classified("internal")]
    pm_tick_pct: Annotated[Decimal, classified("internal")]
    approaching_pm: Annotated[bool, classified("internal")]
    above_pm: Annotated[bool, classified("internal")]
    engine_version: Annotated[str, classified("internal")]
    inputs_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]


class SnapshotOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, Field(ge=1), classified("internal")]
    purpose: Annotated[Literal["conclusion", "rep_letter_attachment"], classified("internal")]
    inputs_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), classified("internal")]
    decision_card_id: Annotated[UUID | None, classified("internal")]


class SnapshotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: Annotated[Literal["conclusion", "rep_letter_attachment"], classified("internal")]


class FactorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    note: Text
    citation_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")] = Field(
        default_factory=list
    )


# --- the routes ----------------------------------------------------------------------------------


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str) -> None:
    """Client 404; the action on the work item's engagement; the flag."""
    if ctx.client:
        raise NotFound("completion")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, ASSURANCE_COMPLETION):
        raise NotFound(ASSURANCE_COMPLETION.name)


async def _gate_flag(ctx: AuthContext) -> None:
    """A record's own path: client 404 and the flag; the record's service authorises (T09+)."""
    if ctx.client:
        raise NotFound("completion")
    if not await flag_enabled(ctx.tenant, ASSURANCE_COMPLETION):
        raise NotFound(ASSURANCE_COMPLETION.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


router = AbacusRouter(prefix="/v1", tags=["assurance"])
_WI = "/work-items/{work_item_id}"


@router.get(
    f"{_WI}/findings", action="finding.read", response_model=ListPage[FindingRowOut], errors=(501,)
)
async def audit_findings_route(work_item_id: UUID, ctx: Ctx) -> ListPage[FindingRowOut]:
    """Severity bands with counts and the awaiting-decision badge (AUD-15 a; T11)."""
    await _gate(ctx, work_item_id, "finding.read")
    _not_yet()


@router.post(
    f"{_WI}/findings",
    action="finding.create",
    response_model=FindingDetailOut,
    status_code=201,
    errors=(409, 501),
)
async def audit_finding_create_route(
    work_item_id: UUID, body: FindingIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FindingDetailOut:
    """Record a finding on a new P-04 issue; an agent's lands Proposed with citations verified
    (422 `uncited_change`; T11)."""
    await _gate(ctx, work_item_id, "finding.create")
    _not_yet()


@router.get(
    "/findings/{finding_id}", action="finding.read", response_model=FindingDetailOut, errors=(501,)
)
async def audit_finding_route(finding_id: UUID, ctx: Ctx) -> FindingDetailOut:
    await _gate_flag(ctx)
    _not_yet()


@router.post(
    "/findings/{finding_id}/convert-to-deficiency",
    action="finding.convert",
    response_model=FindingDetailOut,
    errors=(409, 501),
)
async def finding_to_deficiency_route(
    finding_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FindingDetailOut:
    await _gate_flag(ctx)
    _not_yet()


@router.post(
    "/findings/{finding_id}/convert-to-misstatement",
    action="finding.convert",
    response_model=MisstatementOut,
    errors=(409, 501),
)
async def finding_to_misstatement_route(
    finding_id: UUID, body: ConvertToMisstatementIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MisstatementOut:
    """A projected misstatement takes its figure from `sampling.compute.projection` (T09)."""
    await _gate_flag(ctx)
    _not_yet()


@router.post(
    "/findings/{finding_id}/resolve",
    action="finding.resolve",
    response_model=FindingDetailOut,
    errors=(409, 501),
)
async def finding_resolve_route(
    finding_id: UUID, body: ReasonIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FindingDetailOut:
    await _gate_flag(ctx)
    _not_yet()


@router.post(
    "/findings/{finding_id}/request-decision",
    action="finding.request_decision",
    response_model=DecisionRaisedOut,
    status_code=201,
    errors=(409, 501),
)
async def finding_request_decision_route(
    finding_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DecisionRaisedOut:
    """Raise the `deficiency_severity` card reserved to the EP (AUD-15 a, b; T13)."""
    await _gate_flag(ctx)
    _not_yet()


@router.get(
    f"{_WI}/misstatements",
    action="misstatement.read",
    response_model=ListPage[MisstatementOut],
    errors=(501,),
)
async def misstatements_route(
    work_item_id: UUID,
    ctx: Ctx,
    view: Literal["proposed", "reclass", "passed", "below_ct"] = "proposed",
) -> ListPage[MisstatementOut]:
    await _gate(ctx, work_item_id, "misstatement.read")
    _not_yet()


@router.post(
    "/misstatements/{misstatement_id}/pass-to-sum",
    action="misstatement.pass_to_sum",
    response_model=MisstatementOut,
    errors=(409, 501),
)
async def misstatement_pass_route(
    misstatement_id: UUID, body: ReasonIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MisstatementOut:
    """DF-28: the EP passes a declined misstatement on SUM with a reason (T09)."""
    await _gate_flag(ctx)
    _not_yet()


@router.get(f"{_WI}/sum", action="sum.read", response_model=SumOut, errors=(501,))
async def sum_route(
    work_item_id: UUID, ctx: Ctx, view: Literal["ebp_net_assets", "commercial"] | None = None
) -> SumOut:
    """Code's SUM under both views (AUD-16 a; T13)."""
    await _gate(ctx, work_item_id, "sum.read")
    _not_yet()


@router.put(
    f"{_WI}/sum/qualitative-factors/{{factor}}",
    action="sum.update_factors",
    response_model=SumOut,
    errors=(409, 501),
)
async def sum_factor_route(
    work_item_id: UUID, factor: str, body: FactorIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SumOut:
    """A qualitative factor through `review.api.record_value` with its citation (T13)."""
    await _gate(ctx, work_item_id, "sum.update_factors")
    _not_yet()


@router.post(
    f"{_WI}/sum/request-conclusion",
    action="sum.request_conclusion",
    response_model=DecisionRaisedOut,
    status_code=201,
    errors=(409, 501),
)
async def sum_request_conclusion_route(
    work_item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DecisionRaisedOut:
    """A frozen snapshot and the `sum_conclusion` card (409 `snapshot_changed`; T13)."""
    await _gate(ctx, work_item_id, "sum.request_conclusion")
    _not_yet()


@router.post(
    f"{_WI}/sum/snapshots",
    action="sum.snapshot",
    response_model=SnapshotOut,
    status_code=201,
    errors=(501,),
)
async def sum_snapshot_route(
    work_item_id: UUID, body: SnapshotIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SnapshotOut:
    await _gate(ctx, work_item_id, "sum.snapshot")
    _not_yet()
