"""A-03-T08 (TASK-2612; A-03 §3 F6 US-6.1; ADR-341 §5; ADR-050): the mapping rules in
`ledger.compute.mapping`, pure.

The row's acceptance, its compute half: "Granite Peak's 128 accounts are mapped by rule or left
Needs review with no suggested row." Synthetic accounts in Granite Peak's shape: 128 codes, a
prior year that confirmed some, ranges for most, and a handful no rule reaches.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from abacus.modules.ledger.compute.mapping import (
    CONFIDENCE,
    account_key,
    normalised_code,
    resolve_line,
    rule_line,
    subtotals,
    tallies,
)

CASH, AR, AP, REV = (uuid.uuid4() for _ in range(4))
BY_KEY = {"cash": CASH, "ar": AR, "ap": AP, "revenue": REV}
RANGES = [
    ("1000", "1099", CASH),
    ("1000", "1999", AR),
    ("2000", "2999", AP),
    ("4000", "4999", REV),
]
PRIOR = {
    normalised_code("1140"): "cash",
    normalised_code("1150"): "cash",
    normalised_code("ZZ-9"): "revenue",
}


def granite_peak_codes() -> list[str]:
    """128 codes: 40 cash/AR, 40 AP, 40 revenue, 8 in 5000s no rule holds."""
    return (
        [str(1000 + n * 20) for n in range(40)]
        + [str(2000 + n * 20) for n in range(40)]
        + [str(4000 + n * 20) for n in range(40)]
        + [str(5000 + n) for n in range(8)]
    )


def test_ac1_every_account_is_rule_mapped_or_needs_review_never_suggested() -> None:
    codes = granite_peak_codes()
    assert len(codes) == 128
    resolved = [resolve_line(c, None, PRIOR, BY_KEY, RANGES) for c in codes]
    methods = [m for _, m in resolved]
    assert set(methods) <= {"prior_year", "number_range", None}
    assert "suggested" not in {str(m) for m in methods}
    t = tallies(methods, [Decimal(0)] * len(codes))
    assert (t.total, t.mapped, t.need_review) == (128, 120, 8)
    assert t.prior_year == 1  # 1140 matched the prior year's cash line
    assert t.number_range == 119
    assert t.tb_balanced


def test_ac1_order_edit_then_prior_then_first_range() -> None:
    edited = uuid.uuid4()
    assert resolve_line("1150", edited, PRIOR, BY_KEY, RANGES) == (edited, "manual")
    assert resolve_line("1150", None, PRIOR, BY_KEY, RANGES) == (CASH, "prior_year")
    assert resolve_line("1050", None, PRIOR, BY_KEY, RANGES) == (
        CASH,
        "number_range",
    )  # first wins
    assert resolve_line("1500", None, PRIOR, BY_KEY, RANGES) == (AR, "number_range")
    assert resolve_line("zz9", None, PRIOR, BY_KEY, RANGES) == (REV, "prior_year")  # normalised
    assert resolve_line("5001", None, PRIOR, BY_KEY, RANGES) == (None, None)


def test_ac1_a_prior_key_missing_from_this_version_falls_to_the_ranges() -> None:
    prior = {normalised_code("2040"): "retired_line"}
    assert resolve_line("2040", None, prior, BY_KEY, RANGES) == (AP, "number_range")


def test_numbers_compare_numerically_and_text_after() -> None:
    assert account_key("900") < account_key("1000") < account_key("A-1")
    assert rule_line("950", [("900", "999", CASH)]) == CASH
    assert rule_line("ABC", [("1000", "9999", CASH)]) is None


def test_confidence_is_words() -> None:
    assert CONFIDENCE == {"prior_year": "high", "number_range": "medium", "manual": None}


def test_tb_balanced_reads_the_snapshot() -> None:
    assert not tallies(["number_range"], [Decimal("0.01")]).tb_balanced


def test_subtotals_read_off_only_against_a_summary_line() -> None:
    out = subtotals(
        ["cash", "ap", "equity"],
        [("cash", Decimal("100")), ("cash", Decimal("50")), ("ap", Decimal("-30"))],
        {"cash": Decimal("140"), "ap": Decimal("-30")},
    )
    assert [(s.grouping_key, s.subtotal, s.source_total, s.off) for s in out] == [
        ("cash", Decimal("150"), Decimal("140"), Decimal("10")),
        ("ap", Decimal("-30"), Decimal("-30"), None),
        ("equity", Decimal("0"), None, None),
    ]
