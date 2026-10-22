"""Budget and metering routes (SPEC-007 §8, AC-7, AC-8)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.identity.api import SELF, AbacusRouter, AuthContext, current_context
from abacus.modules.platform.capabilities import capabilities
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


# --- F-03-T30: what the signed-in person may do (ADR-145) --------------------------------------


class RoleOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]


class GrantScopeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Annotated[str, classified("internal")]
    scope_kind: Annotated[str, classified("internal")]
    scope_id: Annotated[UUID, classified("internal")]


class PortalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    shell: Annotated[Literal["full", "k1", "limited", "none"], classified("internal")]
    scopes: Annotated[list[GrantScopeOut], classified("internal")]


class CapabilitiesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID | None, classified("internal")]
    capabilities: Annotated[list[str], classified("internal")]
    roles: Annotated[list[RoleOut], classified("internal")]
    flags: Annotated[dict[str, bool | str], classified("internal")]
    entitlements: Annotated[list[str], classified("internal")]
    office_id: Annotated[UUID | None, classified("internal")]
    tz: Annotated[str, classified("internal")]
    mfa_recent_until: Annotated[datetime | None, classified("internal")]
    server_now: Annotated[datetime, classified("internal")]
    clock_mode: Annotated[Literal["real", "offset", "frozen"], classified("internal")]
    portal: Annotated[PortalOut | None, classified("internal")]


@router.get("/me/capabilities", action=SELF, response_model=CapabilitiesOut)
async def my_capabilities(
    ctx: Ctx, engagement_id: Annotated[UUID | None, Query()] = None
) -> CapabilitiesOut:
    """The matrix evaluated for the caller, without recording an authorisation check: what the
    UI may offer, never a grant (F-03-T30)."""
    found = await capabilities(ctx, engagement_id)
    portal = (
        PortalOut(
            shell=found.portal.shell,  # type: ignore[arg-type]  # a portal shell literal
            scopes=[
                GrantScopeOut(role=s.role, scope_kind=s.scope_kind, scope_id=s.scope_id)
                for s in found.portal.scopes
            ],
        )
        if found.portal is not None
        else None
    )
    return CapabilitiesOut(
        engagement_id=found.engagement_id,
        capabilities=list(found.capabilities),
        roles=[RoleOut(code=r.code, label=r.label) for r in found.roles],
        flags=found.flags,
        entitlements=list(found.entitlements),
        office_id=found.office_id,
        tz=found.tz,
        mfa_recent_until=found.mfa_recent_until,
        server_now=found.server_now,
        clock_mode=found.clock_mode,  # type: ignore[arg-type]  # a clock mode literal
        portal=portal,
    )
