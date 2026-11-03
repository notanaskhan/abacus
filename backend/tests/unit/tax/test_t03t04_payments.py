"""T-03-T04 (TASK-3203; DEC-2203): the payments engine and the TY2027 installment dates.

Row acceptance: "The functions reproduce every TAX-13 figure (110,250; 46,300; 19,990; NY 7,824;
12,733) and the TY2027 installment dates, and each output carries engine name, version and inputs
hash." Figures are TAX-13's (handoff spec, acceptance checklist); dates are I-CLOCKS' TY2027 cases.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.practice.compute import calendar
from abacus.modules.tax.compute import likely_to_extend, payments

P = payments.parameters(2027)
D = Decimal


def _stamped(stamp: payments.Stamp) -> None:
    assert stamp.engine_name == "tax.payments"
    assert stamp.engine_version == "1"
    assert len(stamp.inputs_hash) == 64


@pytest.mark.parametrize(
    ("form", "projected", "target"),
    [
        ("1040", "122500", "110250.00"),  # Feld (4868 + IT-370)
        ("1041", "46300", "46300.00"),  # Calloway Family Trust
        ("1120", "1572900", "1572900.00"),  # Ashford Manufacturing
        ("1040", "148000", "133200.00"),  # Meera Shah
        ("1040", "212000", "190800.00"),  # Walter Thornbury's 1040
        ("1040", "3900", "3510.00"),  # Elena Varga
    ],
)
def test_ac4_safe_harbor_targets(form: str, projected: str, target: str) -> None:
    found = payments.safe_harbor(form, D(projected), P)
    assert found.target == D(target)
    _stamped(found.stamp)


def test_ac4_pass_through_and_exempt_returns_have_no_target() -> None:
    assert payments.safe_harbor("1065", None, P).target is None
    assert payments.safe_harbor("990", None, P).pct is None
    with pytest.raises(LookupError):
        payments.safe_harbor("8879", D(1), P)


@pytest.mark.parametrize(
    ("withholding", "paid", "target", "meets"),
    [
        ("113476", ["10000", "6000"], "110250", True),  # Feld: 123,476 (federal) + NY line
        ("42000", ["5000"], "46300", True),
        ("1560000", ["12900"], "1572900", True),
        ("128000", ["20000"], "133200", True),
        ("3400", ["500"], "3510", True),
        ("100000", [], "110250", False),
    ],
)
def test_ac4_paid_by_the_original_due_date(
    withholding: str, paid: list[str], target: str, meets: bool
) -> None:
    check = payments.paid_by_original_due(D(withholding), [D(p) for p in paid], D(target), P)
    assert check.meets is meets
    assert check.shortfall == (D(0) if meets else D(target) - check.paid_by_original_due)
    _stamped(check.stamp)


def test_ac4_feld_estimates_federal_and_new_york() -> None:
    federal = payments.required_annual_payment(
        "prior_year_110", prior_year_tax=D("123223"), projected_withholding=D("55585"), params=P
    )
    assert federal.base == D("135545")
    assert federal.annual == D("79960")
    assert payments.installment_amounts(federal.annual or D(0), P).amounts == (D("19990"),) * 4
    ny = payments.required_annual_payment(
        "prior_year_110", prior_year_tax=D("52805"), projected_withholding=D("26790"), params=P
    )
    assert ny.base == D("58086")
    assert ny.annual == D("31296")
    assert payments.installment_amounts(ny.annual or D(0), P).amounts[2] == D("7824")
    _stamped(ny.stamp)


@pytest.mark.parametrize(
    ("method", "tax", "annual", "q3"),
    [
        ("prior_year_110", "148000", "162800", "40700"),  # Meera Shah
        ("prior_year_110", "46300", "50930", "12733"),  # Calloway: 12,732.50 half up
        ("prior_year_100", "3900", "3900", "975"),  # Elena Varga
        ("prior_year_100", "6200", "6200", "1550"),  # Gloria Mendez
    ],
)
def test_ac4_estimate_installments(
    method: payments.Method, tax: str, annual: str, q3: str
) -> None:
    found = payments.required_annual_payment(
        method, prior_year_tax=D(tax), projected_withholding=None, params=P
    )
    assert found.annual == D(annual)
    shares = payments.installment_amounts(found.annual or D(0), P)
    assert shares.amounts[2] == D(q3)
    _stamped(shares.stamp)


def test_ac4_largest_remainder_foots_when_asked() -> None:
    shares = payments.installment_amounts(D("50930"), P, rounding="largest_remainder")
    assert sum(shares.amounts) == D("50930")


def test_ac4_not_required_and_prospect_have_no_amount_and_withholding_never_goes_negative() -> (
    None
):
    for method in ("not_required_withholding", "not_required_estate_first_years", "prospect"):
        found = payments.required_annual_payment(
            method,
            prior_year_tax=None,
            projected_withholding=None,
            params=P,
        )
        assert found.annual is None
    covered = payments.required_annual_payment(
        "prior_year_100", prior_year_tax=D("5000"), projected_withholding=D("9000"), params=P
    )
    assert covered.annual == D(0)


def test_ac4_the_prior_year_method_and_the_estate_exemption() -> None:
    assert payments.prior_year_method(D("150001"), P) == "prior_year_110"
    assert payments.prior_year_method(D("150000"), P) == "prior_year_100"
    assert payments.prior_year_method(D("75001"), P, married_separate=True) == "prior_year_110"
    assert payments.estate_exempt(1, P) and payments.estate_exempt(2, P)
    assert not payments.estate_exempt(3, P)


def test_ac4_the_same_inputs_give_the_same_hash() -> None:
    a = payments.safe_harbor("1040", D("122500"), P).stamp
    b = payments.safe_harbor("1040", D("122500.00"), P).stamp
    c = payments.safe_harbor("1040", D("122501"), P).stamp
    assert a == payments.safe_harbor("1040", D("122500"), P).stamp
    assert a.inputs_hash != c.inputs_hash
    assert b.inputs_hash != c.inputs_hash


_ES = calendar.Rule(
    form="1040-ES",
    fye_rule="calendar_year",
    original=calendar.Offset(-8, 15),
    extension_form=None,
    extension_months=None,
    installments=((1, -8, 15), (2, -6, 15), (3, -3, 15), (4, 1, 15)),
)
# Federal and DC holidays named by the TY2027 and TY2028 reference sets (MLK Day).
_HOLIDAYS = frozenset({date(2028, 1, 17), date(2029, 1, 15)})


def test_ac4_ty2027_installment_dates() -> None:
    found = calendar.installment_dates(_ES, date(2027, 12, 31), _HOLIDAYS)
    assert [i.due_on for i in found] == [
        date(2027, 4, 15),
        date(2027, 6, 15),
        date(2027, 9, 15),
        date(2028, 1, 18),  # Sat Jan 15; Mon Jan 17 is MLK Day
    ]
    assert found[3].rolled


def test_ac4_ty2028_q4_rolls_past_mlk_day() -> None:
    found = calendar.installment_dates(_ES, date(2028, 12, 31), _HOLIDAYS)
    assert found[3].due_on == date(2029, 1, 16)


def test_ac4_likely_to_extend_signals() -> None:
    thornbury = likely_to_extend.ReturnFacts(
        original_due_on=date(2026, 11, 2),
        filed=False,
        extension_filed=False,
        k1s_outstanding=0,
        binder_open_items=0,
        engagement_accepted=False,
        preparer_flagged=False,
    )
    assert likely_to_extend.signals(thornbury, date(2026, 10, 14), P) == (
        "engagement_not_accepted",
    )
    assert likely_to_extend.signals(thornbury, date(2026, 9, 14), P) == ()  # outside 30 days
    extended = likely_to_extend.ReturnFacts(
        original_due_on=date(2026, 4, 15),
        filed=False,
        extension_filed=True,
        k1s_outstanding=2,
        binder_open_items=3,
        engagement_accepted=True,
        preparer_flagged=True,
    )
    assert likely_to_extend.signals(extended, date(2026, 4, 10), P) == ()
