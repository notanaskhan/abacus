"""Budgets and metering for firm admins (SPEC-007 AC-7, AC-8). The gateway owns the data."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from abacus.ai_gateway.budgets import (
    FirmBudget,
    SpendLine,
    firm_budget,
    save_firm_budget,
    spend_by_engagement_and_agent,
)
from abacus.kernel.config import settings
from abacus.kernel.errors import DomainInvalid
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise, note_budget_reviewed


class BudgetInvalid(DomainInvalid):
    """Soft must be positive and at most hard; hard at most the plan's limit (Q3)."""

    code = "budget_invalid"


async def read_budget(ctx: AuthContext) -> FirmBudget:
    await authorise(ctx, "budget.read", Resource.firm(ctx.tenant_id))
    return await firm_budget(ctx.tenant)


async def set_budget(ctx: AuthContext, soft: Decimal, hard: Decimal) -> FirmBudget:
    """Applies to the next call (the gateway's cached sums are dropped)."""
    if not Decimal(0) < soft <= hard <= settings().firm_budget_cap_usd:
        raise BudgetInvalid("soft must be positive and at most hard, hard at most the plan limit")
    async with uow(ctx.tenant) as tx:
        await authorise(ctx, "budget.manage", Resource.firm(ctx.tenant_id))
        await save_firm_budget(tx.session, ctx.tenant_id, ctx.user_id, soft, hard)
        await note_budget_reviewed(tx)  # SPEC-024: the checklist's budget step
        tx.record(
            "budget.updated",
            target=Target("firm", ctx.tenant_id),
            after=Ref(monthly_soft_cents=int(soft * 100), monthly_hard_cents=int(hard * 100)),
        )
    return await firm_budget(ctx.tenant)


async def metering(ctx: AuthContext, period: Literal["day", "month"]) -> list[SpendLine]:
    await authorise(ctx, "budget.read", Resource.firm(ctx.tenant_id))
    return await spend_by_engagement_and_agent(ctx.tenant, period)
