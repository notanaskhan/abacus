"""Plan & usage (G-04-T11; SPEC-680 AC-26 to AC-43; ADM-14; DEC-5418; amber).

- **Plan** (AC-27, AC-29): the current `plan_entitlements` version (insert-only; the version is
  its count), seats in use (identity's count, as ADM-02) and pending in open seat requests, the
  firm's enabled modules, the billing contact and Workbench activity (a slot W-02 fills).
- **Budget alerts** (AC-33, AC-34, AC-39): one policy row per firm with a `version`; a PUT with a
  stale version answers 409 `stale_version` (fresh MFA is the matrix's `mfa_recent`). Rules are
  upserted by threshold; a rule the body leaves out is disabled (rules are never deleted). Each
  rule's minutes are code's: the included minutes times the percent, rounded down.
- **Engagement budgets** (AC-32): this usage month's minutes per engagement the reader may open
  (`visible()` through `engagement.read`; a hidden one is left out, never counted), against the
  firm's engagement default; `alerting` keeps those at or over the alert percent.
- **Billing rates** (AC-28): the firm's own rates from its practice-management provider through
  `register_billing_rates`; a synthetic firm reads the fake provider; otherwise not connected.
  Never Accrued's prices (P-27).
- **Plan requests** (AC-40 to AC-43): a firm admin or partner asks; a partner-level member who is
  not the requester approves or declines (the matrix, the table's CHECK and
  `plan_request_self_approval`); the requester withdraws while it awaits the partner. An awaiting
  request names its approver (the policy's partner approver); its C13 gate is G-04-T12's (review
  may read platform; platform may not import review).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from abacus.kernel import clock
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.identity.api import AuthContext, is_synthetic_firm, names_of, seats_in_use
from abacus.modules.platform.metering import (
    _labels,  # pyright: ignore[reportPrivateUsage] -- one module
    _seen,  # pyright: ignore[reportPrivateUsage] -- one module
    usage_month_of,
)
from abacus.modules.platform.plan_usage_contract import (
    AlertRuleOut,
    BillingRateBandOut,
    BillingRatesOut,
    BudgetAlertsIn,
    BudgetAlertsOut,
    EngagementBudgetOut,
    EngagementBudgetsOut,
    FirmPlanOut,
    PersonRef,
    PlanRequestIn,
    PlanRequestNotPending,
    PlanRequestOut,
    PlanRequestSelfApproval,
    PlanRequestsOut,
    SeatsOut,
)

TARGET: Final = "plan_change_request"


class StaleVersion(DomainConflict):
    code = "stale_version"


class NotAMember(DomainConflict):
    code = "not_a_member"


# The change event (the console and a later C13 gate read it; identifiers only).
class _Changed(DomainEvent):
    event_type: ClassVar[str] = "plan_request.changed"

    tenant_id: Annotated[UUID, classified("internal")]
    request_id: Annotated[UUID, classified("internal")]


# --- slots ---------------------------------------------------------------------------------------

WorkbenchActive = Callable[[TenantContext], Awaitable[int]]
_WORKBENCH: list[WorkbenchActive] = []


def register_workbench_activity(source: WorkbenchActive) -> None:
    """W-02: people with a Workbench session in the last 30 days."""
    if source not in _WORKBENCH:
        _WORKBENCH.append(source)


@dataclass(frozen=True)
class RateBand:
    label: str
    people: int
    hourly_rate: Decimal | None


@dataclass(frozen=True)
class RateCard:
    provider_key: str
    bands: tuple[RateBand, ...]
    effective_from: date | None
    synced_at: datetime | None


BillingRates = Callable[[TenantContext], Awaitable[RateCard | None]]
_RATES: list[BillingRates] = []


def register_billing_rates(source: BillingRates) -> None:
    """I-04: the firm's own rates from its practice-management system."""
    if source not in _RATES:
        _RATES.append(source)


# --- plan ----------------------------------------------------------------------------------------

