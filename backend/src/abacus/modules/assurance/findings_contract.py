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
from typing import Annotated, Any, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Query
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
        default_factory=list[UUID]
    )
    # A-06-T11 (DEC-2063): the workpaper the finding's issue sits on, and an agent's run.
    workpaper_id: Annotated[UUID, classified("internal")]
    why_surfaced: Annotated[str | None, Field(max_length=4000), classified("confidential")] = None
    agent_run_id: Annotated[UUID | None, classified("internal")] = None


class ConvertToMisstatementIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Annotated[Literal["factual", "judgmental", "projected"], classified("internal")]
    # Null for projected: the projection is code's.
    amount: Annotated[Money | None, classified("confidential")] = None
    projection_ref: Annotated[UUID | None, classified("internal")] = None
    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    column_set: Annotated[ColumnSet, classified("internal")] = "commercial"


class ReasonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,59}$"), classified("internal")]
    note: Annotated[Text | None, classified("confidential")] = None


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


class SumSnapshotOut(BaseModel):
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
        default_factory=list[UUID]
    )


# --- sign-off matrix and EP involvement (AUD-17; A-06-T23) ---------------------------------------


class SignOffMatrixCellOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Annotated[int, Field(ge=1, le=5), classified("internal")]
    state: Annotated[Literal["signed", "stale", "pending", "not_required"], classified("internal")]
    initials: Annotated[str | None, classified("internal")]
    signed_at: Annotated[datetime | None, classified("internal")]
    version_no: Annotated[int | None, classified("internal")]
    hash_prefix: Annotated[str | None, Field(pattern=r"^[0-9a-f]{8}$"), classified("internal")]


class SignOffMatrixRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    code: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    section: Annotated[
        Literal["planning", "fieldwork", "completion", "reporting"], classified("internal")
    ]
    cells: list[SignOffMatrixCellOut]


class SignOffMatrixFooterOut(BaseModel):
    """Prepared 25 · Reviewed 24 · Partner 8 of 13 · EQR 0 of 6 · Changed after sign-off 1."""

    model_config = ConfigDict(frozen=True)

    prepared: Annotated[int, Field(ge=0), classified("internal")]
    reviewed: Annotated[int, Field(ge=0), classified("internal")]
    partner_signed: Annotated[int, Field(ge=0), classified("internal")]
    partner_required: Annotated[int, Field(ge=0), classified("internal")]
    eqr_signed: Annotated[int, Field(ge=0), classified("internal")]
    eqr_required: Annotated[int, Field(ge=0), classified("internal")]
    changed_after_sign_off: Annotated[int, Field(ge=0), classified("internal")]


class SignOffMatrixOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: list[SignOffMatrixRowOut]
    footer: SignOffMatrixFooterOut


class InvolvementEntryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["decision", "sign_off"], classified("internal")]
    at: Annotated[datetime, classified("internal")]
    by_name: Annotated[str, classified("internal")]
    subject: Annotated[str, classified("internal")]
    outcome: Annotated[str, classified("internal")]


class EpInvolvementOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[InvolvementEntryOut]


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


def _finding_out(found: object) -> FindingDetailOut:
    from abacus.modules.assurance import findings

    f = cast(findings.Finding, found)
    return FindingDetailOut(
        finding=_row_out(f),
        issue_id=f.issue_id,
        why_surfaced=f.why_surfaced,
        citation_ids=[],
        evaluation=f.evaluation,
        decision_card_id=f.decision_card_id,
        allowed_actions=cast(Actions, list(f.allowed_actions)),
    )


def _row_out(f: object) -> FindingRowOut:
    from abacus.modules.assurance import findings

    r = cast(findings.Finding, f)
    return FindingRowOut(
        id=r.id,
        ref=r.ref,
        title=r.title,
        kind=cast(Any, r.kind),  # Any: 0644's CHECK holds the words
        route=cast(Any, r.route),  # Any: 0644's CHECK holds the words
        deficiency_status=cast(Any, r.deficiency_status),  # Any: 0644's CHECK
        severity_proposed=cast(Any, r.severity_proposed),  # Any: 0644's CHECK
        severity_concluded=cast(Any, r.severity_concluded),  # Any: 0644's CHECK
        coso_component=cast(Any, r.coso_component),  # Any: 0644's CHECK
        workpaper_ref=None,
        created_by_name=r.created_by_name,
        created_at=r.created_at,
    )


