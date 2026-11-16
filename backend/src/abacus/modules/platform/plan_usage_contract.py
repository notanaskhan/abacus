"""The plan & usage contract stubs (G-04-T03; SPEC-680 AC-26 to AC-43; DEC-5203).
Contract: `docs/contracts/plan-usage.md`. Screen: ADM-14 (Firm settings > Plan & usage).

Every route has one matrix action and answers, in order: a client principal 404; the action on
the firm (`authorise`); 404 while `platform.plan_usage` is off for the firm; then 501 naming the
task that implements it (G-04-T11). Agent-minutes are stored integers summed by code (ADR-148,
ADR-050); no price, overage amount, payment or invoice appears anywhere (P-27). Billing rates are
the firm's own rates read from its practice-management system (I-04) or, for a synthetic firm
only, the fake provider; they are never Accrued's prices and never editable here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import PLATFORM_PLAN_USAGE
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
Minutes = Annotated[int, Field(ge=0), Internal]
ModuleKey = Literal[
    # G-04-T04 (OQ-6): the four service lines, recorded and shown, not enforced in 2028.
    "tax_services",
    "audit_assurance",
    "client_accounting",
    "advisory",
    # F-03-T28 and later: the add-on modules `require_entitlement()` enforces.
    "attest",
    "internal_audit",
    "group_audit",
    "statements_studio",
    "office_addins",
    "insights",
    "tax_returns",
    "ebp_audits",
    "assurance_completion",
    "tax_entity_returns",
    "cas_closes",
]
At100 = Literal["keep_running", "pause_scheduled"]
PlanRequestKind = Literal["seats", "agent_minutes", "modules"]
PlanRequestStatus = Literal[
    "awaiting_partner", "sent_to_accrued", "applied", "declined", "withdrawn"
]
RecipientGroup = Literal["partners", "firm_admins"]


class PlanRequestSelfApproval(DomainConflict):
    """The approver made the request (AC-41); a different partner-level member decides."""

    code = "plan_request_self_approval"


class PlanRequestNotPending(DomainConflict):
    """The request is no longer awaiting the partner (decided, withdrawn or applied)."""

    code = "plan_request_not_pending"


# --- models --------------------------------------------------------------------------------------


class PersonRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, Internal]
    display_name: Annotated[str, Internal]


class SeatsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    used: Minutes
    total: Annotated[int, Field(ge=1), Internal]
    pending: Minutes  # seats in an open plan request
    full: Annotated[bool, Internal]


class FirmPlanOut(BaseModel):
    """GET /v1/firm/plan (AC-27, AC-29): term, renewal, seats, modules and the library label."""

    model_config = ConfigDict(frozen=True)

    plan_code: Annotated[str, Internal]
    term_start: Annotated[date, Internal]
    term_end: Annotated[date, Internal]
    renewal_on: Annotated[date, Internal]
    renewal_in_days: Minutes
    seats: SeatsOut
    modules: Annotated[list[ModuleKey], Internal]
    library_channel: Annotated[Literal["stable", "early_access"], Internal]
    billing_contact: PersonRef | None
    workbench_active_30d: Minutes
    included_agent_minutes: Minutes
    usage_month_anchor_day: Annotated[int, Field(ge=1, le=28), Internal]
    version: Annotated[int, Field(ge=1), Internal]


class BillingContactIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, Internal]


class AlertRuleOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    threshold_pct: Annotated[int, Field(ge=1, le=100), Internal]
    threshold_minutes: Minutes
    enabled: Annotated[bool, Internal]
    recipients: Annotated[list[PersonRef], Internal]
    recipient_groups: Annotated[list[RecipientGroup], Internal]


class AlertRuleIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    threshold_pct: Annotated[int, Field(ge=1, le=100), Internal]
    enabled: Annotated[bool, Internal]
    recipient_user_ids: Annotated[list[UUID], Field(max_length=50), Internal]
    recipient_groups: Annotated[list[RecipientGroup], Field(max_length=2), Internal]


class BudgetAlertsOut(BaseModel):
    """GET /v1/firm/budget-alerts (AC-33, AC-39)."""

    model_config = ConfigDict(frozen=True)

    rules: Annotated[list[AlertRuleOut], Internal]
    at_100_behaviour: Annotated[At100, Internal]
    engagement_default_minutes: Minutes
    engagement_alert_pct: Annotated[int, Field(ge=1, le=100), Internal]
    partner_approver: PersonRef | None
    version: Annotated[int, Field(ge=1), Internal]
    updated_by: PersonRef | None
    updated_at: Annotated[datetime | None, Internal]


class BudgetAlertsIn(BaseModel):
    """PUT /v1/firm/budget-alerts with `version` (AC-34; 409 `stale_version`, fresh MFA)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Annotated[int, Field(ge=1), Internal]
    rules: Annotated[list[AlertRuleIn], Field(max_length=10), Internal]
    at_100_behaviour: Annotated[At100, Internal]
    engagement_default_minutes: Annotated[int, Field(ge=0, le=1_000_000), Internal]


class EngagementBudgetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, Internal]
    engagement_name: Annotated[str, Confidential]  # through visible() (AC-32); firm side only
    used_minutes: Minutes
    budget_minutes: Minutes
    used_pct: Annotated[Decimal, Internal]
    alert_sent_at: Annotated[datetime | None, Internal]
    alert_sent_to_initials: Annotated[str | None, Internal]


class EngagementBudgetsOut(BaseModel):
    """GET /v1/firm/engagement-budgets?alerting=true (AC-32): visible() rows, no hidden counts."""

    model_config = ConfigDict(frozen=True)

    items: Annotated[list[EngagementBudgetOut], Internal]
    counts: Annotated[dict[str, int], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class BillingRateBandOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[str, Internal]
    people: Minutes
    hourly_rate: Annotated[Decimal | None, Confidential]  # None reads "Non-chargeable"


class BillingRatesOut(BaseModel):
    """GET /v1/firm/billing-rates (AC-28): the registered provider's rates or not connected."""

    model_config = ConfigDict(frozen=True)

    connected: Annotated[bool, Internal]
    provider_key: Annotated[str | None, Internal]
    bands: Annotated[list[BillingRateBandOut], Internal]
    effective_from: Annotated[date | None, Internal]
    synced_at: Annotated[datetime | None, Internal]


class PlanRequestIn(BaseModel):
    """POST /v1/firm/plan-requests (AC-40, AC-43)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    kind: Annotated[PlanRequestKind, Internal]
    to_value: Annotated[int | None, Field(ge=0), Internal] = None
    modules_add: Annotated[list[ModuleKey], Field(max_length=10), Internal] = []
    effective_from: Annotated[date | None, Internal] = None
    reason: Annotated[str, Field(min_length=10, max_length=500), Confidential]


class PlanRequestDeclineIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[str, Field(min_length=10, max_length=500), Confidential]


class PlanRequestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    kind: Annotated[PlanRequestKind, Internal]
    from_value: Annotated[int | None, Internal]
    to_value: Annotated[int | None, Internal]
    modules_add: Annotated[list[ModuleKey], Internal]
    effective_from: Annotated[date | None, Internal]
    reason: Annotated[str, Confidential]
    status: Annotated[PlanRequestStatus, Internal]
    requested_by: PersonRef
    approver: PersonRef | None
    decided_by: PersonRef | None
    decided_at: Annotated[datetime | None, Internal]
    applied_at: Annotated[datetime | None, Internal]
    version: Annotated[int, Field(ge=1), Internal]
    allowed_actions: Annotated[list[Literal["approve", "decline", "withdraw"]], Internal]


class PlanRequestsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[PlanRequestOut], Internal]
    counts: Annotated[dict[str, int], Internal]
    next_cursor: Annotated[str | None, Internal] = None


# --- routes --------------------------------------------------------------------------------------

router = AbacusRouter(prefix="/v1/firm", tags=["plan & usage"])
_TASK = "G-04-T11"


async def _gate(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("plan")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, PLATFORM_PLAN_USAGE):
        raise NotFound(PLATFORM_PLAN_USAGE.name)


@router.get("/plan", action="plan.read", response_model=FirmPlanOut, errors=(501,))
async def plan_get(ctx: Ctx) -> FirmPlanOut:
    await _gate(ctx, "plan.read")
    raise NotImplementedYet(_TASK)


@router.put(
    "/plan/billing-contact",
    action="billing_contact.manage",
    response_model=FirmPlanOut,
    errors=(501,),
)
async def plan_set_billing_contact(body: BillingContactIn, ctx: Ctx) -> FirmPlanOut:
    await _gate(ctx, "billing_contact.manage")
    raise NotImplementedYet(_TASK)


@router.get("/budget-alerts", action="plan.read", response_model=BudgetAlertsOut, errors=(501,))
async def budget_alerts_get(ctx: Ctx) -> BudgetAlertsOut:
    await _gate(ctx, "plan.read")
    raise NotImplementedYet(_TASK)


@router.put(
    "/budget-alerts",
    action="budget_alert.manage",
    response_model=BudgetAlertsOut,
    errors=(409, 501),
)
async def budget_alerts_put(body: BudgetAlertsIn, ctx: Ctx) -> BudgetAlertsOut:
    await _gate(ctx, "budget_alert.manage")
    raise NotImplementedYet(_TASK)


@router.get(
    "/engagement-budgets",
    action="usage.read",
    response_model=EngagementBudgetsOut,
    errors=(501,),
)
async def engagement_budgets(
    ctx: Ctx,
    alerting: Annotated[bool, Query()] = True,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> EngagementBudgetsOut:
    await _gate(ctx, "usage.read")
    raise NotImplementedYet(_TASK)


@router.get("/billing-rates", action="plan.read", response_model=BillingRatesOut, errors=(501,))
async def billing_rates(ctx: Ctx) -> BillingRatesOut:
    await _gate(ctx, "plan.read")
    raise NotImplementedYet(_TASK)


@router.get("/plan-requests", action="plan.read", response_model=PlanRequestsOut, errors=(501,))
async def plan_requests_list(
    ctx: Ctx,
    status: Annotated[PlanRequestStatus | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> PlanRequestsOut:
    await _gate(ctx, "plan.read")
    raise NotImplementedYet(_TASK)


@router.post(
    "/plan-requests",
    action="plan_request.create",
    response_model=PlanRequestOut,
    status_code=201,
    errors=(409, 501),
)
async def plan_requests_create(
    body: PlanRequestIn, ctx: Ctx, _key: IdempotencyKey
) -> PlanRequestOut:
    await _gate(ctx, "plan_request.create")
    raise NotImplementedYet(_TASK)


@router.post(
    "/plan-requests/{request_id}/approve",
    action="plan_request.approve",
    response_model=PlanRequestOut,
    errors=(409, 501),
)
async def plan_requests_approve(request_id: UUID, ctx: Ctx) -> PlanRequestOut:
    await _gate(ctx, "plan_request.approve")
    raise NotImplementedYet(_TASK)


@router.post(
    "/plan-requests/{request_id}/decline",
    action="plan_request.approve",
    response_model=PlanRequestOut,
    errors=(409, 501),
)
async def plan_requests_decline(
    request_id: UUID, body: PlanRequestDeclineIn, ctx: Ctx
) -> PlanRequestOut:
    await _gate(ctx, "plan_request.approve")
    raise NotImplementedYet(_TASK)


@router.post(
    "/plan-requests/{request_id}/withdraw",
    action="plan_request.create",
    response_model=PlanRequestOut,
    errors=(409, 501),
)
async def plan_requests_withdraw(request_id: UUID, ctx: Ctx) -> PlanRequestOut:
    await _gate(ctx, "plan_request.create")
    raise NotImplementedYet(_TASK)
