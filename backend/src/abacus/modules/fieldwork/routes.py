"""Fieldwork routes (SPEC-037; TASK-083). Flag `fieldwork.procedures` gates starting and
selecting; reads follow `procedure.read`."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.fieldwork.completion import (
    AdjustmentView,
    LineIn,
    RepresentationList,
    add_representation,
    adjustments_for,
    propose_adjustment,
    record_adjustment_event,
    record_communication,
    remove_representation,
    representations_for,
    set_severity,
)
from abacus.modules.fieldwork.findings import (
    FindingView,
    Summary,
    findings_for,
    raise_finding,
    record_misstatement,
    summary_for,
)
from abacus.modules.fieldwork.findings import (
    search as search_findings,
)
from abacus.modules.fieldwork.flow import (
    FlowState,
    approve_sample,
    flow_state,
    request_selection_support,
    sign_items,
    waiting_for,
)
from abacus.modules.fieldwork.notes import NoteView, clear, notes_for, raise_note, respond
from abacus.modules.fieldwork.planning import (
    MaterialityVersionView,
    RiskIn,
    RiskView,
    approve_risk,
    decide_materiality,
    materiality_history,
    record_risk,
    risks_for,
)
from abacus.modules.fieldwork.service import (
    AccountsView,
    Basis,
    Defaults,
    Materiality,
    Pick,
    ProcedureView,
    accounts_of,
    add_picks,
    fieldwork_defaults,
    items_of,
    materiality_of,
    procedure_detail,
    procedures_of,
    request_selection,
    set_accounts,
    set_bands,
    set_fieldwork_defaults,
    set_materiality,
    set_parameters,
    start_procedure,
)
from abacus.modules.fieldwork.session import approve_plan, session_of
from abacus.modules.fieldwork.workpapers import (
    WorkpaperState,
    record_result,
    request_support,
    set_conclusion,
    sign_ready,
    sign_reviewed,
    workpaper_file,
    workpaper_state,
)
from abacus.modules.identity.api import (
    OWN,
    AbacusRouter,
    AuthContext,
    current_context,
    current_member,
)

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["fieldwork"])
firm_router = AbacusRouter(prefix="/v1/firm", tags=["fieldwork"])
Ctx = Annotated[AuthContext, Depends(current_context)]
Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]


Pct = Annotated[Decimal, Field(gt=0, le=100, max_digits=6, decimal_places=3)]


class BasisIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    amount: Annotated[Money, classified("confidential")]
    rate_pct: Annotated[Pct, classified("confidential")]
    performance_pct: Annotated[Pct, classified("confidential")]
    trivial_pct: Annotated[Pct, classified("confidential")]


class MaterialityIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    overall: Annotated[Money, classified("confidential")]
    performance: Annotated[Money, classified("confidential")]
    trivial: Annotated[Money, classified("confidential")]
    benchmark: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    basis: Annotated[
        BasisIn | None, Field(default=None), classified("confidential")
    ]  # SPEC-300 AC-1: code computes the amounts from it
    rationale: Annotated[
        str | None, Field(default=None, max_length=2000), classified("confidential")
    ]


class MaterialityOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    overall: Annotated[Decimal, classified("confidential")]
    performance: Annotated[Decimal, classified("confidential")]
    trivial: Annotated[Decimal, classified("confidential")]
    benchmark: Annotated[str, classified("confidential")]
    set_by: Annotated[UUID, classified("internal")]
    set_at: Annotated[datetime, classified("internal")]


def _materiality_out(m: Materiality) -> MaterialityOut:
    return MaterialityOut.model_validate(asdict(m))


@router.get("/materiality", action="procedure.read", response_model=MaterialityOut | None)
async def materiality_route(engagement_id: UUID, ctx: Ctx) -> MaterialityOut | None:
    found = await materiality_of(ctx, engagement_id)
    return _materiality_out(found) if found is not None else None


@router.put("/materiality", action="materiality.set", response_model=MaterialityOut)
async def set_materiality_route(
    engagement_id: UUID, body: MaterialityIn, ctx: Ctx
) -> MaterialityOut:
    """SPEC-037 Q3: entered by the partner or manager; nothing suggests it."""
    return _materiality_out(
        await set_materiality(
            ctx,
            engagement_id,
            overall=body.overall,
            performance=body.performance,
            trivial=body.trivial,
            benchmark=body.benchmark,
            basis=Basis(**body.basis.model_dump()) if body.basis else None,
            rationale=body.rationale,
        )
    )


class CriteriaIO(BaseModel):
    """The criteria's parameters (SPEC-037 Q6): firm defaults, or one procedure's."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    threshold_percent: Annotated[int, Field(ge=1, le=100), classified("internal")] = 100
    round_unit: Annotated[Decimal, Field(ge=0, le=1_000_000), classified("internal")] = Decimal(
        1000
    )
    window_days: Annotated[int, Field(ge=0, le=31), classified("internal")] = 3
    rare_count: Annotated[int, Field(ge=0, le=100), classified("internal")] = 5
    keywords: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=40)]],
        Field(max_length=50),
        classified("internal"),
    ] = []
    manual_kinds_extra: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=60)]],
        Field(max_length=20),
        classified("internal"),
    ] = []
    random_count: Annotated[int, Field(ge=0, le=200), classified("internal")] = 10


def _criteria_out(d: Defaults) -> CriteriaIO:
    return CriteriaIO(
        threshold_percent=d.threshold_percent,
        round_unit=d.round_unit,
        window_days=d.window_days,
        rare_count=d.rare_count,
        keywords=list(d.keywords),
        manual_kinds_extra=list(d.manual_kinds_extra),
        random_count=d.random_count,
    )


def _criteria_raw(body: CriteriaIO) -> dict[str, object]:
    raw = body.model_dump(mode="json")
    raw["round_unit"] = str(body.round_unit)
    return raw


@firm_router.get("/fieldwork-settings", action="methodology.read", response_model=CriteriaIO)
async def fieldwork_settings_route(ctx: Ctx) -> CriteriaIO:
    return _criteria_out(await fieldwork_defaults(ctx))


