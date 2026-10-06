"""AC-11: `ledger.validate`, the provider-neutral checks and their order (TASK-010a contract
revision 1, "Ledger"; ADR-038).

Order: `empty`, `period_mismatch`, `unsupported_currency`, `duplicate_account` (NFKC and
casefold), `duplicate_source_ref`, `control_totals_mismatch`, `unbalanced`, `zero_total`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.ledger.api import LedgerLine, NormalisedTrialBalance, NormaliseError, validate

START = date(2025, 1, 1)
END = date(2025, 12, 31)
OTHER = (date(2024, 1, 1), date(2024, 12, 31))


def _fullwidth(text: str) -> str:
    return "".join(chr(ord(c) + 0xFEE0) for c in text)


def _line(code: str, debit: str, credit: str, ref: str | None = None) -> LedgerLine:
    return LedgerLine(
        code, f"Account {code}", Decimal(debit), Decimal(credit), ref or f"acct-{code}"
    )


def _tb(
    lines: list[LedgerLine],
    *,
    declared: tuple[str, str] | None = None,
    period: tuple[date, date] = (START, END),
    currency: str = "USD",
) -> NormalisedTrialBalance:
    debit = sum((line.debit for line in lines), Decimal(0))
    credit = sum((line.credit for line in lines), Decimal(0))
    declared_debit, declared_credit = (
        (Decimal(declared[0]), Decimal(declared[1])) if declared else (debit, credit)
    )
    return NormalisedTrialBalance(
        period[0], period[1], currency, tuple(lines), declared_debit, declared_credit
    )


def _check(tb: NormalisedTrialBalance) -> str | None:
    return validate(tb, period_start=START, period_end=END)


BALANCED = [_line("1000", "100.00", "0.00"), _line("4000", "0.00", "100.00")]
UNBALANCED = [_line("1000", "100.00", "0.00"), _line("4000", "0.00", "90.00")]


def test_ac11_a_balanced_declared_in_period_usd_trial_balance_passes() -> None:
    assert _check(_tb(BALANCED)) is None


def test_ac11_decimal_arithmetic_is_exact() -> None:
    lines = [
        _line("1", "0.10", "0.00"),
        _line("2", "0.20", "0.00"),
        _line("3", "0.00", "0.30"),
    ]
    assert _check(_tb(lines)) is None


def test_ac11_no_lines_is_empty() -> None:
    assert _check(_tb([])) == "empty"


@pytest.mark.parametrize(
    "period",
    [
        (date(2025, 1, 2), END),
        (START, date(2025, 12, 30)),
        OTHER,
        (date(2025, 1, 2), date(2025, 12, 30)),
    ],
)
def test_ac11_a_different_period_is_a_period_mismatch(period: tuple[date, date]) -> None:
    assert _check(_tb(BALANCED, period=period)) == "period_mismatch"


def test_ac11_the_requested_period_is_the_one_given_not_a_fixed_one() -> None:
    tb = _tb(BALANCED, period=OTHER)
    assert validate(tb, period_start=OTHER[0], period_end=OTHER[1]) is None


@pytest.mark.parametrize("currency", ["EUR", "GBP", "usd", "USD ", "", "XXX"])
def test_ac11_any_currency_but_usd_is_unsupported(currency: str) -> None:
    assert _check(_tb(BALANCED, currency=currency)) == "unsupported_currency"


def test_ac11_the_same_code_twice_is_a_duplicate_account() -> None:
    assert _check(_tb([*BALANCED, _line("1000", "0.00", "0.00", "acct-x")])) == "duplicate_account"


def test_ac11_a_duplicate_account_is_found_even_when_the_names_differ() -> None:
    other = LedgerLine("1000", "Another name", Decimal("0.00"), Decimal("0.00"), "acct-other")
    assert _check(_tb([*BALANCED, other])) == "duplicate_account"


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("abc", "ABC"),
        ("Abc-1", "aBC-1"),
        ("ABC", _fullwidth("ABC")),  # fullwidth letters fold to ASCII under NFKC
        ("1000", _fullwidth("1000")),  # fullwidth digits
        (chr(0xFB01), "fi"),  # ligature
        ("Å", "Å"),  # canonical equivalents
        ("Straße", "STRASSE"),  # casefold: sharp s
    ],
)
def test_ac11_codes_that_render_alike_are_the_same_account(first: str, second: str) -> None:
    lines = [_line(first, "100.00", "0.00", "acct-a"), _line(second, "0.00", "100.00", "acct-b")]
    assert _check(_tb(lines)) == "duplicate_account"


def test_ac11_codes_that_differ_in_more_than_form_are_different_accounts() -> None:
    lines = [_line("1000", "100.00", "0.00", "a"), _line("1001", "0.00", "100.00", "b")]
    assert _check(_tb(lines)) is None


def test_ac11_the_same_source_ref_twice_is_a_duplicate_source_ref() -> None:
    lines = [_line("1000", "100.00", "0.00", "dup"), _line("4000", "0.00", "100.00", "dup")]
    assert _check(_tb(lines)) == "duplicate_source_ref"


@pytest.mark.parametrize("declared", [("100.01", "100.00"), ("100.00", "99.99"), ("0.00", "0.00")])
def test_ac11_computed_totals_that_differ_from_declared_are_a_control_totals_mismatch(
    declared: tuple[str, str],
) -> None:
    assert _check(_tb(BALANCED, declared=declared)) == "control_totals_mismatch"


def test_ac11_unequal_debits_and_credits_that_match_the_declared_totals_are_unbalanced() -> None:
    assert _check(_tb(UNBALANCED)) == "unbalanced"


def test_ac11_a_one_cent_imbalance_is_unbalanced() -> None:
    lines = [_line("1000", "100.01", "0.00"), _line("4000", "0.00", "100.00")]
    assert _check(_tb(lines)) == "unbalanced"


def test_ac11_a_balanced_trial_balance_of_nothing_is_a_zero_total() -> None:
    lines = [_line("1000", "0.00", "0.00"), _line("4000", "0.00", "0.00")]
    assert _check(_tb(lines)) == "zero_total"


def test_ac11_a_trial_balance_with_any_value_is_not_a_zero_total() -> None:
    lines = [_line("1000", "0.00", "0.01"), _line("4000", "0.01", "0.00")]
    assert _check(_tb(lines)) is None


# --- the check order: the earlier failure wins ------------------------------------------------

ORDER: list[tuple[str, NormalisedTrialBalance]] = [
    ("empty", _tb([], declared=("1.00", "1.00"), period=OTHER, currency="EUR")),
    (
        "period_mismatch",
        _tb(
            [_line("A", "1.00", "0.00", "r"), _line("a", "0.00", "5.00", "r")],
            declared=("9.00", "9.00"),
            period=OTHER,
            currency="EUR",
        ),
    ),
    (
        "unsupported_currency",
        _tb(
            [_line("A", "1.00", "0.00", "r"), _line("a", "0.00", "5.00", "r")],
            declared=("9.00", "9.00"),
            currency="EUR",
        ),
    ),
    (
        "duplicate_account",
        _tb(
            [_line("A", "1.00", "0.00", "r"), _line("a", "0.00", "5.00", "r")],
            declared=("9.00", "9.00"),
        ),
    ),
    (
        "duplicate_source_ref",
        _tb(
            [_line("A", "1.00", "0.00", "r"), _line("B", "0.00", "5.00", "r")],
            declared=("9.00", "9.00"),
        ),
    ),
    ("control_totals_mismatch", _tb(UNBALANCED, declared=("9.00", "9.00"))),
    ("unbalanced", _tb(UNBALANCED)),
    (
        "zero_total",
        _tb([_line("A", "0.00", "0.00"), _line("B", "0.00", "0.00")]),
    ),
]


@pytest.mark.parametrize(("expected", "tb"), ORDER, ids=[name for name, _ in ORDER])
def test_ac11_each_check_wins_over_every_later_one(
    expected: str, tb: NormalisedTrialBalance
) -> None:
    assert _check(tb) == expected


def test_ac11_the_order_is_the_contracts() -> None:
    assert [name for name, _ in ORDER] == [
        "empty",
        "period_mismatch",
        "unsupported_currency",
        "duplicate_account",
        "duplicate_source_ref",
        "control_totals_mismatch",
        "unbalanced",
        "zero_total",
    ]


def test_ac11_validate_is_stable_for_the_same_input() -> None:
    tb = ORDER[3][1]
    assert [_check(tb) for _ in range(3)] == ["duplicate_account"] * 3


def test_ac9_normalise_error_carries_a_short_code_and_is_an_exception() -> None:
    error = NormaliseError("malformed_payload")
    assert isinstance(error, Exception)
    assert error.code == "malformed_payload"
