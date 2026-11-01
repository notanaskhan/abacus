"""T-01-T44 (TASK-2620; ADR-078): independent acceptance tests for T-01-T22 (the fake CCH Axcess),
T-01-T23 (the §7216 consents slice) and T-01-T45 (transcript parser and comparison), written from
the contracts and SPEC-501, not from the implementation's own tests.

- The fake conforms (every file passes `conformance`) and refuses any firm that is not synthetic.
- The consents slice foots: its tiles are C19's six statuses and add to its rows.
- The parser reads a transcript the goldens never used (the Okafor household) and the comparison
  is exact Decimal arithmetic: a one-cent difference is a difference, `$0.10 + $0.20` style sums
  never drift, and a payer named differently but the same is still paired.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.tax.compute.transcripts import (
    FiledItem,
    compare,
    parse_amount,
    parse_transcript,
)
from abacus_tools.fakes import cch_axcess as cch
from abacus_tools.synthetic.scenarios.brightwater_hale import consents_7216 as consents

OKAFOR = """Wage and Income Transcript
Tax Period Requested: December, 2025

Form W-2 Wage and Tax Statement
Employer:
Employer Identification Number (EIN):XXXXX2201
HARBORVIEW LOGISTICS INC
Wages, Tips and Other Compensation:........$64,250.10
Federal Income Tax Withheld:...............$7,010.00

Form 1099-INT Interest Income
Payer:
Payer's Federal Identification Number (FIN):XXXXX2202
MERIDIAN SAVINGS BANK
Interest:.................................$0.30

Form 1099-DIV Dividends and Distributions
Payer:
Payer's Federal Identification Number (FIN):XXXXX2203
NORTHSTAR INDEX FUNDS
Total Ordinary Dividends:.................$1,212.45
"""


@pytest.mark.parametrize("version", [1, 2])
def test_every_fake_file_conforms_at_each_engine_version(version: int) -> None:
    """Every engine version the fake emits conforms (T-01-T22 checks V3)."""
    fake = cch.CchAxcessFake()
    export = cch.read_export(
        cch.sample_export(
            cch.FELD, 2025, "1040", [cch.EngineValue("f1040.refund", "1040", "35a", "253")]
        )
    )
    files = {
        "values.csv": fake.values_file(export, version),
        "diagnostics.csv": fake.diagnostics_file(export, version, "informational"),
        **fake.pdf_files(export, version),
    }
    for name, content in files.items():
        assert cch.conformance(name, content) == [], name


async def test_the_fake_refuses_a_firm_that_is_not_synthetic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def not_synthetic(_tenant: TenantContext) -> bool:
        return False

    monkeypatch.setattr(cch, "is_synthetic_firm", not_synthetic)
    monkeypatch.setattr(cch, "settings", lambda: SimpleNamespace(environment="local"))
    # A synthetic environment is not enough: the firm itself must be synthetic.
    with pytest.raises(cch.FakeCchRefused):
        await cch.cch_for(TenantContext(uuid.uuid4(), "human", "u"))


def test_the_consents_slice_foots_to_c19s_tiles() -> None:
    assert set(consents.TILES) == {
        "signed",
        "expiring",
        "requested",
        "expired",
        "declined",
        "revoked",
    }
    assert sum(consents.TILES.values()) == len(consents.ROWS) == consents.TOTAL
    assert all(len(r.purposes) >= 1 for r in consents.ROWS)


@pytest.mark.parametrize(
    ("text", "want"),
    [
        ("$64,250.10", Decimal("64250.10")),
        ("($12.00)", Decimal("-12.00")),
        ("-$9,812.00", Decimal("-9812.00")),
        ("0.00", Decimal("0.00")),
        ("$1,2,3.00", None),
        ("12.3", None),
    ],
)
def test_amounts_parse_exactly_or_not_at_all(text: str, want: Decimal | None) -> None:
    assert parse_amount(text) == want


def test_an_unseen_transcript_parses_and_compares_to_the_cent() -> None:
    parsed = parse_transcript(OKAFOR, "wage_income")
    assert parsed.tax_year == 2025
    amounts = [i.amount for i in parsed.information_returns]
    assert amounts == [Decimal("64250.10"), Decimal("0.30"), Decimal("1212.45")]
    filed = [
        FiledItem("W-2", "Harborview Logistics, Inc.", Decimal("64250.10")),
        FiledItem("1099-INT", "Meridian Savings Bank", Decimal("0.1") + Decimal("0.2")),
        FiledItem("1099-DIV", "Northstar Index Funds", Decimal("1212.44")),
    ]
    result = compare(parsed, filed, 2025)
    statuses = [(line.form, line.status, line.difference) for line in result.lines]
    assert statuses == [
        ("W-2", "agrees", Decimal("0.00")),
        ("1099-INT", "agrees", Decimal("0.00")),
        ("1099-DIV", "differs", Decimal("0.01")),
    ]
    assert result.result == "differences"
    assert result.difference_total == Decimal("0.01")


def test_an_information_return_missing_from_the_return_is_not_on_return() -> None:
    parsed = parse_transcript(OKAFOR, "wage_income")
    result = compare(
        parsed, [FiledItem("W-2", "Harborview Logistics Inc", Decimal("64250.10"))], 2025
    )
    missing = [line for line in result.lines if line.status == "not_on_return"]
    assert [(line.form, line.difference) for line in missing] == [
        ("1099-INT", Decimal("0.30")),
        ("1099-DIV", Decimal("1212.45")),
    ]
    assert result.not_on_transcript == ()


def test_a_year_that_does_not_match_is_refused_not_compared() -> None:
    parsed = parse_transcript(OKAFOR, "wage_income")
    result = compare(parsed, [], 2024)
    assert result.lines == ()
    assert result.problems != ()