@firm_router.put("/fieldwork-settings", action="methodology.manage", response_model=CriteriaIO)
async def set_fieldwork_settings_route(body: CriteriaIO, ctx: Ctx) -> CriteriaIO:
    """SPEC-037 Q6: the firm's default criteria, copied into each new procedure."""
    return _criteria_out(await set_fieldwork_defaults(ctx, _criteria_raw(body)))


class PopulationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    gl_snapshot_id: Annotated[UUID, classified("internal")]
    entry_count: Annotated[int, classified("internal")]
    line_count: Annotated[int, classified("internal")]
    total_debit: Annotated[Decimal, classified("confidential")]
    total_credit: Annotated[Decimal, classified("confidential")]
    tied: Annotated[bool, classified("internal")]
    failure: Annotated[str | None, classified("internal")] = None


class SelectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    item_count: Annotated[int, classified("internal")]
    by_rule: Annotated[dict[str, int], classified("internal")]
    seed: Annotated[int, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class ProcedureOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    definition: Annotated[str, classified("internal")]
    definition_version: Annotated[int, classified("internal")]
    status: Annotated[str, classified("internal")]
    failure_code: Annotated[str | None, classified("internal")] = None
    parameters: Annotated[dict[str, object], classified("internal")]
    population: Annotated[PopulationOut | None, classified("internal")] = None
    selection: Annotated[SelectionOut | None, classified("internal")] = None
    not_performed: Annotated[list[str], classified("internal")] = []


def _procedure_out(v: ProcedureView) -> ProcedureOut:
    return ProcedureOut.model_validate({**asdict(v), "not_performed": list(v.not_performed)})


@router.get("/procedures", action="procedure.read", response_model=list[ProcedureOut])
async def procedures_route(engagement_id: UUID, ctx: Ctx) -> list[ProcedureOut]:
    return [_procedure_out(p) for p in await procedures_of(ctx, engagement_id)]


class StartIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    definition: Annotated[
        Literal["journal_entry_testing", "unrecorded_liabilities"], classified("internal")
    ] = "journal_entry_testing"


@router.post(
    "/procedures",
    action="procedure.run",
    response_model=ProcedureOut,
    status_code=201,
    errors=(409,),
)
async def start_procedure_route(
    engagement_id: UUID, ctx: Ctx, body: StartIn | None = None
) -> ProcedureOut:
    """SPEC-037, SPEC-038: start a procedure (once per engagement and definition)."""
    chosen = body.definition if body is not None else "journal_entry_testing"
    return _procedure_out(await start_procedure(ctx, engagement_id, chosen))


@router.get("/procedures/{procedure_id}", action="procedure.read", response_model=ProcedureOut)
async def procedure_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> ProcedureOut:
    return _procedure_out(await procedure_detail(ctx, engagement_id, procedure_id))


@router.put(
    "/procedures/{procedure_id}/parameters",
    action="procedure.configure",
    response_model=ProcedureOut,
    errors=(409,),
)
async def set_parameters_route(
    engagement_id: UUID, procedure_id: UUID, body: CriteriaIO, ctx: Ctx
) -> ProcedureOut:
    return _procedure_out(
        await set_parameters(ctx, engagement_id, procedure_id, _criteria_raw(body))
    )


class PickIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    posted_on: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$"), classified("internal")]
    kind: Annotated[str, Field(max_length=60), classified("confidential")] = ""
    reference: Annotated[str, Field(max_length=100), classified("confidential")] = ""
    counterparty: Annotated[str, Field(max_length=200), classified("confidential")] = ""
    reason: Annotated[str, Field(min_length=1, max_length=500), classified("confidential")]


class PicksIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    picks: Annotated[list[PickIn], Field(min_length=1, max_length=50), classified("internal")]


@router.post(
    "/procedures/{procedure_id}/picks",
    action="procedure.run",
    response_model=ProcedureOut,
    status_code=201,
    errors=(409,),
)
async def add_picks_route(
    engagement_id: UUID, procedure_id: UUID, body: PicksIn, ctx: Ctx
) -> ProcedureOut:
    """A person's own picks, each with a reason; they join the next selection."""
    picks = [
        Pick((p.posted_on, p.kind, p.reference, "" if p.reference else p.counterparty), p.reason)
        for p in body.picks
    ]
    return _procedure_out(await add_picks(ctx, engagement_id, procedure_id, picks))


@router.post(
    "/procedures/{procedure_id}/select",
    action="procedure.run",
    response_model=ProcedureOut,
    status_code=202,
    errors=(409,),
)
async def select_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> ProcedureOut:
    """SPEC-037 AC-1, AC-3: build the population and select, in the background."""
    return _procedure_out(await request_selection(ctx, engagement_id, procedure_id))


class ItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID | None, classified("internal")] = None
    result: Annotated[str | None, classified("confidential")] = None
    note: Annotated[str | None, classified("confidential")] = None
    evidence_version_ids: Annotated[list[UUID], classified("internal")] = []
    support_requested: Annotated[bool, classified("internal")] = False
    position: Annotated[int, classified("internal")]
    posted_on: Annotated[str, classified("internal")]
    kind: Annotated[str, classified("confidential")]
    reference: Annotated[str, classified("confidential")]
    counterparty: Annotated[str, classified("restricted")]
    accounts: Annotated[list[str], classified("confidential")]
    amount: Annotated[Decimal, classified("restricted")]
    descriptions: Annotated[list[str], classified("restricted")]
    rules: Annotated[list[str], classified("internal")]
    reason: Annotated[str | None, classified("confidential")] = None
    band: Annotated[int | None, classified("internal")] = None
    recorded_bill_reference: Annotated[str | None, classified("confidential")] = None
    recorded_bill_date: Annotated[str | None, classified("internal")] = None
    adopted: Annotated[bool, classified("internal")] = False  # SPEC-044 (TASK-109)
    relates_to_year: Annotated[Literal["yes", "no", "unclear"] | None, classified("internal")] = (
        None
    )


