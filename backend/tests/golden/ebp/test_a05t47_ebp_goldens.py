"""Independent AC goldens for EBP-05, EBP-06, EBP-08 and EBP-09 (A-05-T47; ADR-078): every figure
is the handoff spec's, asserted with exact Decimal equality against the engines. Loans,
withholding, vesting, expenses, limits, participant ties and the certification hold."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus.modules.assurance.compute.ebp import accounts, expenses, loans, trust_agreement

# --- EBP-05 ---------------------------------------------------------------------------------


def test_ebp05_the_loan_rollforward_foots_to_the_trust_report() -> None:
    roll = loans.rollforward(
        [
            loans.Loan(
                "all",
                D("288500.00"),
                D("96200.00"),
                D("57450.00"),
                D("14850.00"),
                D("312400.00"),
            )
        ]
    )
    assert roll.beginning == D("288500.00")
    assert roll.new == D("96200.00")
    assert roll.repayments == D("57450.00")
    assert roll.offsets == D("14850.00")
    assert roll.ending == D("312400.00")
    assert roll.foots is True


def test_ebp05_a_rollforward_off_by_a_cent_does_not_foot() -> None:
    roll = loans.rollforward(
        [loans.Loan("x", D("100.00"), D("0.00"), D("10.00"), D("0.00"), D("90.01"))]
    )
    assert roll.foots is False


@pytest.mark.parametrize(
    ("amount", "vested", "limit", "months", "residence"),
    [
        ("15000.00", "41880.00", "20940.00", 60, False),  # Tomás Ibarra
        ("8000.00", "22400.00", "11200.00", 48, False),  # Rebecca Lindgren
        ("25000.00", "96300.00", "48150.00", 60, False),  # Connor Gallagher
        ("30000.00", "128400.00", "50000.00", 180, True),  # Chloe Dubois, principal residence
        ("18200.00", "52000.00", "26000.00", 60, False),  # Ethan Caldwell
    ],
)
def test_ebp05_new_loans_meet_72p(
    amount: str, vested: str, limit: str, months: int, residence: bool
) -> None:
    found = loans.loan_limit(D(amount), D(vested), months, residence)
    assert found.limit == D(limit)
    assert found.within is True


def test_ebp05_the_new_loans_total() -> None:
    total = sum(
        (D(a) for a in ("15000.00", "8000.00", "25000.00", "30000.00", "18200.00")), D("0.00")
    )
    assert total == D("96200.00")


def test_ebp05_a_180_month_term_needs_a_residence() -> None:
    assert loans.loan_limit(D("30000.00"), D("128400.00"), 180, False).within_term is False


def test_ebp05_offsets_total_and_benefits_paid() -> None:
    assert loans.offsets_total([D("4850.00"), D("5200.00"), D("4800.00")]) == D("14850.00")
    assert D("797800.00") + D("14850.00") == D("812650.00")


def test_ebp05_withholding_counts_the_offset() -> None:
    # Dmitri Volkov: 20% of 17,250.00 (12,400.00 cash + 4,850.00 offset).
    assert loans.withholding("eligible_rollover", D("12400.00"), D("4850.00")) == D("3450.00")
    # Corinne Blake: a direct rollover withholds nothing.
    assert loans.withholding("direct_rollover", D("84210.55")) == D("0.00")


# --- EBP-06 ---------------------------------------------------------------------------------

FUNDS = (
    ("KRS 500 Index Fund", "5102300.00", "6120450.00"),
    ("KRS Target 2035 Fund", "2011640.00", "2384910.00"),
    ("KRS Target 2045 Fund", "2388970.00", "2915330.00"),
    ("KRS Bond Index Fund", "1276090.00", "1408220.00"),
    ("KRS International Index Fund", "868000.00", "902610.00"),
    ("Harborline Stable Value Fund (CIT)", "1036000.00", "1163480.00"),
    ("Self-directed brokerage - BrokerWindow", "1257000.00", "1605000.00"),
)


def _trust(level: str = "nav") -> list[trust_agreement.TrustLine]:
    return [
        trust_agreement.TrustLine(str(i), name, D(boy), D(eoy), level)
        for i, (name, boy, eoy) in enumerate(FUNDS)
    ]


def _tb() -> list[trust_agreement.TbFigure]:
    return [trust_agreement.TbFigure(name, D(boy), D(eoy)) for name, boy, eoy in FUNDS]


def test_ebp06_investments_foot_and_tie_line_by_line() -> None:
    found = trust_agreement.agree(_trust(), _tb())
    assert found.investments_eoy == D("16500000.00")
    assert found.investments_boy == D("13940000.00")
    assert all(line.ties for line in found.lines)
    assert found.py_ties is True


def test_ebp06_a_line_off_by_a_dollar_names_the_difference() -> None:
    tb = _tb()
    tb[0] = trust_agreement.TbFigure(FUNDS[0][0], D(FUNDS[0][1]), D("6120451.00"))
    line = trust_agreement.agree(_trust(), tb).lines[0]
    assert line.ties is False
    assert abs(line.off_by) == D("1.00")


def test_ebp06_a_line_not_certified_is_held_below_the_certified_footing() -> None:
    found = trust_agreement.agree(_trust("not_certified"), _tb())
    assert found.nav_eoy == D("0.00")
    assert found.below_eoy == D("16500000.00")


def test_ebp06_net_trust_assets_with_loans() -> None:
    assert D("16500000.00") + D("312400.00") == D("16812400.00")


# --- EBP-08 ---------------------------------------------------------------------------------

_ACTIVE = accounts.ParticipantBalance(
    "active",
    "active",
    D("11612300"),
    D("1318300"),
    D("1716000"),
    D("-104600"),
    D("-29200"),
    D("-871900"),
    D("13640900"),
)
_TERMINATED = accounts.ParticipantBalance(
    "terminated",
    "terminated",
    D("2616200"),
    D("0"),
    D("400650"),
    D("-708050"),
    D("-9200"),
    D("871900"),
    D("3171500"),
)


def test_ebp08_the_groups_crossfoot_to_the_trust() -> None:
    roll = accounts.rollforward([_ACTIVE, _TERMINATED])
    assert all(g.crossfoots for g in roll.groups)
    assert roll.total.crossfoots is True
    assert roll.total.beginning == D("14228500")
    assert roll.total.contributions == D("1318300")
    assert roll.total.earnings == D("2116650")
    assert roll.total.distributions == D("-812650")
    assert roll.total.fees == D("-38400")
    assert roll.total.ending == D("16812400")
    assert roll.transfers_net_zero is True


def test_ebp08_the_ties_are_tri_state() -> None:
    assert accounts.tie("trust", D("16812400"), D("16812400")).ties is True
    assert accounts.tie("trust", D("16812400"), D("16812401")).ties is False
    assert accounts.tie("trust", None, D("16812400")).ties is None


def test_ebp08_brokerage_by_type_ties_to_ebp06() -> None:
    by_type, total = accounts.sdba_by_type(
        [
            ("Common stocks", D("924300")),
            ("Exchange-traded funds", D("612450")),
            ("Money market sweep", D("68250")),
        ]
    )
    assert by_type["Common stocks"] == D("924300")
    assert total == D("1605000")


def test_ebp08_vesting_is_two_year_cliff_and_unknown_stays_unknown() -> None:
    assert accounts.vested_pct(D("2")) == D("100")
    assert accounts.vested_pct(D("1")) == D("0")
    assert accounts.vested_pct(None) is None


# --- EBP-09 ---------------------------------------------------------------------------------

_EXPENSES = [
    expenses.Expense("recordkeeping", D("24600.00"), D("0.00"), D("24600.00"), "2i2", True),
    expenses.Expense("tpa", D("7800.00"), D("0.00"), D("7800.00"), "2i2", True),
    expenses.Expense("audit", D("9100.00"), D("3100.00"), D("6000.00"), "2i1", True),
]


def test_ebp09_expenses_tie_to_schedule_h() -> None:
    found = expenses.tie(_EXPENSES)
    assert found.invoiced == D("41500.00")
    assert found.credits == D("3100.00")
    assert found.paid == D("38400.00")
    assert found.by_line["2i1"] == D("6000.00")
    assert found.by_line["2i2"] == D("32400.00")
    assert found.invoices_tie is True
    assert found.exceptions == ()


def test_ebp09_a_fee_with_no_disclosure_is_an_exception() -> None:
    bare = expenses.Expense("audit", D("1.00"), D("0.00"), D("1.00"), "2i1", False)
    assert expenses.tie([bare]).exceptions == ("audit",)


def test_ebp09_the_budget_account_rolls() -> None:
    roll = expenses.budget_account(
        [
            ("beginning", D("1200.00")),
            ("revenue_share", D("2650.00")),
            ("applied", D("3100.00")),
        ]
    )
    assert roll.ending == D("750.00")


@pytest.mark.parametrize(
    ("key", "limit"),
    [
        ("402g", "23500.00"),
        ("catch_up", "7500.00"),
        ("catch_up_60_63", "11250.00"),
        ("415c", "70000.00"),
        ("401a17", "350000.00"),
    ],
)
def test_ebp09_py2025_limits(key: str, limit: str) -> None:
    assert expenses.limits_for(2025)[key] == D(limit)
    assert expenses.within_limit(D(limit), key, 2025) is True
    assert expenses.within_limit(D(limit) + D("0.01"), key, 2025) is False
