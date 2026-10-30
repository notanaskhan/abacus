"""T-01-T45 (TASK-2600): the transcript parser and comparison's edges, so the library is covered
line for line and branch for branch (the row's acceptance) and hostile text is reported, never
guessed at (ADR-052)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.tax.compute import transcripts as t
from abacus.modules.tax.compute.transcripts import (
    FiledItem,
    ParsedTranscript,
    Problem,
    compare,
    normalise_payer,
    parse_amount,
    parse_transcript,
    payers_match,
)

WI_HEAD = "Wage and Income Transcript\nTax Period Requested: December, 2024\n"
ACCOUNT_HEAD = "Account Transcript\nReport for Tax Period Ending: 12-31-2024\n"


def _wi(body: str) -> ParsedTranscript:
    return parse_transcript(WI_HEAD + body, "wage_income")


def _codes(parsed: ParsedTranscript) -> list[str]:
    return [p.code for p in parsed.problems]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$1,870.00", Decimal("1870.00")),
        ("1870.00", Decimal("1870.00")),
        ("-$9,812.00", Decimal("-9812.00")),
        ("($12.00)", Decimal("-12.00")),
        (" 0.00 ", Decimal("0.00")),
        ("$1,234,567,890,123.45", Decimal("1234567890123.45")),
        ("(12.00", None),
        ("12.00)", None),
        ("1,870", None),
        ("$12,34.00", None),
        ("1870.5", None),
        ("1e3.00", None),
        ("NaN", None),
        ("", None),
    ],
)
def test_ac1_amounts_are_exact_or_refused(text: str, expected: Decimal | None) -> None:
    assert parse_amount(text) == expected


def test_ac2_payer_names_normalise_and_prefix_match() -> None:
    assert normalise_payer("The Front Range Bank, N.A.") == "front range bank"
    assert normalise_payer("Larkspur Pediatrics P.C.") == "larkspur pediatrics"
    assert normalise_payer("LLC") == ""
    assert payers_match("FRON", "Front Range Bank")  # the IRS's four-character truncation
    assert payers_match("Front Range Bank", "FRONT RANGE BANK, N.A.")
    assert not payers_match("FRO", "Front Range Bank")  # too short to be a prefix
    assert not payers_match("Lakeview", "Front Range Bank")
    assert not payers_match(None, "Front Range Bank")
    assert not payers_match("Inc.", "Front Range Bank")


def test_ac3_wage_income_payer_on_same_or_following_line() -> None:
    parsed = _wi(
        "Taxpayer: XXX-XX-0000\n"  # before any form: ignored
        "Form 1099-INT Interest Income\n"
        "Payer: Front Range Bank\n"
        "Payer: Somebody Else\n"  # the first payer wins
        "Interest:....$1,870.00\n"
        "\n"
        "Form 1099-INT\n"
        "Payer:\n"
        "Payer's Federal Identification Number (FIN):XXXXX1106\n"
        "LAKEVIEW CREDIT UNION\n"
        "123 MAIN ST\n"  # an address line after the name: ignored
        "Submission Type:....Original document\n"
        "Interest:....$1,250.00\n"
    )
    assert parsed.parsed
    assert [(r.payer_name, r.amount) for r in parsed.information_returns] == [
        ("Front Range Bank", Decimal("1870.00")),
        ("LAKEVIEW CREDIT UNION", Decimal("1250.00")),
    ]
    assert parsed.problems == ()


def test_ac4_wage_income_problems_are_reported_by_line() -> None:
    parsed = _wi(
        "Form 1099-INT Interest Income\n"  # line 3: no payer
        "Interest:....$10.00\n"
        "Interest:....$11.00\n"  # line 5: duplicate field
        "Form 1099-DIV Dividends\n"  # line 6: no compared field
        "Payer: Aspen\n"
        "Qualified Dividends:....12.5\n"  # line 8: unreadable amount
        "Form 5498 IRA Contribution Information\n"  # line 9: not a compared form
        "Trustee: Alpine Trust\n"
        "IRA Contributions:....$6,500.00\n"
    )
    assert [(p.line_no, p.code) for p in parsed.problems] == [
        (5, "duplicate_field"),
        (3, "form_without_payer"),
        (8, "unreadable_amount"),
        (6, "form_without_amount"),
        (9, "form_not_compared"),
    ]
    forms = parsed.information_returns
    assert [(r.form, r.amount) for r in forms] == [
        ("1099-INT", Decimal("10.00")),
        ("1099-DIV", None),
        ("5498", None),
    ]
    assert forms[2].fields == (("IRA Contributions", Decimal("6500.00")),)


def test_ac5_header_kind_mismatch_and_missing_year_are_refused() -> None:
    mismatch = parse_transcript(ACCOUNT_HEAD, "wage_income")
    assert _codes(mismatch) == ["kind_mismatch"]
    assert not mismatch.parsed
    no_year = parse_transcript("Wage and Income Transcript\nForm W-2\n", "wage_income")
    assert no_year.tax_year is None
    assert _codes(no_year)[0] == "no_tax_year"
    assert not no_year.parsed
    headerless = parse_transcript("Tax Period Requested: 12/31/2023\r\n", "wage_income")
    assert (headerless.tax_year, headerless.parsed) == (2023, True)


def test_ac6_hostile_sizes_are_refused() -> None:
    too_long = parse_transcript("x" * (t.MAX_TEXT_CHARS + 1), "wage_income")
    assert _codes(too_long) == ["too_large"]
    assert not too_long.parsed
    too_many_lines = parse_transcript("\n" * t.MAX_LINES, "account")
    assert _codes(too_many_lines) == ["too_large"]
    forms = "".join(
        f"Form W-2\nEmployer: E{i}\nWages, Tips and Other Compensation: 1.00\n"
        for i in range(t.MAX_ENTRIES + 1)
    )
    capped = _wi(forms)
    assert len(capped.information_returns) == t.MAX_ENTRIES
    assert _codes(capped)[-1] == "too_large"
    rows = "".join("150 Tax return filed 04-14-2025 $1.00\n" for _ in range(t.MAX_ENTRIES + 1))
    capped_account = parse_transcript(ACCOUNT_HEAD + rows, "account")
    assert len(capped_account.transactions) == t.MAX_ENTRIES
    assert _codes(capped_account) == ["too_large"]


def test_ac7_account_rows_and_balance() -> None:
    parsed = parse_transcript(
        "Record of Account\n"
        "Report for Tax Period Ending: December 31, 2024\n"
        "ACCOUNT BALANCE: ($15.00)\n"
        "Account balance: $99.00\n"  # the first balance wins
        "2024 is not a code\n"
        "150X not a row\n"
        "150 Tax return filed 20251505 04-14-2025 $22,418.00\n"
        "922 Review of unreported income 02-30-2026 $0.00\n"  # line 8: no such date
        "290\n"  # line 9: a code with no row
        "806 W-2 or 1099 withholding 04-15-2025 -$19,146.00\n",
        "record_of_account",
    )
    assert parsed.account_balance == Decimal("-15.00")
    assert [(r.code, r.cycle, r.posted_on, r.amount) for r in parsed.transactions] == [
        ("150", "20251505", date(2025, 4, 14), Decimal("22418.00")),
        ("806", None, date(2025, 4, 15), Decimal("-19146.00")),
    ]
    assert [(p.line_no, p.code) for p in parsed.problems] == [
        (8, "unreadable_transaction"),
        (9, "unreadable_transaction"),
    ]


def _filed(*rows: tuple[str, str, str]) -> list[FiledItem]:
    return [FiledItem(form, payer, Decimal(amount)) for form, payer, amount in rows]


def test_ac8_comparison_matches_prefers_equal_amount_and_reports_both_sides() -> None:
    parsed = _wi(
        "Form 1099-INT\nPayer: FRON\nInterest: $100.00\n"
        "Form 1099-INT\nPayer: FRON\nInterest: $250.00\n"
        "Form 1099-INT\nPayer: LAKE\nInterest: $40.00\n"
        "Form 1099-DIV\nPayer: ASPE\nOther: $1.00\n"
    )
    filed = _filed(
        ("1099-INT", "Front Range Bank", "250.00"),
        ("1099-INT", "Front Range Bank", "90.00"),
        ("W-2", "Front Range Bank", "100.00"),  # another form never matches
        ("1098", "Summit Home Lending", "500.00"),
    )
    result = compare(parsed, filed, 2024)
    assert [
        (ln.transcript_amount, ln.return_amount, ln.difference, ln.status) for ln in result.lines
    ] == [
        (Decimal("100.00"), Decimal("90.00"), Decimal("10.00"), "differs"),
        (Decimal("250.00"), Decimal("250.00"), Decimal("0.00"), "agrees"),
        (Decimal("40.00"), None, Decimal("40.00"), "not_on_return"),
    ]
    assert result.result == "differences"
    assert result.difference_total == Decimal("50.00")
    assert result.agreeing == (("1099-INT", 1),)
    assert result.not_on_transcript == (filed[2], filed[3])
    assert result.not_compared == (12,)
    assert result.problems == (Problem(12, "form_without_amount"),)


def test_ac9_a_negative_difference_is_kept_signed() -> None:
    parsed = _wi("Form W-2\nEmployer: Cobalt\nWages, Tips and Other Compensation: $90.00\n")
    result = compare(parsed, _filed(("W-2", "Cobalt Ridge", "100.00")), 2024)
    assert result.difference_total == Decimal("-10.00")
    assert result.result == "differences"


@pytest.mark.parametrize(
    ("parsed", "year", "code"),
    [
        (parse_transcript(ACCOUNT_HEAD, "account"), 2024, "not_wage_income"),
        (
            parse_transcript("Wage and Income Transcript\n", "wage_income"),
            2024,
            "transcript_not_parsed",
        ),
        (parse_transcript(WI_HEAD, "wage_income"), 2025, "tax_year_mismatch"),
    ],
)
def test_ac10_comparison_is_never_computed_on_a_guess(
    parsed: ParsedTranscript, year: int, code: str
) -> None:
    filed = _filed(("W-2", "Cobalt", "1.00"))
    result = compare(parsed, filed, year)
    assert result.result == "differences"
    assert result.lines == ()
    assert result.difference_total == Decimal("0.00")
    assert result.not_on_transcript == tuple(filed)
    assert [p.code for p in result.problems] == [code]


def test_ac11_empty_transcript_agrees_with_an_empty_return() -> None:
    result = compare(_wi(""), [], 2024)
    assert (result.result, result.lines, result.differing) == ("agrees", (), ())