_PLAN: Final = text(
    "SELECT plan_code, term_start, term_end, renewal_on, seats_total, included_agent_minutes, "
    "library_channel, usage_month_anchor_day, (SELECT count(*) FROM plan_entitlements) AS version "
    "FROM plan_entitlements WHERE valid_from <= abacus_now() "
    "ORDER BY valid_from DESC, created_at DESC LIMIT 1"
)
_MODULES: Final = text("SELECT module FROM tenant_entitlements WHERE enabled ORDER BY module")
_POLICY: Final = text(
    "SELECT version, at_100_behaviour, engagement_default_minutes, engagement_alert_pct, "
    "billing_contact_user_id, partner_approver_user_id, updated_by, updated_at "
    "FROM usage_alert_policies"
)
_PENDING_SEATS: Final = text(
    "SELECT coalesce(sum(greatest(to_value - coalesce(from_value, 0), 0)), 0) "
    "FROM plan_change_requests WHERE kind = 'seats' "
    "AND status IN ('awaiting_partner', 'sent_to_accrued')"
)


async def _person(user_id: UUID | None) -> PersonRef | None:
    if user_id is None:
        return None
    name = (await names_of([user_id])).get(user_id)
    return None if name is None else PersonRef(user_id=user_id, display_name=name)


async def plan(ctx: AuthContext) -> FirmPlanOut:
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_PLAN)).mappings().first()
        modules = [str(m) for m in (await session.execute(_MODULES)).scalars()]
        policy = (await session.execute(_POLICY)).mappings().first()
        pending = int(await session.scalar(_PENDING_SEATS) or 0)
    if row is None:
        raise NotFound("plan_entitlements")
    used = await seats_in_use(ctx.tenant)
    total = int(row["seats_total"])
    today = await clock.today(ctx.tenant)
    active = sum([await source(ctx.tenant) for source in _WORKBENCH])
    return FirmPlanOut(
        plan_code=str(row["plan_code"]),
        term_start=row["term_start"],
        term_end=row["term_end"],
        renewal_on=row["renewal_on"],
        renewal_in_days=max((cast(date, row["renewal_on"]) - today).days, 0),
        seats=SeatsOut(used=used, total=total, pending=pending, full=used >= total),
        modules=modules,  # type: ignore[arg-type] -- tenant_entitlements' CHECK is ModuleKey
        library_channel=row["library_channel"],
        billing_contact=await _person(
            None if policy is None else cast("UUID | None", policy["billing_contact_user_id"])
        ),
        workbench_active_30d=active,
        included_agent_minutes=int(row["included_agent_minutes"]),
        usage_month_anchor_day=int(row["usage_month_anchor_day"]),
        version=int(row["version"]),
    )


_ENSURE_POLICY: Final = text(
    "INSERT INTO usage_alert_policies (tenant_id) VALUES (:t) ON CONFLICT (tenant_id) DO NOTHING"
)


async def set_billing_contact(ctx: AuthContext, user_id: UUID) -> FirmPlanOut:
    if not (await names_of([user_id])).get(user_id):
        raise NotAMember(facts={"user": "not_in_firm"})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_ENSURE_POLICY, {"t": ctx.tenant_id})
        await tx.session.execute(
            text(
                "UPDATE usage_alert_policies SET billing_contact_user_id = :u, updated_by = :by, "
                "updated_at = abacus_now(), version = version + 1"
            ),
            {"u": user_id, "by": ctx.user_id},
        )
        tx.record("billing_contact.changed", target=Target("firm", ctx.tenant_id))
    return await plan(ctx)


# --- budget alerts -------------------------------------------------------------------------------


def rule_minutes(included: int, pct: int) -> int:
    """A rule's minutes: the included minutes times its percent, rounded down (code's figure)."""
    return included * pct // 100


async def _included(tenant: TenantContext) -> int:
    async with tenant_session(tenant) as session:
        return int(
            await session.scalar(
                text(
                    "SELECT included_agent_minutes FROM plan_entitlements "
                    "WHERE valid_from <= abacus_now() ORDER BY valid_from DESC, created_at "
                    "DESC LIMIT 1"
                )
            )
            or 0
        )


