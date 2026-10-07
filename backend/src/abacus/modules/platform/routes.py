"""Budget and metering routes (SPEC-007 §8, AC-7, AC-8)."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.platform.service import metering, read_budget, set_budget

router = AbacusRouter(prefix="/v1", tags=["budget"])
Ctx = Annotated[AuthContext, Depends(current_context)]
Usd = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2), classified("internal")]


class BudgetIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    monthly_soft_usd: Usd
    monthly_hard_usd: Usd


class BudgetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    monthly_soft_usd: Annotated[Decimal, classified("internal")]
    monthly_hard_usd: Annotated[Decimal, classified("internal")]
    plan_cap_usd: Annotated[Decimal, classified("internal")]
    spent_this_month_usd: Annotated[Decimal, classified("internal")]
    is_default: Annotated[bool, classified("internal")]


class SpendOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID | None, classified("internal")]
    agent_id: Annotated[str | None, classified("internal")]
    cost_usd: Annotated[Decimal, classified("internal")]


@router.get("/budget", action="budget.read", response_model=BudgetOut)
async def get_budget_route(ctx: Ctx) -> BudgetOut:
    return BudgetOut.model_validate(asdict(await read_budget(ctx)))


@router.put("/budget", action="budget.manage", response_model=BudgetOut)
async def put_budget_route(body: BudgetIn, ctx: Ctx) -> BudgetOut:
    budget = await set_budget(ctx, body.monthly_soft_usd, body.monthly_hard_usd)
    return BudgetOut.model_validate(asdict(budget))


@router.get("/metering", action="budget.read", response_model=list[SpendOut])
async def metering_route(
    ctx: Ctx, period: Annotated[Literal["day", "month"], Query()] = "month"
) -> list[SpendOut]:
    return [SpendOut.model_validate(asdict(line)) for line in await metering(ctx, period)]
