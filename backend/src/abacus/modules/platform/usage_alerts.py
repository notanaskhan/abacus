"""The usage alert evaluator (G-04-T12; SPEC-680 AC-35, AC-36, AC-38, AC-39; ADM-14 b, c;
DEC-5419; amber).

Ledger-driven: after a run's minutes post (`metering.on_run_completed`) and nightly for every firm
(`UsageAlertReconcileWorkflow`), this usage month's totals are compared with the firm's rules and
each engagement's budget. A threshold crossed for the first time writes one
`usage_alert_events` row (unique per scope, rule or engagement, usage month and threshold, so a
replayed event and the nightly reconcile write nothing more) and emits its C16 event naming the
recipients: the rule's people and groups (partners, firm admins) for the firm; the engagement's
managers (else its leads) for an engagement budget. Minutes and thresholds are code's integers.
ADM-14's banner and helper read `alerts_sent` through `GET /v1/firm/usage` (G-04-T18).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import DomainEvent, Ref, Target, uow
from abacus.modules.identity.api import (
    engagement_leads,
    engagement_managers,
    firm_admins,
    names_of,
    partner_members,
)
from abacus.modules.platform.metering import usage_month_of
from abacus.modules.platform.plan_usage import rule_minutes

_I = classified("internal")
_log = get_logger(__name__)
READER: Final = "usage_alerts"


class UsageThresholdCrossed(DomainEvent):
    """C16 `usage_threshold_crossed` (AC-35): the rule's recipients."""

    event_type: ClassVar[str] = "usage.threshold_crossed"

    usage_month: Annotated[str, _I]
    threshold_pct: Annotated[int, _I]
    minutes: Annotated[int, _I]
    recipient_user_ids: Annotated[list[UUID], _I]


class EngagementBudgetCrossed(DomainEvent):
    """C16 `engagement_budget_threshold_crossed` (AC-38): the engagement's managers."""

    event_type: ClassVar[str] = "engagement_budget.threshold_crossed"

    engagement_id: Annotated[UUID, _I]
    usage_month: Annotated[str, _I]
    threshold_pct: Annotated[int, _I]
    minutes: Annotated[int, _I]
    recipient_user_ids: Annotated[list[UUID], _I]


@dataclass(frozen=True)
class Rule:
    id: UUID
    pct: int
    people: tuple[UUID, ...]
    groups: tuple[str, ...]


def crossed(total: int, included: int, rules: Sequence[Rule]) -> list[Rule]:
    """The rules this total has reached (at or over), lowest first; none without included
    minutes."""
    if included <= 0:
        return []
    return sorted(
        (r for r in rules if total >= rule_minutes(included, r.pct)), key=lambda r: r.pct
    )


def engagement_crossed(used: int, budget: int, alert_pct: int) -> bool:
    return budget > 0 and used * 100 >= budget * alert_pct


_TOTALS: Final = text(
    "SELECT engagement_id, sum(minutes) AS minutes FROM usage_month_rollups "
    "WHERE usage_month = :m GROUP BY engagement_id"
)
_INCLUDED: Final = text(
    "SELECT included_agent_minutes FROM plan_entitlements WHERE valid_from <= abacus_now() "
    "ORDER BY valid_from DESC, created_at DESC LIMIT 1"
)
_RULES: Final = text(
    "SELECT id, threshold_pct, recipient_user_ids, recipient_groups FROM usage_alert_rules "
    "WHERE enabled ORDER BY threshold_pct"
)
_POLICY: Final = text(
    "SELECT engagement_default_minutes, engagement_alert_pct FROM usage_alert_policies"
)
_RECORD: Final = text(
    "INSERT INTO usage_alert_events (tenant_id, scope, rule_id, engagement_id, usage_month, "
    "threshold_pct, crossed_at, minutes_at_crossing, sent_to) VALUES (:t, :scope, :rule, :e, "
    ":m, :p, abacus_now(), :minutes, :to) ON CONFLICT DO NOTHING RETURNING id"
)


async def _recipients(tenant_id: UUID, rule: Rule) -> list[UUID]:
    people = set(rule.people)
    if "partners" in rule.groups:
        people |= set(await partner_members(tenant_id))
    if "firm_admins" in rule.groups:
        people |= set(await firm_admins(tenant_id))
    return sorted(people, key=str)


async def _managers(tenant_id: UUID, engagement_id: UUID) -> list[UUID]:
    managers = await engagement_managers(tenant_id, engagement_id)
    return managers or sorted(await engagement_leads(tenant_id, engagement_id), key=str)


