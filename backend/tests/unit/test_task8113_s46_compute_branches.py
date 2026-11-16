"""TASK-8113: the S46 compute branches the stage 2 floor found untested (ADR-079: 100% line and
branch on `*/compute/`). A-08-T11's confirmation reconciliation, A-08-T12's duplicate entry
refusal, and T-07-T22's estate edges (a missing parameter year, a zero tentative tax, the annual
exclusion outside the table, the stored outputs). Each expected value comes from the arithmetic or
the parameter file, never from the engine's own constants."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

import pytest

from abacus.modules.assurance.compute.reconciliation import reconcile
from abacus.modules.sampling.compute import je_selection as sel
from abacus.modules.tax.compute import estate as e

D = Decimal


def test_a_reconciliation_that_ties_has_nothing_left() -> None:
    r = reconcile(D("1000.00"), D("1250.00"), [D("200.00"), D("50.00")], D("25.00"))
    assert (r.items_total, r.unreconciled, r.ties, r.below_clearly_trivial) == (
        D("250.00"),
        D("0.00"),
        True,
        True,
    )


def test_a_remaining_difference_compares_its_absolute_value_with_clearly_trivial() -> None:
    under = reconcile(D("1000.00"), D("1030.00"), [D("10.00")], D("25.00"))
    assert (under.unreconciled, under.ties, under.below_clearly_trivial) == (
        D("-20.00"),
        False,
        True,
    )
    over = reconcile(D("1000.00"), D("900.00"), [], D("25.00"))
    assert (over.unreconciled, over.below_clearly_trivial) == (D("100.00"), False)


def test_without_clearly_trivial_the_comparison_is_not_made() -> None:
    r = reconcile(D("10.00"), D("5.00"), ())
    assert (r.items_total, r.unreconciled, r.below_clearly_trivial) == (
        D("0.00"),
        D("5.00"),
        None,
    )


def test_a_draw_refuses_an_entry_reference_named_twice() -> None:
    scores = [sel.Scored("JE-001", 90), sel.Scored("JE-001", 40)]
    with pytest.raises(sel.SelectionInvalid, match="duplicate_entry"):
        sel.select(scores, score_min=50, top_n=None, unpredictable_n=0, seed=1)


def test_a_tax_year_without_parameters_is_refused() -> None:
    with pytest.raises(LookupError, match="ty1990"):
        e.parameters(1990)


def test_nothing_taxable_has_no_tentative_tax() -> None:
    params = e.parameters(2026)
    assert e.tentative_tax(D("0"), params) == D("0.00")
    assert e.tentative_tax(D("-5"), params) == D("0.00")


def test_the_annual_exclusion_outside_the_table_takes_its_nearest_year() -> None:
    params = e.parameters(2026)
    years = sorted(params.annual_exclusion)
    assert e.annual_exclusion(years[0] - 3, params) == params.annual_exclusion[years[0]]
    assert e.annual_exclusion(years[-1] + 4, params) == params.annual_exclusion[years[-1]]


def test_the_stored_outputs_write_money_as_strings() -> None:
    inputs = e.EstateInputs(
        2026,
        (
            e.Asset("A", "House", D("500000"), D("480000"), "stepped_up"),
            e.Asset("I", "IRA", D("100000"), D("100000"), "ird_no_step_up"),
        ),
        (e.Deduction("funeral", "J_funeral", D("12500.5")),),
        (e.Gift("2025", 2025, D("30000")),),
    )
    out = e.outputs_of(e.compute(inputs))
    assert out["gross_estate_dod"] == "600000.00"
    assert out["deductions"] == "12500.50"
    assert out["basis_by_asset"] == {"A": "500000.00", "I": None}
    gifts = cast(list[dict[str, object]], out["gifts"])
    assert [(g["year"], g["exclusion"], g["taxable"]) for g in gifts] == [
        (2025, "19000.00", "11000.00")
    ]
    assert out["engine_name"] == e.ENGINE_NAME
