"""Quality management v1 stub (Q-05-T05; SPEC-711 AC-1 to AC-10; `quality-management.md`).
Screens ADM-11 (dashboard, override and accuracy) and ADM-12 (monitoring, inspections, QM
findings, the annual evaluation).

Every route answers, in order: a client principal 404 (no portal route; INV-4); the
`quality.management` flag off 404; a human-only route refuses an agent, the platform or a
support session 403 (INV-1); then 501 until its build task (Q-05-T07, T08, T13).

Classification (ADR-031): QM text (titles, notes, rationale, root cause) is `confidential`;
ids, refs, counts, rates and states are `internal`. Rates are exact decimals computed by code
from `agent_output_outcomes` (ADR-050; DEC-96). The agent reads and decides nothing here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel._flags import QUALITY_MANAGEMENT
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Confidential = classified("confidential")
Count = Annotated[int, Field(ge=0), Internal]
Rate = Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=1), Internal]
MaybeRate = Annotated[
    Decimal | None, Field(ge=0, le=100, max_digits=5, decimal_places=1), Internal
]
Ref = Annotated[str, Field(max_length=20), Internal]

Component = Literal[
    "governance_leadership",
    "ethical_requirements",
    "acceptance_continuance",
    "engagement_performance",
    "resources",
    "information_communication",
]
InspectionKind = Literal["post_issuance_archived", "pre_lock", "in_process", "post_filing"]
InspectionStatus = Literal["planned", "in_progress", "concluded"]
FindingStatus = Literal["open", "in_progress", "remediated"]
Evaluation = Literal[
    "finding_open", "not_a_deficiency", "deficiency", "severe_deficiency", "severe_and_pervasive"
]
RootCause = Literal["people", "process", "methodology", "technology", "culture"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class QualityPersonOut(BaseModel):
    model_config = _cfg()

    user_id: Annotated[UUID, Internal]
    name: Annotated[str, Field(max_length=120), Confidential]


class QualityTilesOut(BaseModel):
    """ADM-11 a (AC-1): 2 of 24 · 5 · 6.0% (206 of 3,410) · 96.8% · 2 · 92 days."""

    model_config = _cfg()

    objectives_at_risk: Count
    objectives: Count
    findings_open: Count
    override_rate: MaybeRate = None
    overrides: Count
    outputs: Count
    tolerance_pct: Rate
    accuracy: MaybeRate = None
    consultations_open: Count
    days_to_evaluation: Annotated[int, Internal]


class QualityComponentOut(BaseModel):
    model_config = _cfg()

    component: Annotated[Component, Internal]
    health: Annotated[Literal["ok", "at_risk"], Internal]
    signals: Annotated[list[str], Internal] = []


class QualityDashboardOut(BaseModel):
    model_config = _cfg()

    cycle_year: Annotated[int, Field(ge=2020, le=2100), Internal]
    office_id: Annotated[UUID | None, Internal] = None
    objectives_firm_wide: Annotated[bool, Internal]
    tiles: Annotated[QualityTilesOut, classified("internal")]
    components: Annotated[list[QualityComponentOut], Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class QualityObjectiveOut(BaseModel):
    model_config = _cfg()

    objective_id: Annotated[UUID, Internal]
    component: Annotated[Component, Internal]
    ref: Ref
    title: Annotated[str, Field(max_length=300), Confidential]
    owner: Annotated[QualityPersonOut | None, classified("confidential")] = None
    health_flag: Annotated[Literal["at_risk"] | None, Internal] = None
    risks: Count
    responses: Count
    version: Annotated[int, Field(ge=1), Internal]


class QualityRegisterOut(BaseModel):
    """24 objectives, 38 risks, 58 responses (AC-34)."""

    model_config = _cfg()

    objectives: Annotated[list[QualityObjectiveOut], Internal]
    risks: Count
    responses: Count


class QualityObjectivePatchIn(BaseModel):
    model_config = _cfg()

    owner_user_id: Annotated[UUID | None, Internal] = None
    health_flag: Annotated[Literal["at_risk"] | None, Internal] = None
    note: Annotated[str | None, Field(max_length=2000), Confidential] = None
    version: Annotated[int, Field(ge=1), Internal]


class QualityImportIn(BaseModel):
    model_config = _cfg()

    kind: Annotated[Literal["register", "cycle"], Internal]
    source_evidence_version_id: Annotated[UUID, Internal]


class QualityImportOut(BaseModel):
    model_config = _cfg()

    import_id: Annotated[UUID, Internal]
    kind: Annotated[Literal["register", "cycle"], Internal]
    status: Annotated[Literal["dry_run", "published"], Internal]
    counts: Annotated[dict[str, int], Internal]


class QualityRiskReviewIn(BaseModel):
    model_config = _cfg()

    reviewed_on: Annotated[date, Internal]
    note: Annotated[str | None, Field(max_length=2000), Confidential] = None


class QualityRiskReviewOut(BaseModel):
    model_config = _cfg()

    review_id: Annotated[UUID, Internal]
    reviewed_on: Annotated[date, Internal]
    reviewed_by: Annotated[QualityPersonOut, classified("confidential")]


class QualityAgentRowOut(BaseModel):
    """ADM-11 c (AC-3): EBP Audit Workpapers 37 = 21 + 9 + 7."""

    model_config = _cfg()

    agent_key: Annotated[str, Field(max_length=80), Internal]
    label: Annotated[str, Field(max_length=120), Internal]
    outputs: Count
    overrides: Count
    rate: MaybeRate = None
    rated: Annotated[bool, Internal]
    above_tolerance: Annotated[bool, Internal]
    finding_ref: Annotated[str | None, Field(max_length=20), Internal] = None


class QualityOverridesOut(BaseModel):
    model_config = _cfg()

    window_days: Annotated[int, Field(ge=1, le=365), Internal]
    tolerance_pct: Rate
    sample_n: Count
    outputs: Count
    overrides: Count
    rate: MaybeRate = None
    unrated: Count
    rows: Annotated[list[QualityAgentRowOut], Internal]


class QualityReasonOut(BaseModel):
    model_config = _cfg()

    reason_code: Annotated[str, Field(max_length=40), Internal]
    count: Count


class QualityReasonsOut(BaseModel):
    model_config = _cfg()

    agent_key: Annotated[str, Field(max_length=80), Internal]
    items: Annotated[list[QualityReasonOut], Internal]


class QualityAccuracyOut(BaseModel):
    """ADM-11 f (AC-4): 1,320 of 41,260 fields changed; 96.8%."""

    model_config = _cfg()

    returns_filed: Count
    fields: Count
    changed: Count
    accuracy: MaybeRate = None


class QualityCycleOut(BaseModel):
    model_config = _cfg()

    cycle_id: Annotated[UUID, Internal]
    year: Annotated[int, Field(ge=2020, le=2100), Internal]
    as_of: Annotated[date, Internal]
    planned: Count
    in_progress: Count
    concluded: Count
    findings_open: Count


class QualityCycleListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[QualityCycleOut], Internal]


class QualityInspectionOut(BaseModel):
    model_config = _cfg()

    inspection_id: Annotated[UUID, Internal]
    ref: Ref
    work_item_id: Annotated[UUID, Internal]
    engagement_name: Annotated[str, Field(max_length=200), Confidential]
    kind: Annotated[InspectionKind, Internal]
    basis: Annotated[Literal["sqms1", "firm_policy_c230_10_36"], Internal]
    inspector: Annotated[QualityPersonOut, classified("confidential")]
    status: Annotated[InspectionStatus, Internal]
    due_on: Annotated[date | None, Internal] = None
    allowed_actions: Annotated[list[str], Internal] = []


class QualityInspectionListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[QualityInspectionOut], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class QualityCandidateOut(BaseModel):
    """ADM-12 b (AC-7): risk score by code; the objectivity verdict per inspector."""

    model_config = _cfg()

    work_item_id: Annotated[UUID, Internal]
    engagement_name: Annotated[str, Field(max_length=200), Confidential]
    risk_score: Annotated[Decimal, Field(ge=0, max_digits=6, decimal_places=2), Internal]
    selected_because: Annotated[str, Field(max_length=300), Internal]
    not_objective_user_ids: Annotated[list[UUID], Internal] = []


class QualityCandidateListOut(BaseModel):
    model_config = _cfg()

    rule_version: Annotated[int, Field(ge=1), Internal]
    items: Annotated[list[QualityCandidateOut], Internal]


class QualityInspectionIn(BaseModel):
    model_config = _cfg()

    cycle_id: Annotated[UUID, Internal]
    work_item_id: Annotated[UUID, Internal]
    kind: Annotated[InspectionKind, Internal]
    inspector_user_id: Annotated[UUID, Internal]
    due_on: Annotated[date | None, Internal] = None


class QualityFindingOut(BaseModel):
    model_config = _cfg()

    finding_id: Annotated[UUID, Internal]
    ref: Ref
    source: Annotated[Literal["inspection", "agent_monitoring", "other"], Internal]
    agent_key: Annotated[str | None, Field(max_length=80), Internal] = None
    inspection_ref: Annotated[str | None, Field(max_length=20), Internal] = None
    title: Annotated[str, Field(max_length=300), Confidential]
    status: Annotated[FindingStatus, Internal]
    evaluation: Annotated[Evaluation | None, Internal] = None
    root_cause_category: Annotated[RootCause | None, Internal] = None
    owner: Annotated[QualityPersonOut | None, classified("confidential")] = None
    due_on: Annotated[date | None, Internal] = None
    raised_by_kind: Annotated[Literal["human", "system"], Internal]
    version: Annotated[int, Field(ge=1), Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class QualityFindingListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[QualityFindingOut], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class QualityFindingIn(BaseModel):
    model_config = _cfg()

    cycle_id: Annotated[UUID, Internal]
    inspection_id: Annotated[UUID | None, Internal] = None
    title: Annotated[str, Field(min_length=1, max_length=300), Confidential]
    owner_user_id: Annotated[UUID | None, Internal] = None
    due_on: Annotated[date | None, Internal] = None


class QualityFindingPatchIn(BaseModel):
    model_config = _cfg()

    root_cause_category: Annotated[RootCause | None, Internal] = None
    root_cause: Annotated[str | None, Field(max_length=4000), Confidential] = None
    remediation: Annotated[str | None, Field(max_length=4000), Confidential] = None
    owner_user_id: Annotated[UUID | None, Internal] = None
    due_on: Annotated[date | None, Internal] = None
    version: Annotated[int, Field(ge=1), Internal]


class QualityEvaluationIn(BaseModel):
    """Only the QM owner evaluates (AC-9); the rationale is required."""

    model_config = _cfg()

    evaluation: Annotated[Evaluation, Internal]
    rationale: Annotated[str, Field(min_length=1, max_length=4000), Confidential]


class QualityRemediateIn(BaseModel):
    model_config = _cfg()

    note: Annotated[str, Field(min_length=1, max_length=4000), Confidential]


class QualityTodoIn(BaseModel):
    model_config = _cfg()

    title: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    assignee_user_id: Annotated[UUID, Internal]
    due_on: Annotated[date | None, Internal] = None


class QualityTodoOut(BaseModel):
    model_config = _cfg()

    todo_id: Annotated[UUID, Internal]
    finding_id: Annotated[UUID, Internal]


class QualityAnnualEvaluationOut(BaseModel):
    """ADM-12 d, f (AC-10): the card reserved to the individual with ultimate responsibility."""

    model_config = _cfg()

    year: Annotated[int, Field(ge=2020, le=2100), Internal]
    status: Annotated[Literal["not_started", "concluded"], Internal]
    responsible: Annotated[QualityPersonOut, classified("confidential")]
    decision_card_id: Annotated[UUID | None, Internal] = None
    concluded_at: Annotated[datetime | None, Internal] = None
    checklist: Annotated[dict[str, bool], Internal] = {}
    inspections_open: Count
    allowed_actions: Annotated[list[str], Internal] = []


class QualityChecklistIn(BaseModel):
    model_config = _cfg()

    checklist: Annotated[dict[str, bool], Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

quality_router = AbacusRouter(prefix="/v1", tags=["practice"])
_Q = "/quality"


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, QUALITY_MANAGEMENT):
        raise NotFound(QUALITY_MANAGEMENT.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@quality_router.get(
    f"{_Q}/dashboard", action="quality.read", response_model=QualityDashboardOut, errors=(501,)
)
async def quality_dashboard_route(
    ctx: Ctx, office_id: UUID | None = None, cycle: int | None = None
) -> QualityDashboardOut:
    """ADM-11 a (Q-05-T08): tiles and component health; an office narrows the rate only."""
    from abacus.kernel.clock import now
    from abacus.modules.practice.quality_dashboard import dashboard

    await _on(ctx)
    del cycle
    found = await dashboard(ctx, await now(ctx.tenant), office_id)
    return QualityDashboardOut.model_validate(found)


@quality_router.get(
    f"{_Q}/register", action="quality.read", response_model=QualityRegisterOut, errors=(501,)
)
async def quality_register_route(
    ctx: Ctx, component: Component | None = None
) -> QualityRegisterOut:
    await _on(ctx)
    from abacus.modules.practice import quality_register as reg

    found = await reg.register(ctx.tenant, component)
    return QualityRegisterOut.model_validate({
        "objectives": [await _objective_out(o, found) for o in found["objectives"]],
        "risks": len(found["risks"]),
        "responses": len(found["responses"]),
    })  # fmt: skip


@quality_router.patch(
    f"{_Q}/objectives/{{objective_id}}",
    action="quality.manage",
    response_model=QualityObjectiveOut,
    errors=(409, 501),
)
async def quality_objective_route(
    objective_id: UUID, body: QualityObjectivePatchIn, ctx: Ctx
) -> QualityObjectiveOut:
    await _human(ctx, "quality.manage")
    from abacus.modules.practice import quality_register as reg

    await reg.patch_objective(
        ctx,
        objective_id,
        owner_user_id=body.owner_user_id,
        health_flag=body.health_flag,
        note=body.note,
        version=body.version,
    )
    found = await reg.register(ctx.tenant, None)
    match = [o for o in found["objectives"] if o["id"] == objective_id]
    if not match:
        raise NotFound("qm_objective")
    return QualityObjectiveOut.model_validate(await _objective_out(match[0], found))


@quality_router.post(
    f"{_Q}/imports",
    action="quality.manage",
    response_model=QualityImportOut,
    status_code=201,
    errors=(409, 501),
)
async def quality_import_route(
    body: QualityImportIn, ctx: Ctx, key: IdempotencyKey
) -> QualityImportOut:
    """A dry run; the register is firm content, never a commit."""
    await _human(ctx, "quality.manage")
    from abacus.modules.practice import quality_register as reg

    del key
    made = await reg.dry_run(ctx, body.kind, body.source_evidence_version_id)
    return _import_out(await reg.import_row(ctx.tenant, made))


@quality_router.post(
    f"{_Q}/imports/{{import_id}}/publish",
    action="quality.manage",
    response_model=QualityImportOut,
    errors=(409, 501),
)
async def quality_import_publish_route(
    import_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> QualityImportOut:
    await _human(ctx, "quality.manage")
    from abacus.modules.practice import quality_register as reg

    del key
    made = await reg.publish(ctx, import_id)
    return _import_out(await reg.import_row(ctx.tenant, made))


@quality_router.post(
    f"{_Q}/risk-assessment/reviews",
    action="quality.manage",
    response_model=QualityRiskReviewOut,
    status_code=201,
    errors=(501,),
)
async def quality_risk_review_route(
    body: QualityRiskReviewIn, ctx: Ctx, key: IdempotencyKey
) -> QualityRiskReviewOut:
    await _human(ctx, "quality.manage")
    from abacus.modules.practice import quality_register as reg

    del key
    review_id = await reg.record_review(ctx, body.reviewed_on, body.note)
    return QualityRiskReviewOut.model_validate(
        {
            "review_id": review_id,
            "reviewed_on": body.reviewed_on,
            "reviewed_by": (await _person(ctx.user_id)).model_dump(),
        }
    )


@quality_router.get(
    f"{_Q}/agent-overrides",
    action="quality.read",
    response_model=QualityOverridesOut,
    errors=(501,),
)
async def quality_overrides_route(
    ctx: Ctx, window: Literal["30d", "90d", "cycle"] = "30d", office_id: UUID | None = None
) -> QualityOverridesOut:
    """ADM-11 c: overrides by agent from the projection (Q-05-T07, DEC-96)."""
    from abacus.kernel.clock import now
    from abacus.modules.practice import overrides

    await _on(ctx)
    found = await overrides.overrides(ctx.tenant, await now(ctx.tenant), window, office_id)
    return QualityOverridesOut.model_validate(found)


@quality_router.get(
    f"{_Q}/agent-overrides/{{agent_key}}/reasons",
    action="quality.read",
    response_model=QualityReasonsOut,
    errors=(501,),
)
async def quality_override_reasons_route(agent_key: str, ctx: Ctx) -> QualityReasonsOut:
    """One agent's override reasons, most frequent first (Q-05-T07)."""
    from abacus.kernel.clock import now
    from abacus.modules.practice import overrides

    await _on(ctx)
    found = await overrides.override_reasons(ctx.tenant, await now(ctx.tenant), agent_key)
    return QualityReasonsOut.model_validate(
        {"agent_key": agent_key, "items": [{"reason_code": c, "count": n} for c, n in found]}
    )


