"""T-07-T22 (TASK-8079; SPEC-656 AC-12.1, AC-12.4, AC-13.1, AC-13.2, AC-13.4): the estate engine.

Row acceptance: "Thornbury's inputs give 16,400,000 / 15,993,000 / 12,688,000, 900,000, 6,625,800,
7,145,800, net tax 0 and 680,000 without DSUE, and the due chip reads Nov 2, 2026 and May 3, 2027."
(The due chip is the service's: `tests/unit/tax/test_t07t22_estate_due.py`.)
"""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.tax.compute import estate as e

D = Decimal
ASSETS = (
    e.Asset("A", "A", D("3850000"), D("3790000"), "stepped_up"),
    e.Asset("B", "B", D("8240000"), D("7965000"), "stepped_up"),
    e.Asset("C", "C", D("412000"), D("412000"), "stepped_up"),
    e.Asset("D", "D", D("1000000"), D("1000000"), "non_probate_excluded"),
    e.Asset("F", "F", D("186000"), D("186000"), "stepped_up"),
    e.Asset("I", "I", D("2712000"), D("2640000"), "ird_no_step_up"),
)
DEDUCTIONS = (
    e.Deduction("funeral", "J_funeral", D("28500")),
    e.Deduction("admin", "J_administration", D("240000")),
    e.Deduction("debts", "K", D("131500")),
    e.Deduction("charity", "O", D("500000")),
)
GIFTS = (
    e.Gift("2023", 2023, D("1217000")),
    e.Gift("2024", 2024, D("18000")),
    e.Gift("2025", 2025, D("19000")),
    e.Gift("2026", 2026, D("19000")),
)
INPUTS = e.EstateInputs(2026, ASSETS, DEDUCTIONS, GIFTS, dsue=D("3000000"), residence_state="IL")


def test_ac121_the_inventory_foots() -> None:
    r = e.compute(INPUTS)
    assert (r.gross_estate_dod, r.gross_estate_avd, r.basis_to_1041) == (
        D("16400000.00"), D("15993000.00"), D("12688000.00"),
    )  # fmt: skip
    assert r.basis_by_asset["I"] is None and r.basis_by_asset["D"] is None  # by rule


def test_ac124_and_ac131_the_computation() -> None:
    r = e.compute(INPUTS)
    assert r.deductions == D("900000.00")
    assert (r.taxable_estate, r.adjusted_taxable_gifts, r.tentative_tax_base) == (
        D("15500000.00"), D("1200000.00"), D("16700000.00"),
    )  # fmt: skip
    assert r.tentative_tax == D("6625800.00")  # 345,800 + 40% × 15,700,000
    assert (r.applicable_exclusion, r.credit, r.net_tax) == (D("18000000.00"), D("7145800.00"), D("0.00"))
    assert (r.credit_without_dsue, r.tax_without_dsue) == (D("5945800.00"), D("680000.00"))
    assert r.filing_threshold_amount == D("17600000.00") and r.filing_required
    assert r.state_required is True  # the Illinois exclusion is 4,000,000; never a figure


def test_ac132_alternate_valuation_is_not_available_without_tax() -> None:
    assert e.compute(INPUTS).avd_available is False
    no_dsue = e.compute(e.EstateInputs(2026, ASSETS, DEDUCTIONS, GIFTS))
    assert no_dsue.avd_available is True  # both the estate and the tax fall


def test_ac134_annual_exclusions_by_year() -> None:
    r = e.compute(INPUTS)
    assert [(g.year, g.exclusion, g.taxable) for g in r.gifts] == [
        (2023, D("17000"), D("1200000.00")), (2024, D("18000"), D("0.00")),
        (2025, D("19000"), D("0.00")), (2026, D("19000"), D("0.00")),
    ]  # fmt: skip


def test_inputs_hash_is_stable() -> None:
    assert e.compute(INPUTS).inputs_hash == e.compute(INPUTS).inputs_hash
