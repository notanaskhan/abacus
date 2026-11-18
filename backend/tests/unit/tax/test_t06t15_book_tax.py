"""T-06-T15 (SPEC-702; DEC-5626): E4 on Ridgeline's 2025 Form 1065 (TXP-04) and Granite Peak's
FY2026 Form 1120 (TXP-13 d)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.tax.compute import book_tax as e4

D = Decimal


def _ridgeline_rows() -> list[e4.M3Row]:
    return [
        e4.M3Row("Interest income (Form 8916-A)", D("24600"), D("0"), D("-6200"), D("18400")),
        e4.M3Row("Other items with no differences", D("1231600"), D("0"), D("0"), D("1231600")),
    ]


def test_ridgeline_must_file_m3_and_may_use_the_m1_alternative() -> None:
    req = e4.m3_requirement(D("17914500"))
    assert req.required and req.m1_option
    assert not e4.m3_requirement(D("9999999.99")).required
    assert not e4.m3_requirement(D("50000000")).m1_option


def test_ridgeline_reconciles_1_256_200_to_1_250_000_with_one_permanent_6_200() -> None:
    rec = e4.reconcile_m3(
        _ridgeline_rows(), part_i_line_11=D("1256200"), analysis_line_1=D("1250000")
    )
    assert (rec.book_income, rec.temporary, rec.permanent, rec.income_per_return) == (
        D("1256200"), D("0"), D("-6200"), D("1250000"),
    )  # fmt: skip
    assert (rec.part_i_tie, rec.analysis_tie) == ("tie", "tie")
    assert sum(1 for r in rec.rows if r.col_c != 0) == 1


def test_a_row_that_does_not_foot_is_refused() -> None:
    with pytest.raises(ValueError, match="does not foot"):
        e4.reconcile_m3(
            [e4.M3Row("bad", D("1"), D("0"), D("0"), D("2"))],
            part_i_line_11=D("1"),
            analysis_line_1=D("2"),
        )


def test_m1_reference_lines_5_8_9() -> None:
    m = e4.m1(D("1256200"), [], [D("6200")])
    assert (m.line_5, m.subtractions, m.line_9) == (D("1256200"), D("6200"), D("1250000"))


def test_granite_peak_1120_m1_starts_at_2_350_000() -> None:
    m = e4.m1_from_1120(D("3100000"), D("750000"))
    assert (m.line_1, m.additions, m.line_5) == (D("2350000"), D("750000"), D("3100000"))


def test_ridgeline_m2_is_off_6_200_until_tax_exempt_interest_is_added() -> None:
    drafted = e4.roll_m2(
        beginning=D("6860000") - D("1250000"), net_income=D("1250000"),
        schedule_l_line_21=D("6866200"),
    )  # fmt: skip
    assert (drafted.ending, drafted.difference, drafted.tally) == (D("6860000"), D("-6200"), "off")
    fixed = e4.roll_m2(
        beginning=D("6860000") - D("1250000"), net_income=D("1250000"),
        other_increases=D("6200"), schedule_l_line_21=D("6866200"),
    )  # fmt: skip
    assert (fixed.ending, fixed.tally) == (D("6866200"), "tie")