@quality_router.get(
    f"{_Q}/accuracy", action="quality.read", response_model=QualityAccuracyOut, errors=(501,)
)
async def quality_accuracy_route(
    ctx: Ctx, cycle: int | None = None, office_id: UUID | None = None
) -> QualityAccuracyOut:
    """ADM-11 f: draft-vs-final over the cycle's filed returns (firm-wide; an office does not
    narrow it yet: returns carry no office)."""
    await _on(ctx)
    from abacus.kernel.clock import now
    from abacus.modules.practice.quality_dashboard import accuracy

    year = cycle if cycle is not None else (await now(ctx.tenant)).year
    return QualityAccuracyOut.model_validate(await accuracy(ctx.tenant, year))


@quality_router.get(
    f"{_Q}/cycles", action="quality.read", response_model=QualityCycleListOut, errors=(501,)
)
async def quality_cycles_route(ctx: Ctx) -> QualityCycleListOut:
    await _on(ctx)
    from abacus.modules.practice import inspections as svc

    rows = await svc.cycles(ctx.tenant)
    return QualityCycleListOut(items=[QualityCycleOut(
        cycle_id=r["id"], year=r["year"], as_of=r["as_of"], planned=r["planned"],
        in_progress=r["in_progress"], concluded=r["concluded"], findings_open=r["findings_open"],
    ) for r in cast(list[Any], rows)])  # Any: SQL rows  # fmt: skip