@router.get(
    "/procedures/{procedure_id}/items", action="procedure.read", response_model=list[ItemOut]
)
async def items_route(
    engagement_id: UUID,
    procedure_id: UUID,
    ctx: Ctx,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ItemOut]:
    return [
        ItemOut.model_validate(
            {
                **asdict(i),
                "accounts": list(i.accounts),
                "descriptions": list(i.descriptions),
                "rules": list(i.rules),
                "evidence_version_ids": list(i.evidence_version_ids),
            }
        )
        for i in await items_of(ctx, engagement_id, procedure_id, offset=offset, limit=limit)
    ]


# --- Results, support, conclusion and the workpaper (SPEC-037; TASK-084) -----------------------


class ResultIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    result: Annotated[Literal["supported", "exception", "not_tested"], classified("internal")]
    note: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None
    evidence_version_ids: Annotated[list[UUID], Field(max_length=20), classified("internal")] = []
    relates_to_year: Annotated[Literal["yes", "no", "unclear"] | None, classified("internal")] = (
        None  # SPEC-038
    )


class DoneOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Annotated[bool, classified("internal")] = True


@router.put(
    "/procedures/{procedure_id}/items/{item_id}/result",
    action="procedure.run",
    response_model=DoneOut,
)
async def result_route(
    engagement_id: UUID, procedure_id: UUID, item_id: UUID, body: ResultIn, ctx: Ctx
) -> DoneOut:
    """SPEC-037 AC-4: a person's result on a selected entry (appended; the newest counts)."""
    await record_result(
        ctx,
        engagement_id,
        procedure_id,
        item_id,
        result=body.result,
        note=body.note,
        evidence_ids=body.evidence_version_ids,
        relates_to_year=body.relates_to_year,
    )
    return DoneOut()


class SupportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]


@router.post(
    "/procedures/{procedure_id}/items/{item_id}/request-support",
    action="procedure.run",
    response_model=SupportOut,
    status_code=201,
)
async def request_support_route(
    engagement_id: UUID, procedure_id: UUID, item_id: UUID, ctx: Ctx
) -> SupportOut:
    """Ask the client for an entry's support: an ordinary request, linked to the entry."""
    made = await request_support(ctx, engagement_id, procedure_id, item_id)
    return SupportOut(request_item_id=made)


class ConclusionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=4000), classified("confidential")]


@router.put(
    "/procedures/{procedure_id}/conclusion", action="procedure.run", response_model=DoneOut
)
async def conclusion_route(
    engagement_id: UUID, procedure_id: UUID, body: ConclusionIn, ctx: Ctx
) -> DoneOut:
    await set_conclusion(ctx, engagement_id, procedure_id, body.text)
    return DoneOut()


class SignatureOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["ready", "reviewed"], classified("internal")]
    signed_by: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    role: Annotated[str, classified("internal")]
    signed_at: Annotated[datetime, classified("internal")]


class VersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Annotated[int, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    signatures: Annotated[list[SignatureOut], classified("internal")]


class WorkpaperOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[Literal["not_started", "draft", "ready", "reviewed"], classified("internal")]
    entries: Annotated[int, classified("internal")]
    with_result: Annotated[int, classified("internal")]
    exceptions: Annotated[int, classified("internal")]
    conclusion: Annotated[str, classified("confidential")]
    versions: Annotated[list[VersionOut], classified("internal")]


def _workpaper_out(state: WorkpaperState) -> WorkpaperOut:
    return WorkpaperOut.model_validate(asdict(state))


@router.get(
    "/procedures/{procedure_id}/workpaper", action="procedure.read", response_model=WorkpaperOut
)
async def workpaper_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> WorkpaperOut:
    return _workpaper_out(await workpaper_state(ctx, engagement_id, procedure_id))


@router.post(
    "/procedures/{procedure_id}/workpaper/sign-ready",
    action="workpaper.sign_ready",
    response_model=WorkpaperOut,
    status_code=201,
    errors=(409,),
)
async def sign_ready_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> WorkpaperOut:
    """ADR-131: the preparer signs the current state; it becomes the next version."""
    return _workpaper_out(await sign_ready(ctx, engagement_id, procedure_id))


@router.post(
    "/procedures/{procedure_id}/workpaper/sign-reviewed",
    action="workpaper.sign_reviewed",
    response_model=WorkpaperOut,
    status_code=201,
    errors=(409,),
)
async def sign_reviewed_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> WorkpaperOut:
    """ADR-131: another person signs the latest ready version, while nothing has changed."""
    return _workpaper_out(await sign_reviewed(ctx, engagement_id, procedure_id))


@router.get(
    "/procedures/{procedure_id}/workpaper/file",
    action="procedure.read",
    response_model=bytes,
    errors=(409,),
)
async def workpaper_file_route(
    engagement_id: UUID,
    procedure_id: UUID,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> Response:
    """The current draft, or a signed version (re-rendered and checked, D1), as an attachment."""
    content, name = await workpaper_file(ctx, engagement_id, procedure_id, version)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


# --- Unrecorded liabilities: bands and accounts (SPEC-038; TASK-086, TASK-087) -----------------


class BandIO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    until_day: Annotated[int | None, Field(ge=1, le=366), classified("internal")] = None
    percent: Annotated[int, Field(ge=1, le=100), classified("internal")]


class BandsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bands: Annotated[list[BandIO], Field(min_length=1, max_length=6), classified("internal")]


@router.put(
    "/procedures/{procedure_id}/bands",
    action="procedure.configure",
    response_model=ProcedureOut,
    errors=(409,),
)
async def bands_route(
    engagement_id: UUID, procedure_id: UUID, body: BandsIn, ctx: Ctx
) -> ProcedureOut:
    """SPEC-038 Q4: the timing bands, as % of performance materiality."""
    raw = [b.model_dump() for b in body.bands]
    return _procedure_out(await set_bands(ctx, engagement_id, procedure_id, raw))


class AccountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("confidential")]
    name: Annotated[str, classified("confidential")]


class AccountsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    accounts: Annotated[list[AccountOut], classified("confidential")]
    bank: Annotated[list[str], classified("confidential")]
    payables: Annotated[list[str], classified("confidential")]
    suggested_bank: Annotated[list[str], classified("confidential")]
    suggested_payables: Annotated[list[str], classified("confidential")]
    confirmed: Annotated[bool, classified("internal")]


class AccountsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bank: Annotated[list[str], Field(min_length=1, max_length=50), classified("confidential")]
    payables: Annotated[list[str], Field(min_length=1, max_length=50), classified("confidential")]


def _accounts_out(v: AccountsView) -> AccountsOut:
    return AccountsOut(
        accounts=[AccountOut(code=c, name=n) for c, n in v.accounts],
        bank=list(v.bank),
        payables=list(v.payables),
        suggested_bank=list(v.suggested_bank),
        suggested_payables=list(v.suggested_payables),
        confirmed=v.confirmed,
    )


@router.get("/fieldwork/accounts", action="procedure.read", response_model=AccountsOut)
async def accounts_route(engagement_id: UUID, ctx: Ctx) -> AccountsOut:
    """SPEC-038 Q3, Q5: confirmed bank and payables accounts, with suggestions by name."""
    return _accounts_out(await accounts_of(ctx, engagement_id))


@router.put("/fieldwork/accounts", action="procedure.configure", response_model=AccountsOut)
async def set_accounts_route(engagement_id: UUID, body: AccountsIn, ctx: Ctx) -> AccountsOut:
    return _accounts_out(await set_accounts(ctx, engagement_id, body.bank, body.payables))


# --- The flow (SPEC-040; TASK-100) --------------------------------------------------------------


class ApprovalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    approved_by: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    approved_at: Annotated[datetime, classified("internal")]
    note: Annotated[str | None, classified("confidential")]


class RowSignOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    signed_by: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    initials: Annotated[str, classified("internal")]
    signed_at: Annotated[datetime, classified("internal")]
    stale: Annotated[bool, classified("internal")]


class RowStateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    item_id: Annotated[UUID, classified("internal")]
    prepared: Annotated[RowSignOut | None, classified("internal")]
    reviewed: Annotated[RowSignOut | None, classified("internal")]


class FlowStepOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    state: Annotated[Literal["done", "current", "todo"], classified("internal")]


class FlowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    approval: Annotated[ApprovalOut | None, classified("internal")]
    steps: Annotated[list[FlowStepOut], classified("internal")]
    exceptions: Annotated[int, classified("internal")]
    needs_input: Annotated[int, classified("internal")]
    passed: Annotated[int, classified("internal")]
    rows: Annotated[list[RowStateOut], classified("internal")]


def _flow_out(state: FlowState) -> FlowOut:
    return FlowOut.model_validate(asdict(state))


@router.get("/procedures/{procedure_id}/flow", action="procedure.read", response_model=FlowOut)
async def flow_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> FlowOut:
    """SPEC-040 AC-11, AC-12: the procedure's steps, triage counts and row sign-offs."""
    return _flow_out(await flow_state(ctx, engagement_id, procedure_id))


class ApproveIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    note: Annotated[str | None, Field(default=None, max_length=1000), classified("confidential")]


@router.post(
    "/procedures/{procedure_id}/approve",
    action="sample.approve",
    response_model=FlowOut,
    status_code=201,
    errors=(409,),
)
async def approve_route(
    engagement_id: UUID, procedure_id: UUID, body: ApproveIn, ctx: Ctx
) -> FlowOut:
    """SPEC-040 AC-1: a manager or the engagement partner approves the current selection."""
    await approve_sample(ctx, engagement_id, procedure_id, body.note)
    return _flow_out(await flow_state(ctx, engagement_id, procedure_id))


class SelectionSupportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    items: Annotated[int, classified("internal")]


@router.post(
    "/procedures/{procedure_id}/request-support",
    action="procedure.run",
    response_model=SelectionSupportOut,
    status_code=201,
    errors=(409,),
)
async def request_selection_support_route(
    engagement_id: UUID, procedure_id: UUID, ctx: Ctx
) -> SelectionSupportOut:
    """SPEC-040 AC-4: one request to the client listing every item still without one."""
    made, items = await request_selection_support(ctx, engagement_id, procedure_id)
    return SelectionSupportOut(request_item_id=made, items=items)


class SignItemsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), classified("internal")]


class SignedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: Annotated[int, classified("internal")]


@router.post(
    "/procedures/{procedure_id}/items/sign-prepared",
    action="item.sign_prepared",
    response_model=SignedOut,
    status_code=201,
    errors=(409,),
)
async def sign_prepared_route(
    engagement_id: UUID, procedure_id: UUID, body: SignItemsIn, ctx: Ctx
) -> SignedOut:
    """SPEC-040 AC-6, AC-9: the preparer signs rows, each on its current result."""
    return SignedOut(
        rows=await sign_items(ctx, engagement_id, procedure_id, "prepared", body.item_ids)
    )


@router.post(
    "/procedures/{procedure_id}/items/sign-reviewed",
    action="item.sign_reviewed",
    response_model=SignedOut,
    status_code=201,
    errors=(409,),
)
async def sign_reviewed_items_route(
    engagement_id: UUID, procedure_id: UUID, body: SignItemsIn, ctx: Ctx
) -> SignedOut:
    """SPEC-040 AC-7: a reviewer who isn't the row's preparer signs rows."""
    return SignedOut(
        rows=await sign_items(ctx, engagement_id, procedure_id, "reviewed", body.item_ids)
    )


class WaitingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    procedure_id: Annotated[UUID, classified("internal")]
    definition: Annotated[str, classified("internal")]
    kind: Annotated[
        Literal["approve_sample", "prepare_rows", "review_rows", "respond_notes", "clear_notes"],
        classified("internal"),
    ]
    count: Annotated[int, classified("internal")]


Member = Annotated[AuthContext, Depends(current_member)]


