"""A-03-T17 (TASK-2815; DEC-1864): the independent AC suite (ADR-078) for the ledger mapping and
grouping work (A-03-T01, T06, T08, T21), written apart from the code it tests.

Row acceptance: "The suite passes on main and fails when any human-only CHECK, the freeze
trigger, the unmapped guard or the stale computation is removed." This file holds the pure half:
the rules' order and goldens transcribed by hand (Granite Peak's 128 accounts, 8,090,000 +
310,000 = 8,400,000 on a Harlow & Pike-shaped grouping), the kernel helpers (allocate footing,
business days over a passed holiday set), the reserved `suggested` state, and the matrix. The
database half is `tests/integration/test_a03t17_mapping_guards.py`. The stale computation
(A-03-T14's `follow_tb_version`) is not on main: its tests join with it.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import get_args

import pytest

from abacus.kernel.calendar import add_business_days, is_business_day, roll
from abacus.kernel.numeric import allocate
from abacus.modules.assurance import mapping as assurance_mapping
from abacus.modules.identity.authz import _matrix
from abacus.modules.ledger.compute import mapping as rules

D = Decimal
CLIENTS = ("client_admin", "client_contributor", "third_party")


# --- the rules -----------------------------------------------------------------------------------


def test_the_order_is_edit_then_prior_year_then_ranges_then_unmapped() -> None:
    edited, prior_line, range_line = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    by_key = {"cash": prior_line}
    prior = {"1000": "cash"}
    ranges = [("1000", "1999", range_line)]
    assert rules.resolve_line("1000", edited, prior, by_key, ranges) == (edited, "manual")
    assert rules.resolve_line("1000", None, prior, by_key, ranges) == (prior_line, "prior_year")
    assert rules.resolve_line("1500", None, prior, by_key, ranges) == (range_line, "number_range")
    assert rules.resolve_line("2500", None, prior, by_key, ranges) == (None, None)


def test_numeric_codes_compare_as_numbers_and_codes_normalise() -> None:
    line = uuid.uuid4()
    assert rules.rule_line("900", [("100", "999", line)]) == line
    assert rules.rule_line("1000", [("100", "999", line)]) is None
    assert rules.normalised_code("1000-01 ") == rules.normalised_code("100001")


def test_the_suggested_state_is_reserved_and_no_rule_writes_it() -> None:
    assert "suggested" not in get_args(rules.Method)
    assert rules.CONFIDENCE["manual"] is None


def test_granite_peak_maps_128_of_128_and_balances() -> None:
    """128 accounts in four ranges (transcribed from AUD-31 f: 128 of 128, TB balanced 1 of 1)."""
    lines = [uuid.uuid4() for _ in range(4)]
    ranges = [("1000", "1999", lines[0]), ("2000", "2999", lines[1]), ("3000", "3999", lines[2])]
    ranges.append(("4000", "9999", lines[3]))
    codes = [str(1000 + 60 * i) for i in range(128)]
    methods: list[rules.Method | None] = [
        rules.resolve_line(c, None, {}, {}, ranges)[1] for c in codes
    ]
    balances = [D("100.00")] * 64 + [D("-100.00")] * 64
    t = rules.tallies(methods, balances)
    assert (t.total, t.mapped, t.need_review, t.number_range) == (128, 128, 0, 128)
    assert t.tb_balanced


def test_an_unbalanced_tb_is_not_balanced() -> None:
    assert not rules.tallies(["manual"], [D("0.01")]).tb_balanced


def test_harlow_and_pike_subtotal_ties_8_090_000_plus_310_000() -> None:
    mapped = [("cash", D("8090000.00")), ("cash", D("310000.00"))]
    [tie] = rules.subtotals(["cash"], mapped, {"cash": D("8400000.00")})
    assert (tie.subtotal, tie.off) == (D("8400000.00"), None)
    [off] = rules.subtotals(["cash"], mapped, {"cash": D("8390000.00")})
    assert off.off == D("10000.00")  # reads off; never adjusted


# --- the kernel helpers (A-03-T21) ---------------------------------------------------------------

HOLIDAYS = frozenset({date(2026, 1, 1), date(2026, 1, 19)})


def test_business_days_skip_weekends_and_the_passed_holidays_only() -> None:
    assert add_business_days(date(2025, 12, 31), 1, HOLIDAYS) == date(2026, 1, 2)
    assert add_business_days(date(2026, 1, 16), 1, HOLIDAYS) == date(2026, 1, 20)
    assert add_business_days(date(2026, 1, 16), 1, frozenset()) == date(2026, 1, 19)
    assert roll(date(2026, 1, 17), HOLIDAYS) == (date(2026, 1, 20), True)
    assert is_business_day(date(2026, 1, 2), HOLIDAYS)
    with pytest.raises(ValueError):
        add_business_days(date(2026, 1, 2), -1, HOLIDAYS)


@pytest.mark.parametrize("total", [D("100.00"), D("-100.00"), D("0.03"), D("8400000.00")])
def test_allocate_always_foots(total: Decimal) -> None:
    for half_up in (False, True):
        shares = allocate(total, [D(3), D(3), D(1)], 2, half_up_shares=half_up)
        assert sum(shares, D(0)) == total


# --- the matrix ----------------------------------------------------------------------------------

READS = ("grouping_set.read", "mapping_set.read")
WRITES = (
    "grouping_set.import",
    "grouping_set.publish",
    "mapping_set.run",
    "mapping_set.confirm",
    "account_mapping.edit",
)


@pytest.mark.parametrize("action", READS + WRITES)
def test_no_client_principal_holds_a_mapping_action(action: str) -> None:
    cells = _matrix.ACTIONS[action]
    for role in CLIENTS:
        assert cells.get(role) in (None, "deny"), (action, role)


@pytest.mark.parametrize("action", WRITES)
def test_the_agent_holds_no_mapping_write(action: str) -> None:
    assert _matrix.ACTIONS[action].get("agent") in (None, "deny"), action


def test_the_system_only_runs_the_rules() -> None:
    assert _matrix.ACTIONS["mapping_set.run"].get("system") == "allow"
    for action in ("mapping_set.confirm", "account_mapping.edit", "grouping_set.publish"):
        assert _matrix.ACTIONS[action].get("system") in (None, "deny"), action


def test_the_unmapped_guard_answers_its_code() -> None:
    found = [
        v
        for v in vars(assurance_mapping).values()
        if isinstance(v, type) and getattr(v, "code", None) == "unmapped_accounts"
    ]
    assert found, "confirm must refuse 409 unmapped_accounts while any account is unmapped"