@quality_router.get(
    f"{_Q}/inspections",
    action="quality.read",
    response_model=QualityInspectionListOut,
    errors=(501,),
)
async def quality_inspections_route(
    ctx: Ctx,
    cycle: int | None = None,
    type: InspectionKind | None = None,
    inspector: UUID | None = None,
    status: InspectionStatus | None = None,
    cursor: str | None = None,
) -> QualityInspectionListOut:
    await _on(ctx)
    from abacus.modules.practice import inspections as svc

    del cursor, cycle
    rows = [r for r in await svc.inspections(ctx.tenant, None)
            if (type is None or r["kind"] == type) and (status is None or r["status"] == status)
            and (inspector is None or r["inspector_user_id"] == inspector)]  # fmt: skip
    return QualityInspectionListOut(
        items=[await _inspection_out(ctx, r) for r in rows], next_cursor=None
    )


@quality_router.get(
    f"{_Q}/inspection-candidates",
    action="inspection.plan",
    response_model=QualityCandidateListOut,
    errors=(501,),
)
async def quality_candidates_route(ctx: Ctx, cycle: int) -> QualityCandidateListOut:
    await _human(ctx, "inspection.plan")
    from abacus.modules.practice import inspections as svc

    async with tenant_session(ctx.tenant) as session:
        cycle_id = await session.scalar(
            text("SELECT id FROM qm_cycles WHERE year = :y"), {"y": cycle}
        )
    if cycle_id is None:
        raise NotFound("qm_cycle")
    version, found = await svc.candidates(ctx, cast(UUID, cycle_id))
    return QualityCandidateListOut(rule_version=version, items=[QualityCandidateOut(
        work_item_id=c.work_item_id, engagement_name=c.engagement_name, risk_score=c.risk_score,
        selected_because=c.selected_because, not_objective_user_ids=c.not_objective_user_ids,
    ) for c in found])  # fmt: skip