@firm_router.get("/waiting/fieldwork", action=OWN, response_model=list[WaitingOut])
async def fieldwork_waiting_route(ctx: Member) -> list[WaitingOut]:
    """TASK-102: samples to approve and rows to sign, on the caller's engagements."""
    return [WaitingOut.model_validate(asdict(w)) for w in await waiting_for(ctx)]


# --- Review notes (SPEC-041; TASK-103) ----------------------------------------------------------


class NoteEntryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["raised", "responded", "reopened", "cleared"], classified("internal")]
    body: Annotated[str | None, classified("confidential")]
    by: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class NoteOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    item_id: Annotated[UUID | None, classified("internal")]
    state: Annotated[Literal["open", "responded", "cleared"], classified("internal")]
    raised_by: Annotated[UUID, classified("internal")]
    raised_by_name: Annotated[str, classified("internal")]
    raised_at: Annotated[datetime, classified("internal")]
    thread: Annotated[list[NoteEntryOut], classified("confidential")]


def _notes_out(notes: list[NoteView]) -> list[NoteOut]:
    return [NoteOut.model_validate(asdict(n)) for n in notes]


@router.get(
    "/procedures/{procedure_id}/notes", action="procedure.read", response_model=list[NoteOut]
)
async def notes_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> list[NoteOut]:
    """SPEC-041 AC-7: the procedure's review notes with their threads."""
    return _notes_out(await notes_for(ctx, engagement_id, procedure_id))


class NoteIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    item_id: Annotated[UUID | None, Field(default=None), classified("internal")]
    body: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]


@router.post(
    "/procedures/{procedure_id}/notes",
    action="review_note.raise",
    response_model=list[NoteOut],
    status_code=201,
    errors=(409,),
)
async def raise_note_route(
    engagement_id: UUID, procedure_id: UUID, body: NoteIn, ctx: Ctx
) -> list[NoteOut]:
    """SPEC-041 AC-1: a reviewer's note on a row, or on the workpaper."""
    await raise_note(ctx, engagement_id, procedure_id, body.item_id, body.body)
    return _notes_out(await notes_for(ctx, engagement_id, procedure_id))


class ReplyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]


@router.post(
    "/procedures/{procedure_id}/notes/{note_id}/respond",
    action="review_note.respond",
    response_model=list[NoteOut],
    status_code=201,
    errors=(409,),
)
async def respond_note_route(
    engagement_id: UUID, procedure_id: UUID, note_id: UUID, body: ReplyIn, ctx: Ctx
) -> list[NoteOut]:
    """SPEC-041 AC-2: the preparer responds; the raiser's reply reopens it."""
    await respond(ctx, engagement_id, procedure_id, note_id, body.body)
    return _notes_out(await notes_for(ctx, engagement_id, procedure_id))


@router.post(
    "/procedures/{procedure_id}/notes/{note_id}/clear",
    action="review_note.clear",
    response_model=list[NoteOut],
    status_code=201,
    errors=(409,),
)
async def clear_note_route(
    engagement_id: UUID, procedure_id: UUID, note_id: UUID, ctx: Ctx
) -> list[NoteOut]:
    """SPEC-041 AC-3: the raiser clears it."""
    await clear(ctx, engagement_id, procedure_id, note_id)
    return _notes_out(await notes_for(ctx, engagement_id, procedure_id))


# --- Findings (SPEC-043; TASK-107) ---------------------------------------------------------------


class MisstatementOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["factual", "judgmental", "projected"], classified("internal")]
    amount: Annotated[Decimal, classified("confidential")]
    account_code: Annotated[str | None, classified("confidential")]
    corrected: Annotated[bool, classified("internal")]
    recorded_by_name: Annotated[str, classified("internal")]
    recorded_at: Annotated[datetime, classified("internal")]


Severity = Literal["deficiency", "significant_deficiency", "material_weakness"]


class DeficiencyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[Literal["proposed", "concluded", "communicated"], classified("internal")]
    proposed: Annotated[Severity | None, classified("confidential")]
    proposed_by_name: Annotated[str | None, classified("internal")]
    concluded: Annotated[Severity | None, classified("confidential")]
    concluded_by_name: Annotated[str | None, classified("internal")]
    concluded_at: Annotated[datetime | None, classified("internal")]
    conclusion_rationale: Annotated[str | None, classified("confidential")]
    communicated_on: Annotated[date | None, classified("internal")]
    communicated_to: Annotated[str | None, classified("confidential")]


class FindingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    description: Annotated[str | None, classified("confidential")]
    procedure_id: Annotated[UUID | None, classified("internal")]
    item_id: Annotated[UUID | None, classified("internal")]
    raised_by_name: Annotated[str, classified("internal")]
    raised_at: Annotated[datetime, classified("internal")]
    misstatement: Annotated[MisstatementOut | None, classified("confidential")]
    deficiency: Annotated[DeficiencyOut | None, classified("confidential")]  # SPEC-301


def _findings_out(found: list[FindingView]) -> list[FindingOut]:
    return [FindingOut.model_validate(asdict(f)) for f in found]


@router.get("/findings", action="procedure.read", response_model=list[FindingOut])
async def findings_route(engagement_id: UUID, ctx: Ctx) -> list[FindingOut]:
    """SPEC-043 AC-5: the findings register."""
    return _findings_out(await findings_for(ctx, engagement_id))


class FindingIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    description: Annotated[
        str | None, Field(default=None, max_length=2000), classified("confidential")
    ]
    procedure_id: Annotated[UUID | None, Field(default=None), classified("internal")]
    item_id: Annotated[UUID | None, Field(default=None), classified("internal")]


@router.post(
    "/findings",
    action="finding.raise",
    response_model=list[FindingOut],
    status_code=201,
)
async def raise_finding_route(engagement_id: UUID, body: FindingIn, ctx: Ctx) -> list[FindingOut]:
    """SPEC-043 AC-1: raise a finding, from a fieldwork row or by hand."""
    await raise_finding(
        ctx, engagement_id, body.title, body.description, body.procedure_id, body.item_id
    )
    return _findings_out(await findings_for(ctx, engagement_id))


class MisstatementIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[Literal["factual", "judgmental", "projected"], classified("internal")]
    amount: Annotated[Decimal, Field(max_digits=18, decimal_places=2), classified("confidential")]
    account_code: Annotated[
        str | None, Field(default=None, max_length=64), classified("confidential")
    ]
    corrected: Annotated[bool, Field(default=False), classified("internal")]


@router.post(
    "/findings/{finding_id}/misstatement",
    action="misstatement.set",
    response_model=list[FindingOut],
    status_code=201,
)
async def misstatement_route(
    engagement_id: UUID, finding_id: UUID, body: MisstatementIn, ctx: Ctx
) -> list[FindingOut]:
    """SPEC-043 AC-2: record (or revise) the finding's misstatement."""
    await record_misstatement(
        ctx, engagement_id, finding_id, body.kind, body.amount, body.account_code, body.corrected
    )
    return _findings_out(await findings_for(ctx, engagement_id))


class KindTotalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[str, classified("internal")]
    count: Annotated[int, classified("internal")]
    total: Annotated[Decimal, classified("confidential")]


class SummaryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    materiality_set: Annotated[bool, classified("internal")]
    overall: Annotated[Decimal | None, classified("confidential")]
    performance: Annotated[Decimal | None, classified("confidential")]
    trivial: Annotated[Decimal | None, classified("confidential")]
    by_kind: Annotated[list[KindTotalOut], classified("confidential")]
    total: Annotated[Decimal, classified("confidential")]
    position: Annotated[
        Literal["below_performance", "at_or_above_performance", "at_or_above_overall", "unknown"],
        classified("internal"),
    ]


@router.get("/findings/summary", action="procedure.read", response_model=SummaryOut)
async def findings_summary_route(engagement_id: UUID, ctx: Ctx) -> SummaryOut:
    """SPEC-043 AC-3: the summary of uncorrected misstatements, computed by code."""
    found: Summary = await summary_for(ctx, engagement_id)
    return SummaryOut.model_validate(asdict(found))


# --- Completion: severity, proposed entries, representations (SPEC-301; TASK-302) ---------------


class SeverityIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: Annotated[Severity, classified("confidential")]
    rationale: Annotated[
        str | None, Field(default=None, max_length=2000), classified("confidential")
    ]


@router.post(
    "/findings/{finding_id}/severity/propose",
    action="finding.propose_severity",
    response_model=list[FindingOut],
    status_code=201,
)
async def propose_severity_route(
    engagement_id: UUID, finding_id: UUID, body: SeverityIn, ctx: Ctx
) -> list[FindingOut]:
    """SPEC-301 AC-1: propose a deficiency's severity."""
    await set_severity(ctx, engagement_id, finding_id, "proposed", body.severity, body.rationale)
    return _findings_out(await findings_for(ctx, engagement_id))


@router.post(
    "/findings/{finding_id}/severity/conclude",
    action="finding.conclude_severity",
    response_model=list[FindingOut],
    status_code=201,
)
async def conclude_severity_route(
    engagement_id: UUID, finding_id: UUID, body: SeverityIn, ctx: Ctx
) -> list[FindingOut]:
    """SPEC-301 AC-2: the engagement partner concludes the severity, with a rationale."""
    await set_severity(ctx, engagement_id, finding_id, "concluded", body.severity, body.rationale)
    return _findings_out(await findings_for(ctx, engagement_id))


class CommunicationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    communicated_on: Annotated[date, classified("internal")]
    recipients: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]


@router.post(
    "/findings/{finding_id}/communicated",
    action="finding.communicate",
    response_model=list[FindingOut],
    status_code=201,
)
async def communicated_route(
    engagement_id: UUID, finding_id: UUID, body: CommunicationIn, ctx: Ctx
) -> list[FindingOut]:
    """SPEC-301 AC-3: record when and to whom a concluded deficiency was communicated."""
    await record_communication(
        ctx, engagement_id, finding_id, body.communicated_on, body.recipients
    )
    return _findings_out(await findings_for(ctx, engagement_id))


Amount = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class LineBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    account_code: Annotated[str, Field(min_length=1, max_length=64), classified("confidential")]
    debit: Annotated[Amount, Field(default=Decimal(0)), classified("confidential")]
    credit: Annotated[Amount, Field(default=Decimal(0)), classified("confidential")]


class AdjustmentIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[Literal["aje", "rje"], classified("internal")]
    description: Annotated[str, Field(min_length=1, max_length=500), classified("confidential")]
    finding_id: Annotated[UUID | None, Field(default=None), classified("internal")]
    lines: Annotated[
        list[LineBody], Field(min_length=2, max_length=50), classified("confidential")
    ]


class LineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("confidential")]
    debit: Annotated[Decimal, classified("confidential")]
    credit: Annotated[Decimal, classified("confidential")]


class AdjustmentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    ref: Annotated[str, classified("internal")]
    kind: Annotated[Literal["aje", "rje"], classified("internal")]
    description: Annotated[str, classified("confidential")]
    finding_id: Annotated[UUID | None, classified("internal")]
    lines: Annotated[list[LineOut], classified("confidential")]
    total: Annotated[Decimal, classified("confidential")]
    status: Annotated[
        Literal["proposed", "approved", "client_accepted", "client_declined"],
        classified("internal"),
    ]
    raised_by_name: Annotated[str, classified("internal")]
    raised_at: Annotated[datetime, classified("internal")]
    approved_by_name: Annotated[str | None, classified("internal")]
    response_note: Annotated[str | None, classified("confidential")]


def _adjustments_out(found: list[AdjustmentView]) -> list[AdjustmentOut]:
    return [AdjustmentOut.model_validate(asdict(a)) for a in found]


@router.get("/adjustments", action="procedure.read", response_model=list[AdjustmentOut])
async def adjustments_route(engagement_id: UUID, ctx: Ctx) -> list[AdjustmentOut]:
    """SPEC-301 AC-6: the proposed entries."""
    return _adjustments_out(await adjustments_for(ctx, engagement_id))