@router.get(
    f"{_WI}/findings", action="finding.read", response_model=ListPage[FindingRowOut], errors=(501,)
)
async def audit_findings_route(work_item_id: UUID, ctx: Ctx) -> ListPage[FindingRowOut]:
    """Severity bands with counts and the awaiting-decision badge (AUD-15 a; T11)."""
    await _gate(ctx, work_item_id, "finding.read")
    from abacus.modules.assurance import findings

    page = await findings.findings_of(ctx, work_item_id)
    return ListPage(
        items=[_row_out(f) for f in page.rows],
        total=len(page.rows),
        counts={**page.counts, "awaiting_decision": page.awaiting_decision},
    )


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
    (422 `uncited_finding`; T11)."""
    await _gate(ctx, work_item_id, "finding.create")
    from abacus.modules.assurance import findings

    new = findings.NewFinding(
        workpaper_id=body.workpaper_id,
        title=body.title,
        kind=body.kind,
        coso_component=body.coso_component,
        citation_ids=tuple(body.citation_ids),
        why_surfaced=body.why_surfaced,
        agent_run_id=body.agent_run_id,
    )
    return _finding_out(await findings.record_finding(ctx, work_item_id, new))


@router.get(
    "/findings/{finding_id}", action="finding.read", response_model=FindingDetailOut, errors=(501,)
)
async def audit_finding_route(finding_id: UUID, ctx: Ctx) -> FindingDetailOut:
    from abacus.modules.assurance import findings

    await _gate(ctx, await findings.work_item_of(ctx.tenant, finding_id), "finding.read")
    return _finding_out(await findings.finding(ctx, finding_id))


@router.post(
    "/findings/{finding_id}/convert-to-deficiency",
    action="finding.convert",
    response_model=FindingDetailOut,
    errors=(409, 501),
)
async def finding_to_deficiency_route(
    finding_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FindingDetailOut:
    from abacus.modules.assurance import findings

    await _gate(ctx, await findings.work_item_of(ctx.tenant, finding_id), "finding.convert")
    return _finding_out(await findings.to_deficiency(ctx, finding_id))


@router.post(
    "/findings/{finding_id}/convert-to-misstatement",
    action="finding.convert",
    response_model=MisstatementOut,
    errors=(409, 501),
)
async def finding_to_misstatement_route(
    finding_id: UUID, body: ConvertToMisstatementIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> MisstatementOut:
    """A projected misstatement takes its figure from sampling (422 `projection_unavailable`
    until A-03 exposes its projection facts; T11)."""
    from abacus.modules.assurance import findings

    work_item = await findings.work_item_of(ctx.tenant, finding_id)
    await _gate(ctx, work_item, "finding.convert")
    misstatement_id = await findings.to_misstatement(
        ctx, finding_id, type_=body.type, amount=body.amount, column_set=body.column_set
    )
    found = await findings.finding(ctx, finding_id)
    return MisstatementOut(
        id=misstatement_id,
        ref=f"M-{found.ref.removeprefix('F-')}",
        origin_ref=None,
        type=body.type,
        nature="misstatement",
        status="confirmed",
        amount=body.amount or Decimal(0),
        finding_ref=found.ref,
        proposed_entry_ref=None,
        allowed_actions=[],
    )


@router.post(
    "/findings/{finding_id}/resolve",
    action="finding.resolve",
    response_model=FindingDetailOut,
    errors=(409, 501),
)
async def finding_resolve_route(
    finding_id: UUID, body: ReasonIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FindingDetailOut:
    """Resolved through the finding's issue; the agent is refused by the matrix (T11)."""
    from abacus.modules.assurance import findings

    await _gate(ctx, await findings.work_item_of(ctx.tenant, finding_id), "finding.resolve")
    return _finding_out(await findings.move(ctx, finding_id, "resolved"))