async def budget_alerts(ctx: AuthContext) -> BudgetAlertsOut:
    async with tenant_session(ctx.tenant) as session:
        policy = (await session.execute(_POLICY)).mappings().first()
        rules = list(
            (
                await session.execute(
                    text(
                        "SELECT id, threshold_pct, enabled, recipient_user_ids, recipient_groups "
                        "FROM usage_alert_rules ORDER BY threshold_pct"
                    )
                )
            ).mappings()
        )
    included = await _included(ctx.tenant)
    people = await names_of(
        sorted({u for r in rules for u in cast("list[UUID]", r["recipient_user_ids"])}, key=str)
    )
    return BudgetAlertsOut(
        rules=[
            AlertRuleOut(
                id=r["id"],
                threshold_pct=int(r["threshold_pct"]),
                threshold_minutes=rule_minutes(included, int(r["threshold_pct"])),
                enabled=bool(r["enabled"]),
                recipients=[
                    PersonRef(user_id=u, display_name=people[u])
                    for u in cast("list[UUID]", r["recipient_user_ids"])
                    if u in people
                ],
                recipient_groups=list(r["recipient_groups"] or []),
            )
            for r in rules
        ],
        at_100_behaviour="keep_running" if policy is None else policy["at_100_behaviour"],
        engagement_default_minutes=1500
        if policy is None
        else int(policy["engagement_default_minutes"]),
        engagement_alert_pct=80 if policy is None else int(policy["engagement_alert_pct"]),
        partner_approver=await _person(
            None if policy is None else cast("UUID | None", policy["partner_approver_user_id"])
        ),
        version=1 if policy is None else int(policy["version"]),
        updated_by=await _person(None if policy is None else policy["updated_by"]),
        updated_at=None if policy is None else policy["updated_at"],
    )


async def set_budget_alerts(ctx: AuthContext, body: BudgetAlertsIn) -> BudgetAlertsOut:
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_ENSURE_POLICY, {"t": ctx.tenant_id})
        changed = await tx.session.scalar(
            text(
                "UPDATE usage_alert_policies SET version = version + 1, at_100_behaviour = :b, "
                "engagement_default_minutes = :m, updated_by = :by, updated_at = abacus_now() "
                "WHERE version = :v RETURNING version"
            ),
            {"b": body.at_100_behaviour, "m": body.engagement_default_minutes,
             "by": ctx.user_id, "v": body.version},
        )  # fmt: skip
        if changed is None:
            current = await tx.session.scalar(text("SELECT version FROM usage_alert_policies"))
            raise StaleVersion(facts={"version": int(current or 1)})
        wanted = {r.threshold_pct for r in body.rules}
        for r in body.rules:
            await tx.session.execute(
                text(
                    "INSERT INTO usage_alert_rules (tenant_id, threshold_pct, enabled, "
                    "recipient_user_ids, recipient_groups) VALUES (:t, :p, :e, :u, :g) "
                    "ON CONFLICT (tenant_id, level, threshold_pct) DO UPDATE SET "
                    "enabled = EXCLUDED.enabled, "
                    "recipient_user_ids = EXCLUDED.recipient_user_ids, "
                    "recipient_groups = EXCLUDED.recipient_groups, updated_at = abacus_now()"
                ),
                {"t": ctx.tenant_id, "p": r.threshold_pct, "e": r.enabled,
                 "u": list(r.recipient_user_ids), "g": list(r.recipient_groups)},
            )  # fmt: skip
        await tx.session.execute(
            text(
                "UPDATE usage_alert_rules SET enabled = false, updated_at = abacus_now() "
                "WHERE NOT (threshold_pct = ANY(:keep)) AND enabled"
            ),
            {"keep": sorted(wanted)},
        )
        tx.record(
            "budget_alerts.changed",
            target=Target("firm", ctx.tenant_id),
            after=Ref(version=int(changed), rules=len(body.rules)),
        )
    return await budget_alerts(ctx)