async def evaluate(tenant_id: UUID, usage_month: str | None = None) -> int:
    """Record and announce each first crossing this usage month; returns the rows written."""
    tenant = TenantContext(tenant_id, "system", READER)
    month = usage_month or usage_month_of(await clock.today(tenant))
    async with tenant_session(tenant) as session:
        totals = list((await session.execute(_TOTALS, {"m": month})).mappings())
        included = int(await session.scalar(_INCLUDED) or 0)
        rules = [
            Rule(r.id, int(r.threshold_pct), tuple(r.recipient_user_ids or ()),
                 tuple(r.recipient_groups or ()))
            for r in await session.execute(_RULES)
        ]  # fmt: skip
        policy = (await session.execute(_POLICY)).first()
    firm_total = sum(int(r["minutes"]) for r in totals)
    budget = 1500 if policy is None else int(policy[0])
    alert_pct = 80 if policy is None else int(policy[1])
    written = 0
    for rule in crossed(firm_total, included, rules):
        to = await _recipients(tenant_id, rule)
        async with uow(tenant) as tx:
            made = await tx.session.scalar(
                _RECORD,
                {"t": tenant_id, "scope": "firm", "rule": rule.id, "e": None, "m": month,
                 "p": rule.pct, "minutes": firm_total, "to": to},
            )  # fmt: skip
            if made is None:
                continue
            tx.record("usage_alert.crossed", target=Target("firm", tenant_id),
                      after=Ref(threshold_pct=rule.pct, usage_month=month))  # fmt: skip
            tx.emit(UsageThresholdCrossed(usage_month=month, threshold_pct=rule.pct,
                                          minutes=firm_total, recipient_user_ids=to))  # fmt: skip
            written += 1
    for row in totals:
        engagement = cast("UUID | None", row["engagement_id"])
        used = int(row["minutes"])
        if engagement is None or not engagement_crossed(used, budget, alert_pct):
            continue
        to = await _managers(tenant_id, engagement)
        async with uow(tenant) as tx:
            made = await tx.session.scalar(
                _RECORD,
                {"t": tenant_id, "scope": "engagement", "rule": None, "e": engagement, "m": month,
                 "p": alert_pct, "minutes": used, "to": to},
            )  # fmt: skip
            if made is None:
                continue
            tx.record("usage_alert.crossed", target=Target("engagement", engagement),
                      after=Ref(threshold_pct=alert_pct, usage_month=month))  # fmt: skip
            tx.emit(EngagementBudgetCrossed(engagement_id=engagement, usage_month=month,
                                            threshold_pct=alert_pct, minutes=used,
                                            recipient_user_ids=to))  # fmt: skip
            written += 1
    return written


@dataclass(frozen=True)
class Banner:
    """ADM-14 b and c: the newest firm alert this usage month and the minutes over included."""

    threshold_pct: int
    crossed_at: datetime
    recipients: tuple[str, ...]
    over_included: int


async def banner_facts(tenant: TenantContext) -> Banner | None:
    month = usage_month_of(await clock.today(tenant))
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT threshold_pct, crossed_at, sent_to FROM usage_alert_events "
                    "WHERE scope = 'firm' AND usage_month = :m "
                    "ORDER BY threshold_pct DESC, crossed_at DESC LIMIT 1"
                ),
                {"m": month},
            )
        ).first()
        total = int(
            await session.scalar(
                text(
                    "SELECT coalesce(sum(minutes), 0) FROM usage_month_rollups "
                    "WHERE usage_month = :m"
                ),
                {"m": month},
            )
            or 0
        )
        included = int(await session.scalar(_INCLUDED) or 0)
    if row is None:
        return None
    sent = cast("list[UUID]", list(row.sent_to or []))
    people = await names_of(sent)
    return Banner(
        int(row.threshold_pct),
        row.crossed_at,
        tuple(people[u] for u in sent if u in people),
        max(total - included, 0),
    )


@dataclass(frozen=True)
class SentAlert:
    """One firm alert sent this usage month (ADM-14 b and c): the threshold, when it was crossed
    and who it went to, by name."""

    threshold_pct: int
    crossed_at: datetime
    recipients: tuple[str, ...]


_SENT: Final = text(
    "SELECT threshold_pct, crossed_at, sent_to FROM usage_alert_events "
    "WHERE scope = 'firm' AND usage_month = :m ORDER BY threshold_pct, crossed_at"
)


async def alerts_sent(tenant: TenantContext, usage_month: str) -> list[SentAlert]:
    """The usage month's firm alerts, lowest threshold first; the caller has authorised
    `usage.read`. Recipients are named in the order the evaluator recorded them."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_SENT, {"m": usage_month})).all()
    ids = {u for row in rows for u in cast("list[UUID]", list(row.sent_to or []))}
    people = await names_of(sorted(ids, key=str)) if ids else {}
    return [
        SentAlert(
            int(row.threshold_pct),
            row.crossed_at,
            tuple(people[u] for u in cast("list[UUID]", list(row.sent_to or [])) if u in people),
        )
        for row in rows
    ]


async def evaluate_all() -> int:
    """The nightly reconcile: every firm, each in its own context; a failure is logged and the
    next firm runs."""
    from abacus.modules.identity.api import firm_tenant_ids

    written = 0
    for tenant_id in await firm_tenant_ids():
        try:
            written += await evaluate(tenant_id)
        except Exception as exc:
            _log.error("usage_alerts.failed", tenant_id=str(tenant_id), error=type(exc).__name__)
    return written


__all__ = [
    "Banner",
    "EngagementBudgetCrossed",
    "SentAlert",
    "UsageThresholdCrossed",
    "alerts_sent",
    "banner_facts",
    "crossed",
    "engagement_crossed",
    "evaluate",
    "evaluate_all",
]
