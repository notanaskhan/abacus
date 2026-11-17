# ac-test-author: notanaskhan
"""G-04-T15 (TASK-8539; ADR-078): the AC suite for AY's amber plan and usage work (ADM-14).

Written from G-04 §4 and SPEC ADM-14's acceptance criteria, not from the services' own tests: the
plan read model's seat tiles (sandboxes excluded, counted over the whole directory), alert rule
minutes, once-per-usage-month crossings (an alert never fires twice in a usage month), the plan
request partner gate (a requester never approves their own request) and the billing-rate fake
refused outside synthetic firms.
"""

from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.modules.identity.api import AuthContext
from abacus.modules.platform import plan_usage
from abacus.modules.platform.console import tiles
from abacus.modules.platform.metering import usage_month_bounds, usage_month_of
from abacus.modules.platform.plan_usage import allowed, rule_minutes, used_pct
from abacus.modules.platform.usage_alerts import Rule, crossed, engagement_crossed

MIGRATION = (
    Path(__file__).resolve().parents[3] / "migrations" / "versions"
    / "0920_platform_console_plan_support.py"
)  # fmt: skip


# ---- plan read model: seats exclude sandboxes -------------------------------------------------


def _tenant(health: str, used: int, total: int, sandbox_of: object = None) -> dict[str, Any]:
    return {"health": health, "seats_used": used, "seats_total": total, "sandbox_of": sandbox_of}


def test_seats_used_is_404_of_490_with_the_sandbox_excluded() -> None:
    rows = [
        _tenant("healthy", 46, 46),
        _tenant("healthy", 46, 46, sandbox_of=uuid.uuid4()),
        _tenant("healthy", 128, 140),
        _tenant("degraded", 212, 220),
        _tenant("healthy", 18, 20),
        _tenant("onboarding", 0, 64),
    ]
    t = tiles(rows)  # type: ignore[arg-type] -- RowMapping-shaped dicts
    assert (t.tenants, t.healthy, t.degraded, t.onboarding) == (6, 4, 1, 1)
    assert (t.seats_used, t.seats_provisioned) == (404, 490)


# ---- alert rules: minutes, crossings, once per usage month -------------------------------------


def test_a_rules_minutes_are_the_included_minutes_times_its_percent_rounded_down() -> None:
    assert rule_minutes(3000, 80) == 2400
    assert rule_minutes(1999, 75) == 1499


def _rule(pct: int) -> Rule:
    return Rule(uuid.uuid4(), pct, (), ())


def test_crossings_are_the_rules_reached_lowest_first() -> None:
    rules = [_rule(100), _rule(50), _rule(80)]
    assert [r.pct for r in crossed(2400, 3000, rules)] == [50, 80]
    assert [r.pct for r in crossed(3000, 3000, rules)] == [50, 80, 100]
    assert crossed(5000, 0, rules) == []


def test_an_engagement_budget_crosses_at_or_over_its_percent() -> None:
    assert engagement_crossed(1200, 1500, 80) is True
    assert engagement_crossed(1199, 1500, 80) is False
    assert engagement_crossed(10, 0, 80) is False
    assert used_pct(1200, 1500) == 80


def test_an_alert_fires_once_per_usage_month_by_the_database() -> None:
    body = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX usage_alert_events_once ON usage_alert_events" in body
    assert "coalesce(rule_id, engagement_id), usage_month, threshold_pct)" in body


def test_the_usage_month_runs_from_the_anchor_day() -> None:
    assert usage_month_bounds("2026-09") == (date(2026, 9, 15), date(2026, 10, 14))
    assert usage_month_of(date(2026, 10, 14)) == "2026-09"
    assert usage_month_of(date(2026, 10, 15)) == "2026-10"
    assert usage_month_of(date(2026, 1, 3)) == "2025-12"


# ---- plan requests: the partner gate ----------------------------------------------------------

ME = uuid.uuid4()
OTHER = uuid.uuid4()


def _ctx(user: uuid.UUID) -> AuthContext:
    return cast("AuthContext", SimpleNamespace(user_id=user))


def test_a_requester_never_approves_their_own_plan_request() -> None:
    row = {"status": "awaiting_partner", "requested_by": ME}
    assert allowed(row, _ctx(ME), may_approve=True) == ["withdraw"]
    assert allowed(row, _ctx(OTHER), may_approve=True) == ["approve", "decline"]
    assert allowed(row, _ctx(OTHER), may_approve=False) == []


def test_a_decided_request_offers_nothing() -> None:
    for status in ("approved", "declined", "applied", "withdrawn"):
        assert allowed({"status": status, "requested_by": ME}, _ctx(ME), may_approve=True) == []


# ---- billing rates: the fake card only for a synthetic firm ------------------------------------


@pytest.mark.parametrize(("synthetic", "connected"), [(False, False), (True, True)])
async def test_the_fake_rate_card_is_refused_outside_synthetic_firms(
    monkeypatch: pytest.MonkeyPatch, synthetic: bool, connected: bool
) -> None:
    async def is_synthetic(_tenant: object) -> bool:
        return synthetic

    monkeypatch.setattr(plan_usage, "is_synthetic_firm", is_synthetic)
    monkeypatch.setattr(plan_usage, "_RATES", [])
    out = await plan_usage.billing_rates(SimpleNamespace(tenant=object()))  # type: ignore[arg-type]
    assert out.connected is connected
    assert (out.provider_key == "fake_practice_management") is synthetic
