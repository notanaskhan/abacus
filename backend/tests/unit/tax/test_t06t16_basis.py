"""T-06-T16 (SPEC-702; DEC-5627): E8 on Ridgeline's 2025 partners (TXP-08)."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.tax.compute import basis as e8

D = Decimal
PROFIT = {
    "Ridgeline GP LLC": D("2"),
    "Meera Shah": D("38"),
    "Pell Street Ventures LLC": D("30"),
    "Pell Street II LLC": D("5"),
    "Jonah Feld": D("25"),
}


def test_752_shares_foot_to_liabilities_by_year_end_profit() -> None:
    shares = e8.liability_shares(D("11048300"), PROFIT)
    assert shares == {
        "Ridgeline GP LLC": D("220966"),
        "Meera Shah": D("4198354"),
        "Pell Street Ventures LLC": D("3314490"),
        "Pell Street II LLC": D("552415"),
        "Jonah Feld": D("2762075"),
    }
    assert sum(shares.values()) == D("11048300")


def test_feld_4_428_925_plus_564_050_less_316_850_is_4_676_125() -> None:
    contribution, distribution = e8.deemed(D("2928925"), D("2762075"))
    assert (contribution, distribution) == (D("0"), D("166850"))
    r = e8.roll(
        D("1500000") + D("2928925"),
        [D("250000"), D("312500"), D("1550")],
        [D("150000"), distribution],
    )
    assert (r.beginning, r.increases, r.decreases, r.ending) == (
        D("4428925"), D("564050"), D("316850"), D("4676125"),
    )  # fmt: skip
    feld = e8.partner_basis(
        "Jonah Feld", tax_capital=D("1914050"), s752_share=D("2762075"), outside=r.ending
    )
    assert feld.tally == "reconciled"


def test_pell_street_ii_is_off_28_595_the_743b_placeholder() -> None:
    outside = e8.roll(D("0"), [D("360000"), D("31250"), D("155"), D("552415")], [D("30000")])
    inside = e8.roll(D("0"), [D("331405"), D("31250"), D("155"), D("552415")], [D("30000")])
    assert (outside.ending, inside.ending) == (D("913820"), D("885225"))
    p = e8.partner_basis(
        "Pell Street II LLC",
        tax_capital=D("332810"),
        s752_share=D("552415"),
        outside=outside.ending,
    )
    assert (p.inside, p.difference, p.tally) == (D("885225"), D("28595"), "off")
    assert e8.s743b_placeholder(D("360000"), D("331405")) == p.difference


def test_outside_basis_never_goes_below_zero() -> None:
    assert e8.roll(D("100"), [], [D("150")]).ending == D("0")