# --- engagement budgets --------------------------------------------------------------------------

_BY_ENGAGEMENT: Final = text(
    "SELECT engagement_id, sum(minutes) AS minutes FROM usage_month_rollups "
    "WHERE usage_month = :m AND engagement_id IS NOT NULL GROUP BY engagement_id"
)
_ENGAGEMENT_ALERTS: Final = text(
    "SELECT DISTINCT ON (engagement_id) engagement_id, crossed_at, sent_to "
    "FROM usage_alert_events "
    "WHERE scope = 'engagement' AND usage_month = :m ORDER BY engagement_id, crossed_at DESC"
)


def used_pct(used: int, budget: int) -> Decimal:
    if budget <= 0:
        return Decimal(0)
    return (Decimal(used) * 100 / Decimal(budget)).quantize(Decimal("0.1"), ROUND_HALF_UP)


def _initials(name: str) -> str:
    parts = name.split()
    return "".join(p[0] for p in parts[:1] + parts[-1:]).upper() if parts else ""


async def engagement_budgets(ctx: AuthContext, alerting: bool) -> EngagementBudgetsOut:
    month = usage_month_of(await clock.today(ctx.tenant))
    async with tenant_session(ctx.tenant) as session:
        rows = list((await session.execute(_BY_ENGAGEMENT, {"m": month})).mappings())
        alerts = {
            cast(UUID, r["engagement_id"]): r
            for r in (await session.execute(_ENGAGEMENT_ALERTS, {"m": month})).mappings()
        }
        policy = (await session.execute(_POLICY)).mappings().first()
    budget = 1500 if policy is None else int(policy["engagement_default_minutes"])
    alert_pct = 80 if policy is None else int(policy["engagement_alert_pct"])
    visible = [r for r in rows if await _seen(ctx, cast(UUID, r["engagement_id"]))]
    labels = dict(
        await _labels(ctx.tenant, "engagement", [str(r["engagement_id"]) for r in visible])
    )
    out: list[EngagementBudgetOut] = []
    for r in visible:
        eid = cast(UUID, r["engagement_id"])
        used = int(r["minutes"])
        pct = used_pct(used, budget)
        if alerting and pct < alert_pct:
            continue
        sent = alerts.get(eid)
        first = cast("list[UUID]", sent["sent_to"])[:1] if sent is not None else []
        names = await names_of(first) if first else {}
        out.append(
            EngagementBudgetOut(
                engagement_id=eid,
                engagement_name=labels.get(str(eid), ""),
                used_minutes=used,
                budget_minutes=budget,
                used_pct=pct,
                alert_sent_at=None if sent is None else sent["crossed_at"],
                alert_sent_to_initials=_initials(names[first[0]])
                if first and first[0] in names
                else None,
            )
        )
    out.sort(key=lambda e: e.used_pct, reverse=True)
    return EngagementBudgetsOut(items=out, counts={"alerting": len(out)})


# --- over-limit policy (G-04-T08) ----------------------------------------------------------------


@dataclass(frozen=True)
class OverLimit:
    """`platform.api.over_limit_policy` (plan-usage contract): the firm's At 100% choice and
    whether this usage month's minutes are at or over the included minutes."""

    pause_scheduled: bool
    at_or_over: bool
    usage_month: str
    minutes: int
    included: int


async def over_limit_policy(tenant: TenantContext) -> OverLimit:
    from abacus.kernel._flags import PLATFORM_PLAN_USAGE
    from abacus.kernel.flags import flag_enabled

    month = usage_month_of(await clock.today(tenant))
    async with tenant_session(tenant) as session:
        policy = await session.scalar(text("SELECT at_100_behaviour FROM usage_alert_policies"))
        minutes = int(
            await session.scalar(
                text(
                    "SELECT coalesce(sum(minutes), 0) FROM usage_month_rollups "
                    "WHERE usage_month = :m"
                ),
                {"m": month},
            )
            or 0
        )
    included = await _included(tenant)
    on = await flag_enabled(tenant, PLATFORM_PLAN_USAGE)
    return OverLimit(
        pause_scheduled=on and policy == "pause_scheduled",
        at_or_over=included > 0 and minutes >= included,
        usage_month=month,
        minutes=minutes,
        included=included,
    )