@quality_router.post(
    f"{_Q}/inspections",
    action="inspection.plan",
    response_model=QualityInspectionOut,
    status_code=201,
    errors=(409, 501),
)
async def quality_inspection_create_route(
    body: QualityInspectionIn, ctx: Ctx, key: IdempotencyKey
) -> QualityInspectionOut:
    """409 `inspector_not_objective` (AC-7); planning issues the inspector's grant (AC-8)."""
    await _human(ctx, "inspection.plan")
    from abacus.modules.practice import inspections as svc

    del key
    made = await svc.plan(
        ctx,
        cycle_id=body.cycle_id,
        work_item_id=body.work_item_id,
        kind=body.kind,
        inspector_user_id=body.inspector_user_id,
        due_on=body.due_on,
    )
    return await _inspection_by_id(ctx, made)


@quality_router.post(
    f"{_Q}/inspections/{{inspection_id}}/start",
    action="inspection.update",
    response_model=QualityInspectionOut,
    errors=(409, 501),
)
async def quality_inspection_start_route(
    inspection_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> QualityInspectionOut:
    await _human(ctx, "inspection.update")
    from abacus.modules.practice import inspections as svc

    del key
    await svc.start(ctx, inspection_id)
    return await _inspection_by_id(ctx, inspection_id)


@quality_router.post(
    f"{_Q}/inspections/{{inspection_id}}/conclude",
    action="inspection.update",
    response_model=QualityInspectionOut,
    errors=(409, 501),
)
async def quality_inspection_conclude_route(
    inspection_id: UUID, ctx: Ctx, key: IdempotencyKey
) -> QualityInspectionOut:
    """Concluding revokes the inspector's grant."""
    await _human(ctx, "inspection.update")
    from abacus.modules.practice import inspections as svc

    del key
    await svc.conclude(ctx, inspection_id)
    return await _inspection_by_id(ctx, inspection_id)


@quality_router.get(
    f"{_Q}/findings", action="quality.read", response_model=QualityFindingListOut, errors=(501,)
)
async def quality_findings_route(
    ctx: Ctx, cycle: int | None = None, status: FindingStatus | None = None
) -> QualityFindingListOut:
    await _on(ctx)
    from abacus.modules.practice import inspections as svc

    rows = await svc.findings(ctx.tenant, cycle, status)
    return QualityFindingListOut(items=[await _finding_out(r) for r in rows], next_cursor=None)


@quality_router.get(
    f"{_Q}/findings/{{finding_id}}",
    action="quality.read",
    response_model=QualityFindingOut,
    errors=(501,),
)
async def quality_finding_route(finding_id: UUID, ctx: Ctx) -> QualityFindingOut:
    await _on(ctx)
    return await _finding_by_id(ctx, finding_id)


@quality_router.post(
    f"{_Q}/findings",
    action="qm_finding.record",
    response_model=QualityFindingOut,
    status_code=201,
    errors=(409, 501),
)
async def quality_finding_create_route(
    body: QualityFindingIn, ctx: Ctx, key: IdempotencyKey
) -> QualityFindingOut:
    await _human(ctx, "qm_finding.record")
    from abacus.modules.practice import inspections as svc

    del key
    made = await svc.record_finding(
        ctx,
        cycle_id=body.cycle_id,
        inspection_id=body.inspection_id,
        title=body.title,
        owner_user_id=body.owner_user_id,
        due_on=body.due_on,
    )
    return await _finding_by_id(ctx, made)


@quality_router.patch(
    f"{_Q}/findings/{{finding_id}}",
    action="qm_finding.update",
    response_model=QualityFindingOut,
    errors=(409, 501),
)
async def quality_finding_patch_route(
    finding_id: UUID, body: QualityFindingPatchIn, ctx: Ctx
) -> QualityFindingOut:
    await _human(ctx, "qm_finding.update")
    from abacus.modules.practice import inspections as svc

    await svc.update_finding(
        ctx, finding_id, root_cause_category=body.root_cause_category, root_cause=body.root_cause,
        remediation=body.remediation, owner_user_id=body.owner_user_id, due_on=body.due_on,
        version=body.version,
    )  # fmt: skip
    return await _finding_by_id(ctx, finding_id)


@quality_router.post(
    f"{_Q}/findings/{{finding_id}}/evaluations",
    action="qm_finding.evaluate",
    response_model=QualityFindingOut,
    status_code=201,
    errors=(409, 501),
)
async def quality_finding_evaluate_route(
    finding_id: UUID, body: QualityEvaluationIn, ctx: Ctx, key: IdempotencyKey
) -> QualityFindingOut:
    """Human-only, insert-only; the QM owner (AC-9)."""
    await _human(ctx, "qm_finding.evaluate")
    from abacus.modules.practice import inspections as svc

    del key
    await svc.evaluate_finding(
        ctx, finding_id, evaluation=body.evaluation, rationale=body.rationale
    )
    return await _finding_by_id(ctx, finding_id)


@quality_router.post(
    f"{_Q}/findings/{{finding_id}}/remediate",
    action="qm_finding.remediate",
    response_model=QualityFindingOut,
    errors=(409, 501),
)
async def quality_finding_remediate_route(
    finding_id: UUID, body: QualityRemediateIn, ctx: Ctx, key: IdempotencyKey
) -> QualityFindingOut:
    await _human(ctx, "qm_finding.remediate")
    from abacus.modules.practice import inspections as svc

    del key
    await svc.remediate(ctx, finding_id, body.note)
    return await _finding_by_id(ctx, finding_id)


@quality_router.post(
    f"{_Q}/findings/{{finding_id}}/remediation-todos",
    action="todo.create",
    response_model=QualityTodoOut,
    status_code=201,
    errors=(501,),
)
async def quality_finding_todo_route(
    finding_id: UUID, body: QualityTodoIn, ctx: Ctx, key: IdempotencyKey
) -> QualityTodoOut:
    await _human(ctx, "todo.create")
    from abacus.modules.practice import inspections as svc

    del key
    todo_id = await svc.remediation_todo(
        ctx,
        finding_id,
        title=body.title,
        assignee_user_id=body.assignee_user_id,
        due_on=body.due_on,
    )
    return QualityTodoOut.model_validate({"todo_id": todo_id, "finding_id": finding_id})


@quality_router.get(
    f"{_Q}/evaluations/{{year}}",
    action="quality.read",
    response_model=QualityAnnualEvaluationOut,
    errors=(501,),
)
async def quality_evaluation_route(year: int, ctx: Ctx) -> QualityAnnualEvaluationOut:
    await _on(ctx)
    return await _evaluation_out(ctx, year)


@quality_router.patch(
    f"{_Q}/evaluations/{{year}}/checklist",
    action="quality.manage",
    response_model=QualityAnnualEvaluationOut,
    errors=(409, 501),
)
async def quality_evaluation_checklist_route(
    year: int, body: QualityChecklistIn, ctx: Ctx
) -> QualityAnnualEvaluationOut:
    await _human(ctx, "quality.manage")
    from abacus.modules.practice import inspections as svc

    await svc.save_checklist(ctx, year, dict(body.checklist))
    return await _evaluation_out(ctx, year)


@quality_router.post(
    f"{_Q}/evaluations/{{year}}/request-conclusion",
    action="quality.manage",
    response_model=QualityAnnualEvaluationOut,
    errors=(409, 501),
)
async def quality_evaluation_request_route(
    year: int, ctx: Ctx, key: IdempotencyKey
) -> QualityAnnualEvaluationOut:
    """Raises the firm-scope `qm_annual_evaluation` card; 409 `inspections_open`."""
    await _human(ctx, "quality.manage")
    from abacus.modules.practice import inspections as svc

    del key
    await svc.request_conclusion(ctx, year)
    return await _evaluation_out(ctx, year)


# --- Q-05-T18 (DEC-5827): the outs of inspections, findings and the evaluation -----------------


async def _person(user_id: UUID | None) -> QualityPersonOut:
    from abacus.modules.identity.api import display_names

    if user_id is None:
        return QualityPersonOut.model_validate({"user_id": None, "name": ""})
    return QualityPersonOut.model_validate(
        {"user_id": user_id, "name": (await display_names([user_id])).get(user_id, "")}
    )


async def _inspection_out(ctx: AuthContext, r: dict[str, object]) -> QualityInspectionOut:
    from abacus.modules.engagements.api import engagement_label

    label = await engagement_label(ctx.tenant, cast(UUID, r["inspected_engagement_id"]))
    return QualityInspectionOut(
        inspection_id=cast(UUID, r["id"]),
        ref=str(r["ref"]),
        work_item_id=cast(UUID, r["work_item_id"]),
        engagement_name="" if label is None else (label.client_entity_name or label.client_name),
        kind=cast(InspectionKind, r["kind"]),
        basis=cast(Any, r["basis"]),  # Any: a row value
        inspector=await _person(cast(UUID, r["inspector_user_id"])),
        status=cast(InspectionStatus, r["status"]),
        due_on=cast(Any, r["due_on"]),  # Any: a row value
    )


async def _inspection_by_id(ctx: AuthContext, inspection_id: UUID) -> QualityInspectionOut:
    from abacus.modules.practice import inspections as svc

    found = [r for r in await svc.inspections(ctx.tenant, None) if r["id"] == inspection_id]
    if not found:
        raise NotFound("inspection")
    return await _inspection_out(ctx, found[0])


async def _finding_out(r: dict[str, object]) -> QualityFindingOut:
    return QualityFindingOut.model_validate(
        {
            "finding_id": r["id"],
            "ref": r["ref"],
            "source": r["source"],
            "agent_key": r["agent_key"],
            "inspection_ref": r["inspection_ref"],
            "title": r["title"],
            "status": r["status"],
            "evaluation": r["evaluation"],
            "root_cause_category": r["root_cause_category"],
            "owner": None
            if r["owner_user_id"] is None
            else (await _person(cast(UUID, r["owner_user_id"]))).model_dump(),
            "due_on": r["due_on"],
            "raised_by_kind": r["raised_by_kind"],
            "version": r["version"],
        }
    )


async def _finding_by_id(ctx: AuthContext, finding_id: UUID) -> QualityFindingOut:
    from abacus.modules.practice import inspections as svc

    found = [r for r in await svc.findings(ctx.tenant, None, None) if r["id"] == finding_id]
    if not found:
        raise NotFound("qm_finding")
    return await _finding_out(found[0])


async def _evaluation_out(ctx: AuthContext, year: int) -> QualityAnnualEvaluationOut:
    from abacus.modules.practice import inspections as svc

    found = await svc.annual_evaluation(ctx.tenant, year)
    return QualityAnnualEvaluationOut(
        year=year,
        status=cast(Any, found["status"]),  # Any: a row value
        responsible=await _person(cast(UUID | None, found["responsible_user_id"])),
        decision_card_id=cast(UUID | None, found["decision_card_id"]),
        concluded_at=cast(Any, found["concluded_at"]),  # Any: a row value
        checklist=cast(dict[str, bool], found["checklist"]),
        inspections_open=int(cast(int, found["inspections_open"])),
    )


# --- S52 Q-05 sweep (DEC-5829): the register's outs ---------------------------------------------


async def _objective_out(
    o: dict[str, object], found: dict[str, list[dict[str, object]]]
) -> dict[str, object]:
    return {
        "objective_id": o["id"],
        "component": o["component"],
        "ref": o["ref"],
        "title": o["title"],
        "owner": None
        if o["owner_user_id"] is None
        else (await _person(cast(UUID, o["owner_user_id"]))).model_dump(),
        "health_flag": o["health_flag"],
        "risks": sum(1 for r in found["risks"] if r["objective_id"] == o["id"]),
        "responses": sum(1 for r in found["responses"] if r["objective_id"] == o["id"]),
        "version": o["version"],
    }


def _import_out(row: dict[str, object]) -> QualityImportOut:
    return QualityImportOut.model_validate(
        {
            "import_id": row["id"],
            "kind": row["kind"],
            "status": row["status"],
            "counts": row["counts"],
        }
    )