@router.post(
    "/adjustments",
    action="adjustment.propose",
    response_model=list[AdjustmentOut],
    status_code=201,
)
async def propose_adjustment_route(
    engagement_id: UUID, body: AdjustmentIn, ctx: Ctx
) -> list[AdjustmentOut]:
    """SPEC-301 AC-4: propose an entry; debits equal credits."""
    await propose_adjustment(
        ctx,
        engagement_id,
        body.kind,
        body.description,
        body.finding_id,
        [LineIn(x.account_code, x.debit, x.credit) for x in body.lines],
    )
    return _adjustments_out(await adjustments_for(ctx, engagement_id))


@router.post(
    "/adjustments/{adjustment_id}/approve",
    action="adjustment.approve",
    response_model=list[AdjustmentOut],
    status_code=201,
)
async def approve_adjustment_route(
    engagement_id: UUID, adjustment_id: UUID, ctx: Ctx
) -> list[AdjustmentOut]:
    """SPEC-301 AC-5: a manager or the partner approves the entry."""
    await record_adjustment_event(ctx, engagement_id, adjustment_id, "approved", None)
    return _adjustments_out(await adjustments_for(ctx, engagement_id))


class ClientAnswerIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    accepted: Annotated[bool, classified("internal")]
    note: Annotated[str | None, Field(default=None, max_length=1000), classified("confidential")]


@router.post(
    "/adjustments/{adjustment_id}/client-answer",
    action="adjustment.record_response",
    response_model=list[AdjustmentOut],
    status_code=201,
)
async def client_answer_route(
    engagement_id: UUID, adjustment_id: UUID, body: ClientAnswerIn, ctx: Ctx
) -> list[AdjustmentOut]:
    """SPEC-301 AC-5: the client accepted the entry, or declined it (passed)."""
    kind = "client_accepted" if body.accepted else "client_declined"
    await record_adjustment_event(ctx, engagement_id, adjustment_id, kind, body.note)
    return _adjustments_out(await adjustments_for(ctx, engagement_id))


class RepresentationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    body: Annotated[str, classified("confidential")]
    finding_id: Annotated[UUID | None, classified("internal")]
    adjustment_id: Annotated[UUID | None, classified("internal")]
    raised_by_name: Annotated[str, classified("internal")]
    raised_at: Annotated[datetime, classified("internal")]


class RepresentationGapOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["finding", "adjustment"], classified("internal")]
    id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]


class RepresentationListOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[RepresentationOut], classified("confidential")]
    passed: Annotated[list[str], classified("internal")]
    gaps: Annotated[list[RepresentationGapOut], classified("confidential")]


def _reps_out(found: RepresentationList) -> RepresentationListOut:
    return RepresentationListOut.model_validate(asdict(found))


@router.get("/representations", action="procedure.read", response_model=RepresentationListOut)
async def representations_route(engagement_id: UUID, ctx: Ctx) -> RepresentationListOut:
    """SPEC-301 AC-7, AC-8: the representation list and what still lacks one."""
    return _reps_out(await representations_for(ctx, engagement_id))


class RepresentationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]
    finding_id: Annotated[UUID | None, Field(default=None), classified("internal")]
    adjustment_id: Annotated[UUID | None, Field(default=None), classified("internal")]


@router.post(
    "/representations",
    action="representation.edit",
    response_model=RepresentationListOut,
    status_code=201,
)
async def add_representation_route(
    engagement_id: UUID, body: RepresentationIn, ctx: Ctx
) -> RepresentationListOut:
    """SPEC-301 AC-7: add a specific representation."""
    await add_representation(ctx, engagement_id, body.body, body.finding_id, body.adjustment_id)
    return _reps_out(await representations_for(ctx, engagement_id))


@router.post(
    "/representations/{representation_id}/remove",
    action="representation.edit",
    response_model=RepresentationListOut,
    status_code=201,
)
async def remove_representation_route(
    engagement_id: UUID, representation_id: UUID, ctx: Ctx
) -> RepresentationListOut:
    """SPEC-301 AC-7: take a representation off the list (the record stays)."""
    await remove_representation(ctx, engagement_id, representation_id)
    return _reps_out(await representations_for(ctx, engagement_id))


# --- Planning: materiality decision and risks (SPEC-300; TASK-301) ------------------------------


class MaterialityVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]
    status: Annotated[Literal["proposed", "decided", "superseded"], classified("internal")]
    overall: Annotated[Decimal, classified("confidential")]
    performance: Annotated[Decimal, classified("confidential")]
    trivial: Annotated[Decimal, classified("confidential")]
    benchmark: Annotated[str, classified("confidential")]
    basis_amount: Annotated[Decimal | None, classified("confidential")]
    rate_pct: Annotated[Decimal | None, classified("confidential")]
    performance_pct: Annotated[Decimal | None, classified("confidential")]
    trivial_pct: Annotated[Decimal | None, classified("confidential")]
    rationale: Annotated[str | None, classified("confidential")]
    set_by_name: Annotated[str, classified("internal")]
    set_at: Annotated[datetime, classified("internal")]
    decided_by_name: Annotated[str | None, classified("internal")]
    decided_at: Annotated[datetime | None, classified("internal")]
    decision_rationale: Annotated[str | None, classified("confidential")]


def _versions_out(found: list[MaterialityVersionView]) -> list[MaterialityVersionOut]:
    return [MaterialityVersionOut.model_validate(asdict(v)) for v in found]


@router.get(
    "/materiality/versions", action="procedure.read", response_model=list[MaterialityVersionOut]
)
async def materiality_versions_route(engagement_id: UUID, ctx: Ctx) -> list[MaterialityVersionOut]:
    """SPEC-300 AC-3: every materiality version, newest first, with its decision."""
    return _versions_out(await materiality_history(ctx, engagement_id))


class DecisionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rationale: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]


@router.post(
    "/materiality/decide",
    action="materiality.decide",
    response_model=list[MaterialityVersionOut],
    status_code=201,
)
async def decide_materiality_route(
    engagement_id: UUID, body: DecisionIn, ctx: Ctx
) -> list[MaterialityVersionOut]:
    """SPEC-300 AC-2: the engagement partner decides the newest version."""
    await decide_materiality(ctx, engagement_id, body.rationale)
    return _versions_out(await materiality_history(ctx, engagement_id))


