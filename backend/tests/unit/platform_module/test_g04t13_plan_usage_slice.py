"""G-04-T13: the `plan_usage` seed slice ties to the figure book (`g04_fixtures`; ADM-14 a, b;
DEC-5421): 46 seats, 20,000 included, rules at 75, 90 and 100, alerts at 15,000 and 18,000,
renewal in 92 days at Thu Oct 1."""

from __future__ import annotations

from datetime import date

from abacus.modules.platform import g04_fixtures as fx
from abacus.modules.platform.plan_usage import rule_minutes
from abacus_tools.synthetic import g04_tenants
from abacus_tools.synthetic.scenarios.brightwater_hale import plan_usage_slice as s
from abacus_tools.synthetic.scenarios.brightwater_hale import usage_slice


def _plan() -> dict[str, object]:
    return dict(next(e for e in s.plan_usage_events() if e.kind == "platform.plan_seeded").data)


def test_the_plan_row_is_the_figure_books() -> None:
    plan = _plan()
    assert plan["seats_total"] == fx.SEATS_TOTAL == 46
    assert plan["included_agent_minutes"] == fx.INCLUDED_MINUTES == 20_000
    assert plan["anchor_day"] == fx.ANCHOR_DAY == 15
    assert (date.fromisoformat(str(plan["renewal_on"])) - date(2026, 10, 1)).days == 92
    assert [r["pct"] for r in plan["rules"]] == list(fx.THRESHOLDS)  # type: ignore[index, union-attr] -- the slice's dicts


def test_the_alerts_are_codes_thresholds_and_the_ledger_reaches_them() -> None:
    for pct, _, minutes, _ in s.ALERTS:
        assert minutes == rule_minutes(fx.INCLUDED_MINUTES, pct)
    assert usage_slice.ADM14_TOTAL == fx.used_oct_1() == 14_920
    assert fx.USED_OCT_9 >= 18_000 > fx.used_oct_1() >= 0
    assert fx.USED_OCT_14 == 20_860


def test_the_console_goldens_hold() -> None:
    assert g04_tenants.tiles()["tenants"] == 6 == 4 + 1 + 1
    assert (g04_tenants.tiles()["seats_used"], g04_tenants.tiles()["seats_provisioned"]) == (
        404,
        490,
    )