@router.post(
    "/findings/{finding_id}/not-applicable",
    action="finding.mark_not_applicable",
    response_model=FindingDetailOut,
    errors=(409,),
)
async def finding_not_applicable_route(
    finding_id: UUID, body: ReasonIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FindingDetailOut:
    """Marked not applicable through the finding's issue; never by the agent (T11)."""
    from abacus.modules.assurance import findings

    work_item = await findings.work_item_of(ctx.tenant, finding_id)
    await _gate(ctx, work_item, "finding.mark_not_applicable")
    return _finding_out(await findings.move(ctx, finding_id, "not_applicable"))


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
    from abacus.modules.assurance import completion_decisions as cd
    from abacus.modules.assurance import findings

    work_item = await findings.work_item_of(ctx.tenant, finding_id)
    await _gate(ctx, work_item, "finding.request_decision")
    return DecisionRaisedOut(decision_card_id=await cd.request_severity_decision(ctx, finding_id))


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
    """A frozen snapshot and the `sum_conclusion` card (409 `no_snapshot`; T13)."""
    await _gate(ctx, work_item_id, "sum.request_conclusion")
    from abacus.modules.assurance import completion_decisions as cd
    from abacus.modules.engagements.api import assurance_item

    item = await assurance_item(ctx.tenant, work_item_id)
    card = await cd.request_sum_conclusion(ctx, item.engagement_id, work_item_id)
    return DecisionRaisedOut(decision_card_id=card)


@router.post(
    f"{_WI}/sum/snapshots",
    action="sum.snapshot",
    response_model=SumSnapshotOut,
    status_code=201,
    errors=(501,),
)
async def sum_snapshot_route(
    work_item_id: UUID, body: SnapshotIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SumSnapshotOut:
    await _gate(ctx, work_item_id, "sum.snapshot")
    _not_yet()


@router.get(f"{_WI}/sign-off-matrix", action="sign_off.read", response_model=SignOffMatrixOut)
async def sign_off_matrix_route(
    work_item_id: UUID,
    ctx: Ctx,
    section: Annotated[
        Literal["planning", "fieldwork", "completion", "reporting"] | None, Query()
    ] = None,
) -> SignOffMatrixOut:
    """AUD-17: workpapers by L1 to L5 with the footer counts; L5 read-only (A-06-T23)."""
    await _gate(ctx, work_item_id, "sign_off.read")
    from abacus.modules.assurance import review_matrix

    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    found = await review_matrix.matrix(ctx.tenant, cast(UUID, engagement_id), section=section)
    return SignOffMatrixOut(
        rows=[
            SignOffMatrixRowOut(
                target_type=r.target_type,
                target_id=r.target_id,
                code=r.code,
                title=r.title,
                section=r.section,
                cells=[
                    SignOffMatrixCellOut(
                        level=c.level,
                        state=c.state,
                        initials=c.initials,
                        signed_at=c.signed_at,
                        version_no=c.version_no,
                        hash_prefix=c.hash_prefix,
                    )
                    for c in r.cells
                ],
            )
            for r in found.rows
        ],
        footer=SignOffMatrixFooterOut(**vars(found.footer)),
    )


@router.get(f"{_WI}/ep-involvement", action="sign_off.read", response_model=EpInvolvementOut)
async def ep_involvement_route(work_item_id: UUID, ctx: Ctx) -> EpInvolvementOut:
    """AUD-17 c: the EP's decisions and L4 sign-offs, oldest first (AU-C 220; A-06-T23)."""
    await _gate(ctx, work_item_id, "sign_off.read")
    from abacus.modules.assurance import review_matrix
    from abacus.modules.identity.api import names_of

    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    entries = await review_matrix.ep_involvement(ctx.tenant, cast(UUID, engagement_id))
    names = await names_of(sorted({e.by_user_id for e in entries}, key=str)) if entries else {}
    return EpInvolvementOut(
        items=[
            InvolvementEntryOut(
                kind=e.kind,
                at=e.at,
                by_name=names.get(e.by_user_id, ""),
                subject=e.subject,
                outcome=e.outcome,
            )
            for e in entries
        ]
    )
