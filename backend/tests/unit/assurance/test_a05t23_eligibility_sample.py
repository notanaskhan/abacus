"""A-05-T23 (DEC-2225, DEC-2328): what EBP-03's sample shows, by code, with no birth date."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from abacus.modules.assurance.compute.ebp import eligibility
from abacus.modules.assurance.ebp_eligibility_sample import eligible_shown, rate_label

ENTRY_2025 = date(2025, 6, 1)


def test_eligible_on_is_shown_where_hire_plus_three_months_governs() -> None:
    entry = eligibility.entry(date(1990, 1, 15), date(2025, 2, 10))
    assert eligible_shown(entry, date(2025, 2, 10)) == date(2025, 5, 10)


def test_eligible_on_is_withheld_where_it_would_be_the_21st_birthday() -> None:
    dob = date(2004, 9, 1)
    entry = eligibility.entry(dob, date(2025, 1, 6))
    assert entry.eligible_on == date(2025, 9, 1)
    assert eligible_shown(entry, date(2025, 1, 6)) is None


def test_the_rate_label_reads_the_election_or_codes_escalated_default() -> None:
    assert rate_label(Decimal("8.0000"), ENTRY_2025, 2025, flagged=False) == "8% elected"
    assert rate_label(None, ENTRY_2025, 2025, flagged=False) == "6% default"
    assert rate_label(None, date(2023, 7, 1), 2025, flagged=False) == "8% default"
    assert rate_label(Decimal(0), ENTRY_2025, 2025, flagged=True) == "0% — no opt-out"
    assert rate_label(Decimal(0), ENTRY_2025, 2025, flagged=False) == "0%"
    assert rate_label(None, None, 2025, flagged=False) == ""
