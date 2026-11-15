"""The compute floor (ADR-079; coverage-thresholds.yaml `compute: 100`): each refusal of the
EBP rate reader returns None for a person to read, never a guessed rate."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.assurance.compute.ebp.eligibility import match_pct_from, rates_from

STEP = "1% each Jan 1 after one full plan year up to 10%"


def test_a_second_first_tier_is_refused() -> None:
    assert match_pct_from("100% of first 1% + 50% of first 5%") is None


def test_the_reader_reads_a_well_formed_match() -> None:
    assert match_pct_from("100% of first 1% + 50% of next 5%") == Decimal("3.5")


def test_an_unreadable_step_or_match_leaves_the_rates_unread() -> None:
    assert rates_from({"default_deferral_rate": "3%", "auto_escalation": "1% a year",
                       "safe_harbor_match": "100% of first 1%"}) is None  # fmt: skip


def test_a_cap_below_the_default_rate_is_refused() -> None:
    rates = {
        "default_deferral_rate": "6%",
        "auto_escalation": "1% each Jan 1 after one full plan year up to 4%",
        "safe_harbor_match": "100% of first 1% + 50% of next 5%",
    }
    assert rates_from(rates) is None


def test_well_formed_rates_read() -> None:
    rates = {
        "default_deferral_rate": "3%",
        "auto_escalation": STEP,
        "safe_harbor_match": "100% of first 1% + 50% of next 5%",
    }
    found = rates_from(rates)
    assert found is not None
    assert found.match_pct == Decimal("3.5")
