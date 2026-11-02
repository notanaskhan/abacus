"""N-04-T04 (TASK-3003; DEC-2053): the notices compute library's goldens and properties.

Row acceptance: "Goldens for Whitley (3,120; 686.40; 753.01), Collins and Santos pass, and the
library imports nothing beyond the kernel numeric and calendar packages." The import rule is the
import-linter contract (`make check-fast`); the goldens are N-04 US-4.3, US-4.5, US-2.2 and US-7.4.
"""

from __future__ import annotations

import ast
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.notices.compute import (
    balance_due,
    bracket,
    clocks,
    notice_types,
    payments,
    plausibility,
    risk,
    underreporter,
)
from abacus.modules.notices.compute.underreporter import InformationReturn, ProposedLine

COMPUTE = Path(underreporter.__file__).parent
DEMO = date(2026, 9, 14)  # Mon Sep 14, 2026 (NOT-01 a)


def _whitley() -> underreporter.Comparison:
    return underreporter.compare(
        {"interest": D("412.00"), "taxable_income": D("148600.00"), "tax": D("22798.00")},
        [
            ProposedLine("interest", "Interest income", D("412.00"), D("3532.00")),
            ProposedLine("taxable_income", "Taxable income", D("148600.00"), D("151720.00")),
            ProposedLine("tax", "Tax", D("22798.00"), D("23484.40")),
        ],
        [
            InformationReturn("Front Range Bank", "1099-INT", D("1870.00"), on_return=False),
            InformationReturn("Lakeview Credit Union", "1099-INT", D("1250.00"), on_return=False),
        ],
    )


def test_ac_whitley_rows_and_the_difference_is_explained() -> None:
    c = _whitley()
    assert [(r.key, r.as_filed, r.irs, r.difference) for r in c.rows] == [
        ("interest", D("412.00"), D("3532.00"), D("3120.00")),
        ("taxable_income", D("148600.00"), D("151720.00"), D("3120.00")),
        ("tax", D("22798.00"), D("23484.40"), D("686.40")),
    ]
    assert c.income_difference == D("3120.00") == c.unreported  # 1,870.00 + 1,250.00
    assert c.difference_explained


def test_ac_whitley_bracket_check_agrees_at_686_40() -> None:
    table = bracket.schedule(2024, "mfj")
    assert table is not None
    assert bracket.tax(D("148600"), table) == D("22798.00")
    assert bracket.tax(D("151720"), table) == D("23484.40")
    check = bracket.check("mfj", 2024, D("148600"), D("151720"), D("686.40"))
    assert (check.checked, check.rate, check.expected, check.agrees) == (
        True,
        D("0.22"),
        D("686.40"),
        True,
    )


def test_ac_whitley_total_foots_to_753_01_with_the_notices_interest() -> None:
    footing = payments.foot(D("686.40"), D("66.61"), None, D("753.01"))
    assert footing.foots and footing.computed_total == D("753.01")


def test_ac_collins_basis_on_8949_makes_the_gain_zero_and_rates_are_preferential() -> None:
    c = underreporter.compare(
        {"capital_gains": D("0.00")},
        [ProposedLine("capital_gains", "Capital gain", D("0.00"), D("13200.00"))],
        [
            InformationReturn(
                "Broker", "1099-B", D("13200.00"), on_return=True, line_key="capital_gains"
            )
        ],
    )
    assert c.rows[0].difference == D("13200.00")
    assert c.unreported == D("0.00")  # the sale is on the return's Form 8949, with its basis
    assert not c.difference_explained
    check = bracket.check("mfj", 2023, D("0"), D("13200"), D("1980.00"), preferential=True)
    assert not check.checked and check.reason == bracket.PREFERENTIAL


def test_ac_santos_cp14_window_and_risk() -> None:
    cp14 = notice_types.lookup("CP14")
    assert (cp14.key, cp14.analysis_kind, cp14.window_days) == ("cp14", "balance_due", 21)
    assert (
        plausibility.respond_by(cp14, date(2026, 9, 10), date(2026, 10, 1)).verdict == "plausible"
    )
    assert risk.band(date(2026, 10, 1), DEMO) == risk.Risk("amber", 17)


def test_ac_the_index_risk_bands() -> None:
    assert risk.band(date(2026, 9, 21), DEMO).band == "red"  # N4, 7 days
    assert risk.band(date(2026, 9, 23), DEMO).band == "amber"  # N1, 9 days
    assert risk.band(date(2026, 10, 11), DEMO).band == "amber"  # N9, 27 days
    assert risk.band(None, DEMO).band == "none"


def test_ac_cp2000_respond_by_is_thirty_days_and_a_mismatch_is_never_corrected() -> None:
    cp2000 = notice_types.lookup("cp2000")
    ok = plausibility.respond_by(cp2000, date(2026, 8, 24), date(2026, 9, 23))
    assert ok == plausibility.Plausibility("plausible", date(2026, 9, 23))
    off = plausibility.respond_by(cp2000, date(2026, 8, 24), date(2026, 9, 30))
    assert off.verdict == "check" and off.expected == date(2026, 9, 23)
    assert (
        plausibility.respond_by(notice_types.lookup("CP501"), DEMO, DEMO).verdict == "not_checked"
    )


def test_ac_follow_up_is_sixty_calendar_days_never_rolled() -> None:
    assert clocks.follow_up_on(date(2026, 9, 17)) == date(2026, 11, 16)
    with pytest.raises(ValueError):
        clocks.follow_up_on(date(2026, 9, 17), 0)


def test_unmapped_codes_fall_back_by_agency() -> None:
    assert notice_types.lookup("DTF-160", agency="state").key == "state_generic"
    assert notice_types.lookup("LTR 12C").key == "unknown"
    assert notice_types.lookup("CP3219A").partner_owned


def test_balance_due_compares_the_notice_with_the_return() -> None:
    result = balance_due.compare(D("10000.00"), D("8894.00"), D("1106.00"))
    assert result.return_balance == D("1106.00") and result.agrees


def test_same_inputs_same_stamp_and_different_inputs_differ() -> None:
    assert _whitley().stamp == _whitley().stamp
    a = bracket.check("mfj", 2024, D("148600"), D("151720"), D("686.40")).stamp
    b = bracket.check("mfj", 2024, D("148600"), D("151720"), D("686.41")).stamp
    assert a.inputs_hash != b.inputs_hash and len(a.inputs_hash) == 64


def test_the_library_imports_only_the_kernel_numeric_and_calendar() -> None:
    allowed = ("abacus.kernel.numeric", "abacus.kernel.calendar", "abacus.modules.notices.compute")
    for path in COMPUTE.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("abacus")
            ):
                assert node.module.startswith(allowed), (path.name, node.module)


money = st.decimals(min_value=0, max_value=10_000_000, places=2, allow_nan=False)


@given(money, money)
def test_property_tax_never_falls_as_income_rises(a: D, b: D) -> None:
    table = bracket.schedule(2025, "single")
    assert table is not None
    low, high = sorted((a, b))
    assert bracket.tax(low, table) <= bracket.tax(high, table)


@given(money, money, money)
def test_property_payments_foot_exactly_when_the_total_is_the_sum(t: D, i: D, p: D) -> None:
    assert payments.foot(t, i, p, t + i + p).foots


@given(st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 1, 1)), st.integers(1, 365))
def test_property_follow_up_is_pure_calendar_arithmetic(sent: date, days: int) -> None:
    assert clocks.follow_up_on(sent, days) == sent + timedelta(days=days)
