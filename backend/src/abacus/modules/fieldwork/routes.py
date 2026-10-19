"""Fieldwork routes (SPEC-037; TASK-077). Flag `fieldwork.procedures` gates starting and
selecting; reads follow `procedure.read`."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.fieldwork.service import (
    Defaults,
    Materiality,
    Pick,
    ProcedureView,
    add_picks,
    fieldwork_defaults,
    items_of,
    materiality_of,
    procedure_detail,
    procedures_of,
    request_selection,
    set_fieldwork_defaults,
    set_materiality,
    set_parameters,
    start_procedure,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["fieldwork"])
firm_router = AbacusRouter(prefix="/v1/firm", tags=["fieldwork"])
Ctx = Annotated[AuthContext, Depends(current_context)]
Money = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]


class MaterialityIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    overall: Annotated[Money, classified("confidential")]
    performance: Annotated[Money, classified("confidential")]
    trivial: Annotated[Money, classified("confidential")]
    benchmark: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]


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


@router.post(
    "/procedures",
    action="procedure.run",
    response_model=ProcedureOut,
    status_code=201,
    errors=(409,),
)
async def start_procedure_route(engagement_id: UUID, ctx: Ctx) -> ProcedureOut:
    """SPEC-037: start journal entry testing (once per engagement)."""
    return _procedure_out(await start_procedure(ctx, engagement_id))


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
            }
        )
        for i in await items_of(ctx, engagement_id, procedure_id, offset=offset, limit=limit)
    ]
