"""Brightwater Hale's plan & usage rows for the scenario loader (G-04-T13; DEC-5421): the plan
version, the budget-alert policy and rules, and the alert events the usage history crossed.
Synthetic firms only (DEC-1530); a second call writes nothing."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import is_synthetic_firm


@dataclass(frozen=True)
class SeedPlan:
    plan_code: str
    term_start: date
    term_end: date
    renewal_on: date
    included_agent_minutes: int
    seats_total: int
    usage_month_anchor_day: int
    billing_contact: UUID | None
    partner_approver: UUID | None
    engagement_default_minutes: int
    engagement_alert_pct: int


@dataclass(frozen=True)
class SeedRule:
    threshold_pct: int
    recipients: tuple[UUID, ...]


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "scenario:plan_usage")


async def seed_synthetic_plan(tenant_id: UUID, plan: SeedPlan, rules: Sequence[SeedRule]) -> bool:
    """The plan version, policy and rules; False when the firm already has a plan version."""
    tenant = _system(tenant_id)
    if not await is_synthetic_firm(tenant):
        raise NotFound("plan_entitlements")
    async with uow(tenant) as tx:
        if await tx.session.scalar(text("SELECT 1 FROM plan_entitlements LIMIT 1")):
            return False
        await tx.session.execute(
            text(
                "INSERT INTO plan_entitlements (tenant_id, plan_code, term_start, term_end, "
                "renewal_on, usage_month_anchor_day, included_agent_minutes, seats_total, "
                "changed_by_staff, change_reason) VALUES (:t, :code, :ts, :te, :r, :a, :m, :s, "
                "'scenario', 'Synthetic plan at term start (G-04-T13)')"
            ),
            {"t": tenant_id, "code": plan.plan_code, "ts": plan.term_start, "te": plan.term_end,
             "r": plan.renewal_on, "a": plan.usage_month_anchor_day,
             "m": plan.included_agent_minutes, "s": plan.seats_total},
        )  # fmt: skip
        await tx.session.execute(
            text(
                "INSERT INTO usage_alert_policies (tenant_id, engagement_default_minutes, "
                "engagement_alert_pct, billing_contact_user_id, partner_approver_user_id) "
                "VALUES (:t, :m, :p, :b, :a) ON CONFLICT (tenant_id) DO NOTHING"
            ),
            {"t": tenant_id, "m": plan.engagement_default_minutes,
             "p": plan.engagement_alert_pct, "b": plan.billing_contact,
             "a": plan.partner_approver},
        )  # fmt: skip
        for rule in rules:
            await tx.session.execute(
                text(
                    "INSERT INTO usage_alert_rules (tenant_id, threshold_pct, recipient_user_ids) "
                    "VALUES (:t, :p, :u) ON CONFLICT (tenant_id, level, threshold_pct) DO NOTHING"
                ),
                {"t": tenant_id, "p": rule.threshold_pct, "u": list(rule.recipients)},
            )
        tx.record("plan.seeded", target=Target("firm", tenant_id), after=Ref(rules=len(rules)))
    return True


async def seed_synthetic_alert(
    tenant_id: UUID,
    *,
    usage_month: str,
    threshold_pct: int,
    crossed_at: datetime,
    minutes: int,
    sent_to: Sequence[UUID],
) -> bool:
    """One firm alert the scenario's usage crossed (ADM-14 a, b); its rule must exist."""
    tenant = _system(tenant_id)
    if not await is_synthetic_firm(tenant):
        raise NotFound("usage_alert_events")
    async with uow(tenant) as tx:
        made = await tx.session.scalar(
            text(
                "INSERT INTO usage_alert_events (tenant_id, scope, rule_id, usage_month, "
                "threshold_pct, crossed_at, minutes_at_crossing, sent_to) SELECT :t, 'firm', "
                "r.id, :m, :p, :at, :min, :to FROM usage_alert_rules r WHERE r.threshold_pct = :p "
                "ON CONFLICT DO NOTHING RETURNING id"
            ),
            {"t": tenant_id, "m": usage_month, "p": threshold_pct, "at": crossed_at,
             "min": minutes, "to": list(sent_to)},
        )  # fmt: skip
        if made is None:
            return False
        tx.record("usage_alert.seeded", target=Target("firm", tenant_id),
                  after=Ref(threshold_pct=threshold_pct))  # fmt: skip
    return True


__all__ = ["SeedPlan", "SeedRule", "seed_synthetic_alert", "seed_synthetic_plan"]