# --- billing rates -------------------------------------------------------------------------------


def _fake_rates() -> RateCard:
    """AC-28: the fake provider's card (the figure book's `g04_fixtures`), synthetic firms
    only."""
    from abacus.modules.platform.g04_fixtures import RATE_BANDS, RATES_EFFECTIVE

    return RateCard(
        "fake_practice_management",
        tuple(RateBand(label, people, rate) for label, people, rate in RATE_BANDS),
        RATES_EFFECTIVE,
        None,
    )


async def billing_rates(ctx: AuthContext) -> BillingRatesOut:
    """AC-28: the registered provider's card, the fake one for a synthetic firm only."""
    card: RateCard | None = None
    for source in _RATES:
        card = await source(ctx.tenant)
        if card is not None:
            break
    if card is None and await is_synthetic_firm(ctx.tenant):
        card = _fake_rates()
    if card is None:
        return BillingRatesOut(
            connected=False, provider_key=None, bands=[], effective_from=None, synced_at=None
        )
    return BillingRatesOut(
        connected=True,
        provider_key=card.provider_key,
        bands=[
            BillingRateBandOut(label=b.label, people=b.people, hourly_rate=b.hourly_rate)
            for b in card.bands
        ],
        effective_from=card.effective_from,
        synced_at=card.synced_at,
    )


# --- plan requests -------------------------------------------------------------------------------

_REQUESTS: Final = text(
    "SELECT id, kind, from_value, to_value, modules_add, effective_from, reason, status, "
    "requested_by, approver_user_id, decided_by, decided_at, applied_at, version "
    "FROM plan_change_requests ORDER BY created_at DESC"
)


def allowed(row: Mapping[str, object], ctx: AuthContext, may_approve: bool) -> list[str]:
    """What this reader may do: approve or decline (a partner who did not ask), withdraw (the
    requester), only while the request awaits the partner."""
    if row["status"] != "awaiting_partner":
        return []
    out: list[str] = []
    if may_approve and row["requested_by"] != ctx.user_id:
        out += ["approve", "decline"]
    if row["requested_by"] == ctx.user_id:
        out.append("withdraw")
    return out


async def _may_approve(ctx: AuthContext) -> bool:
    from abacus.modules.identity.api import Forbidden, Resource, authorise

    try:
        await authorise(ctx, "plan_request.approve", Resource.firm(ctx.tenant_id))
    except Forbidden:
        return False
    return True


async def _out(ctx: AuthContext, rows: Sequence[RowMapping]) -> list[PlanRequestOut]:
    ids = {
        cast(UUID, r[k])
        for r in rows
        for k in ("requested_by", "approver_user_id", "decided_by")
        if r[k] is not None
    }
    people = await names_of(sorted(ids, key=str)) if ids else {}
    may = await _may_approve(ctx)

    def ref(u: object) -> PersonRef | None:
        return (
            None
            if u is None
            else PersonRef(user_id=cast(UUID, u), display_name=people.get(cast(UUID, u), ""))
        )

    return [
        PlanRequestOut(
            id=r["id"],
            kind=r["kind"],
            from_value=r["from_value"],
            to_value=r["to_value"],
            modules_add=list(r["modules_add"] or []),
            effective_from=r["effective_from"],
            reason=str(r["reason"]),
            status=r["status"],
            requested_by=cast(PersonRef, ref(r["requested_by"])),
            approver=ref(r["approver_user_id"]),
            decided_by=ref(r["decided_by"]),
            decided_at=r["decided_at"],
            applied_at=r["applied_at"],
            version=int(r["version"]),
            allowed_actions=allowed(r, ctx, may),  # type: ignore[arg-type] -- the three words
        )
        for r in rows
    ]


