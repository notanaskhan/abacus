"""T-01-T45 (TASK-2600; T-01 §3.6; CLI-05 a): golden comparisons on the Whitleys' synthetic
transcripts, by exact Decimal.

`transcripts/` holds the four transcripts Kevin Osei pulled under the 8821 (Wage & Income and
Account, TY2024 and TY2025) and the two returns as filed. The designed figures are the two
1099-INTs not on the TY2024 return, 1,870.00 + 1,250.00 = 3,120.00 (the CP2000's unreported
interest), and four agreeing forms (W-2 x 2, 1098, 1099-INT x 1); TC 922 on Aug 24, 2026 on the
TY2024 account and TC 150 on Apr 10, 2026 with a 0.00 balance on TY2025. Amounts in the YAML are
quoted text read as `Decimal`; a float is refused.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from abacus.modules.tax.compute.transcripts import (
    COMPARE_VERSION,
    FiledItem,
    ParsedTranscript,
    TranscriptKind,
    compare,
    parse_transcript,
    transactions_with_code,
)

HERE = Path(__file__).parent / "transcripts"


def _text(name: str) -> str:
    return (HERE / name).read_text(encoding="utf-8")


def _filed(name: str) -> list[FiledItem]:
    rows = yaml.safe_load((HERE / name).read_text(encoding="utf-8"))
    items: list[FiledItem] = []
    for row in rows:
        assert isinstance(row["amount"], str), "amounts are quoted text, never a float"
        items.append(FiledItem(str(row["form"]), row["payer_name"], Decimal(row["amount"])))
    return items


def _parsed(name: str, kind: TranscriptKind) -> ParsedTranscript:
    parsed = parse_transcript(_text(name), kind)
    assert parsed.parsed, parsed.problems
    return parsed


def test_ac1_whitley_2024_two_1099_int_not_on_return_total_3120() -> None:
    parsed = _parsed("whitley_wage_income_2024.txt", "wage_income")
    assert parsed.tax_year == 2024
    assert [r.form for r in parsed.information_returns] == [
        "W-2",
        "W-2",
        "1098",
        "1099-INT",
        "1099-INT",
        "1099-INT",
    ]

    result = compare(parsed, _filed("whitley_filed_2024.yaml"), 2024)

    assert result.result == "differences"
    assert result.version == COMPARE_VERSION
    differing = [
        (line.form, line.payer_name, line.transcript_amount, line.return_amount, line.status)
        for line in result.differing
    ]
    assert differing == [
        ("1099-INT", "FRONT RANGE BANK", Decimal("1870.00"), None, "not_on_return"),
        ("1099-INT", "LAKEVIEW CREDIT UNION", Decimal("1250.00"), None, "not_on_return"),
    ]
    assert result.difference_total == Decimal("3120.00")
    assert str(result.difference_total) == "3120.00"
    assert sum(line.difference for line in result.differing) == Decimal("1870.00") + Decimal(
        "1250.00"
    )
    assert result.agreeing == (("W-2", 2), ("1098", 1), ("1099-INT", 1))
    assert sum(count for _, count in result.agreeing) == 4
    assert result.not_on_transcript == ()
    assert result.not_compared == ()
    assert result.problems == ()


def test_ac2_whitley_2025_agrees_to_return() -> None:
    parsed = _parsed("whitley_wage_income_2025.txt", "wage_income")
    result = compare(parsed, _filed("whitley_filed_2025.yaml"), 2025)
    assert result.result == "agrees"
    assert result.differing == ()
    assert result.difference_total == Decimal("0.00")
    assert result.agreeing == (("W-2", 2), ("1098", 1), ("1099-INT", 2))


def test_ac3_whitley_2024_account_tc_922_review_not_an_assessment() -> None:
    parsed = _parsed("whitley_account_2024.txt", "account")
    assert parsed.tax_year == 2024
    assert parsed.account_balance == Decimal("0.00")
    (review,) = transactions_with_code(parsed, "922")
    assert review.posted_on == date(2026, 8, 24)
    assert review.explanation == "Review of unreported income"
    assert review.amount == Decimal("0.00")  # a review, not an assessment: nothing is assessed
    (filed,) = transactions_with_code(parsed, "150")
    assert (filed.cycle, filed.amount) == ("20251505", Decimal("22418.00"))
    # The account foots: tax assessed less withholding and the payment leaves the balance.
    assert sum(t.amount for t in parsed.transactions) == parsed.account_balance


def test_ac4_whitley_2025_account_tc_150_apr_10_balance_zero() -> None:
    parsed = _parsed("whitley_account_2025.txt", "account")
    (filed,) = transactions_with_code(parsed, "150")
    assert filed.posted_on == date(2026, 4, 10)
    assert parsed.account_balance == Decimal("0.00")
    assert transactions_with_code(parsed, "922") == ()
    assert sum(t.amount for t in parsed.transactions) == parsed.account_balance


@pytest.mark.parametrize(
    "name",
    ["whitley_wage_income_2024.txt", "whitley_wage_income_2025.txt"],
)
def test_ac5_masked_identifiers_never_read_as_money(name: str) -> None:
    parsed = _parsed(name, "wage_income")
    for info in parsed.information_returns:
        labels = {label.casefold() for label, _ in info.fields}
        assert not any("identification" in label or "security" in label for label in labels)
