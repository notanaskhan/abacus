"""T-05-T37 (TASK-7627; DEC-4622): TXP-02's sections, totals and figure cards, by the server.

On Ridgeline's figures, total assets 17,914,500, total deductions 2,641,300, gross rents
3,872,900 and net rental real estate income 1,231,600; the TB total foots to $0.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus.modules.tax.entity_tb import TbRow, figures, group_of, totals

D = Decimal


@pytest.mark.parametrize(
    ("key", "group"),
    [
        ("L1", "assets"),
        ("L9b", "assets"),
        ("L13", "assets"),
        ("L15", "liabilities"),
        ("L18", "liabilities"),
        ("L21", "equity"),
        ("M-2 6a", "equity"),
        ("8825 Rents", "income"),
        ("K 5", "income"),
        ("K 18a", "income"),
        ("M-3 perm.", "income"),
        ("8825 Taxes", "deductions"),
        (None, "unmapped"),
    ],
)
def test_ac_sections_follow_the_form_line(key: str | None, group: str) -> None:
    assert group_of(key) == group


def _r(code: str, line: str, ttb: str) -> TbRow:
    t = D(ttb)
    return TbRow(code, code, line, t, D(0), D(0), D(0), t, adjusted=t, group=group_of(line))


ROWS = [
    _r("1000", "L1", "17914500"),
    _r("2000", "L15", "-11048300"),
    _r("3000", "L21", "-5960000"),
    _r("3100", "M-2 2a", "-250000"),
    _r("3200", "M-2 6a", "600000"),
    _r("4000", "8825 Rents", "-3776500"),
    _r("4100", "8825 Rents", "-96400"),
    _r("4500", "K 5", "-18400"),
    _r("4510-T", "K 18a", "-6200"),
    _r("5000", "8825 Repairs", "2641300"),
]


def test_ac_section_totals_and_the_tb_total_are_the_servers() -> None:
    by_key = {t.key: t for t in totals(ROWS)}
    assert by_key["assets"].tax_basis == D("17914500")
    assert by_key["deductions"].tax_basis == D("2641300")
    assert by_key["equity"].tax_basis == D("-5610000")
    assert by_key["tb_total"].tax_basis == D(0) and by_key["tb_total"].adjusted == D(0)
    assert list(by_key)[-1] == "tb_total"


def test_ac_figure_cards_on_ridgeline() -> None:
    cards = {f.key: f.amount for f in figures(ROWS)}
    assert cards == {
        "gross_rents": D("3872900"),
        "total_deductions": D("2641300"),
        "net_rental_income": D("1231600"),
        "book_total_assets": D("17914500"),
    }