async def plan_requests(ctx: AuthContext, status: str | None) -> PlanRequestsOut:
    async with tenant_session(ctx.tenant) as session:
        rows = list((await session.execute(_REQUESTS)).mappings())
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    shown = [r for r in rows if status is None or r["status"] == status]
    return PlanRequestsOut(items=await _out(ctx, shown), counts=counts)


async def _one(ctx: AuthContext, request_id: UUID) -> PlanRequestOut:
    found = next((r for r in (await plan_requests(ctx, None)).items if r.id == request_id), None)
    if found is None:
        raise NotFound(TARGET)
    return found


async def create_request(ctx: AuthContext, body: PlanRequestIn) -> PlanRequestOut:
    current = await plan(ctx)
    from_value = (
        current.seats.total
        if body.kind == "seats"
        else current.included_agent_minutes
        if body.kind == "agent_minutes"
        else None
    )
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_ENSURE_POLICY, {"t": ctx.tenant_id})
        approver = await tx.session.scalar(
            text("SELECT partner_approver_user_id FROM usage_alert_policies")
        )
        made = await tx.session.scalar(
            text(
                "INSERT INTO plan_change_requests (tenant_id, kind, from_value, to_value, "
                "modules_add, effective_from, reason, requested_by, approver_user_id) VALUES "
                "(:t, :k, :f, :to, :m, :e, :r, :u, :a) RETURNING id"
            ),
            {"t": ctx.tenant_id, "k": body.kind, "f": from_value, "to": body.to_value,
             "m": list(body.modules_add), "e": body.effective_from, "r": body.reason,
             "u": ctx.user_id, "a": approver},
        )  # fmt: skip
        tx.record("plan_request.created", target=Target(TARGET, cast(UUID, made)))
        tx.emit(_Changed(tenant_id=ctx.tenant_id, request_id=cast(UUID, made)))
    return await _one(ctx, cast(UUID, made))


async def settle_request(
    ctx: AuthContext, request_id: UUID, decision: str, reason: str | None = None
) -> PlanRequestOut:
    """Approve (sent to Accrued) or decline, by a partner who did not ask; withdraw by the
    requester."""
    async with uow(ctx.tenant) as tx:
        row = (
            await tx.session.execute(
                text(
                    "SELECT status, requested_by FROM plan_change_requests WHERE id = :id "
                    "FOR UPDATE"
                ),
                {"id": request_id},
            )
        ).first()
        if row is None:
            raise NotFound(TARGET)
        if row.status != "awaiting_partner":
            raise PlanRequestNotPending(facts={"status": str(row.status)})
        if decision == "withdraw":
            if row.requested_by != ctx.user_id:
                raise NotFound(TARGET)
            status, by = "withdrawn", None
        else:
            if row.requested_by == ctx.user_id:
                raise PlanRequestSelfApproval(facts={"request": str(request_id)})
            status, by = ("sent_to_accrued" if decision == "approve" else "declined"), ctx.user_id
        await tx.session.execute(
            text(
                "UPDATE plan_change_requests SET status = :s, decided_by = :by, "
                "decided_at = CASE WHEN :by IS NULL THEN decided_at ELSE abacus_now() END, "
                "decline_reason = :reason, version = version + 1 WHERE id = :id"
            ),
            {"s": status, "by": by, "reason": reason, "id": request_id},
        )
        tx.record(f"plan_request.{status}", target=Target(TARGET, request_id))
        tx.emit(_Changed(tenant_id=ctx.tenant_id, request_id=request_id))
    return await _one(ctx, request_id)


__all__ = [
    "allowed",
    "billing_rates",
    "budget_alerts",
    "create_request",
    "engagement_budgets",
    "over_limit_policy",
    "plan",
    "plan_requests",
    "register_billing_rates",
    "register_workbench_activity",
    "rule_minutes",
    "set_billing_contact",
    "set_budget_alerts",
    "settle_request",
    "used_pct",
]
