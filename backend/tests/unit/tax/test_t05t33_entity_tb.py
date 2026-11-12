"""T-05-T33 (TASK-7623; DEC-4618): the entity TB and TTB read model's pure parts.

Line view sums accounts per form line, the statement filter splits Schedule L from the rest,
and the tallies foot each column and mark unmapped accounts as `check` (the export gate).
"""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.tax.entity_tb import TbRow, by_line, narrowed, tallies

D = Decimal


def _row(code: str, line: str | None, utb: str, aje: str = "0", tje: str = "0") -> TbRow:
    u, a, t = D(utb), D(aje), D(tje)
    return TbRow(code, f"Account {code}", line, u, a, D("0"), t, u + a + t)


ROWS = [
    _row("1000", "L1", "6200.00"),
    _row("1010", "L1", "800.00", aje="-50.00"),
    _row("3000", "L21", "-7000.00"),
    _row("4000", "1a", "-1200.00", tje="100.00"),
    _row("6000", "20", "1200.00", aje="50.00", tje="-100.00"),
]


def test_ac_line_view_sums_accounts_per_form_line() -> None:
    lines = {r.form_line_key: r for r in by_line(ROWS)}
    assert set(lines) == {"L1", "L21", "1a", "20"}
    assert lines["L1"].unadjusted == D("7000.00")
    assert lines["L1"].aje == D("-50.00")
    assert lines["L1"].tax_basis == D("6950.00")


def test_ac_line_view_leaves_unmapped_accounts_out() -> None:
    rows = [*ROWS, _row("9999", None, "10.00")]
    assert all(r.form_line_key is not None for r in by_line(rows))


def test_ac_statement_filter_splits_schedule_l() -> None:
    bs = narrowed(ROWS, "balance_sheet", False)
    inc = narrowed(ROWS, "income_statement", False)
    assert {r.account_code for r in bs} == {"1000", "1010", "3000"}
    assert {r.account_code for r in inc} == {"4000", "6000"}
    assert len(narrowed(ROWS, "full", False)) == len(ROWS)


def test_ac_unmapped_filter_keeps_only_accounts_without_a_line() -> None:
    rows = [*ROWS, _row("9999", None, "0.00")]
    assert [r.account_code for r in narrowed(rows, "full", True)] == ["9999"]


def test_ac_tallies_tie_when_every_column_foots() -> None:
    by_key = {t.key: t for t in tallies(ROWS)}
    assert by_key["utb_foot"].state == "tie"
    assert by_key["atb_foot"].state == "tie"
    assert by_key["ttb_foot"].state == "tie"
    assert by_key["unmapped"].state == "tie" and by_key["unmapped"].difference == D(0)


def test_ac_tallies_report_the_difference_and_the_unmapped_check() -> None:
    rows = [*ROWS, _row("9999", None, "25.00")]
    by_key = {t.key: t for t in tallies(rows)}
    assert by_key["utb_foot"].state == "off" and by_key["utb_foot"].difference == D("25.00")
    assert by_key["unmapped"].state == "check" and by_key["unmapped"].difference == D(1)