RiskLevel = Literal["financial_statement", "assertion"]
Rating = Literal["low", "moderate", "high"]
ControlRating = Literal["low", "moderate", "high", "maximum"]
Fraud = Literal["none", "presumed", "rebuttal"]
Assertion = Literal[
    "existence",
    "completeness",
    "accuracy",
    "valuation",
    "cut_off",
    "rights_obligations",
    "presentation",
]


class RiskBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    area: Annotated[str, Field(min_length=1, max_length=120), classified("confidential")]
    level: Annotated[RiskLevel, classified("internal")]
    assertions: Annotated[list[Assertion], Field(max_length=7), classified("internal")]
    inherent: Annotated[Rating, classified("confidential")]
    control: Annotated[ControlRating, classified("confidential")]
    significant: Annotated[bool, Field(default=False), classified("confidential")]
    fraud: Annotated[Fraud, Field(default="none"), classified("confidential")]
    rationale: Annotated[
        str | None, Field(default=None, max_length=2000), classified("confidential")
    ]


class RiskOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    code: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    area: Annotated[str, classified("confidential")]
    level: Annotated[RiskLevel, classified("internal")]
    assertions: Annotated[list[str], classified("internal")]
    inherent: Annotated[Rating, classified("confidential")]
    control: Annotated[ControlRating, classified("confidential")]
    rmm: Annotated[Rating, classified("confidential")]
    significant: Annotated[bool, classified("confidential")]
    fraud: Annotated[Fraud, classified("confidential")]
    rationale: Annotated[str | None, classified("confidential")]
    needs_approval: Annotated[bool, classified("internal")]
    approved_by_name: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")]
    recorded_by_name: Annotated[str, classified("internal")]
    recorded_at: Annotated[datetime, classified("internal")]


def _risks_out(found: list[RiskView]) -> list[RiskOut]:
    return [RiskOut.model_validate(asdict(r)) for r in found]


def _risk_in(body: RiskBody) -> RiskIn:
    return RiskIn(
        body.title,
        body.area,
        body.level,
        list(body.assertions),
        body.inherent,
        body.control,
        body.significant,
        body.fraud,
        body.rationale,
    )


@router.get("/risks", action="procedure.read", response_model=list[RiskOut])
async def risks_route(engagement_id: UUID, ctx: Ctx) -> list[RiskOut]:
    """SPEC-300 AC-6: the risk register."""
    return _risks_out(await risks_for(ctx, engagement_id))


@router.post("/risks", action="risk.assess", response_model=list[RiskOut], status_code=201)
async def add_risk_route(engagement_id: UUID, body: RiskBody, ctx: Ctx) -> list[RiskOut]:
    """SPEC-300 AC-4: record a new risk."""
    await record_risk(ctx, engagement_id, None, _risk_in(body))
    return _risks_out(await risks_for(ctx, engagement_id))


@router.post(
    "/risks/{risk_id}/versions",
    action="risk.assess",
    response_model=list[RiskOut],
    status_code=201,
)
async def revise_risk_route(
    engagement_id: UUID, risk_id: UUID, body: RiskBody, ctx: Ctx
) -> list[RiskOut]:
    """SPEC-300 AC-4: revise a risk (a new version; the old one stays)."""
    await record_risk(ctx, engagement_id, risk_id, _risk_in(body))
    return _risks_out(await risks_for(ctx, engagement_id))


class ApprovalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rationale: Annotated[
        str | None, Field(default=None, max_length=2000), classified("confidential")
    ]


@router.post(
    "/risks/{risk_id}/approve",
    action="risk.approve",
    response_model=list[RiskOut],
    status_code=201,
)
async def approve_risk_route(
    engagement_id: UUID, risk_id: UUID, body: ApprovalIn, ctx: Ctx
) -> list[RiskOut]:
    """SPEC-300 AC-5: the partner approves the significant risk or rebuttal."""
    await approve_risk(ctx, engagement_id, risk_id, body.rationale)
    return _risks_out(await risks_for(ctx, engagement_id))


# --- The agent procedure session (SPEC-044; TASK-109) ------------------------------------------


class PlanStepOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    text: Annotated[str, classified("internal")]


class SessionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan: Annotated[list[PlanStepOut], classified("internal")]
    approved_by_name: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")]


async def _session_out(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> SessionOut:
    found = await session_of(ctx, engagement_id, procedure_id)
    return SessionOut(
        plan=[PlanStepOut(key=k, text=t) for k, t in found.plan],
        approved_by_name=found.approved_by_name,
        approved_at=found.approved_at,
    )


@router.get(
    "/procedures/{procedure_id}/session", action="procedure.read", response_model=SessionOut
)
async def session_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> SessionOut:
    """SPEC-044 AC-1: the session's plan, and its approval."""
    return await _session_out(ctx, engagement_id, procedure_id)


@router.post(
    "/procedures/{procedure_id}/session/approve-plan",
    action="procedure.run",
    response_model=SessionOut,
    status_code=201,
    errors=(409,),
)
async def approve_plan_route(engagement_id: UUID, procedure_id: UUID, ctx: Ctx) -> SessionOut:
    """SPEC-044 AC-2: a person approves the plan; the selection starts if there's none."""
    if await approve_plan(ctx, engagement_id, procedure_id):
        await request_selection(ctx, engagement_id, procedure_id)
    return await _session_out(ctx, engagement_id, procedure_id)


class FindingHitOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]


@firm_router.get("/search/findings", action=OWN, response_model=list[FindingHitOut])
async def search_findings_route(
    ctx: Annotated[AuthContext, Depends(current_member)],
    q: Annotated[str, Query(max_length=100)] = "",
) -> list[FindingHitOut]:
    """SPEC-302 AC-2: the command palette's findings, newest first."""
    return [
        FindingHitOut(id=f.id, engagement_id=f.engagement_id, title=f.title)
        for f in await search_findings(ctx, q)
    ]
