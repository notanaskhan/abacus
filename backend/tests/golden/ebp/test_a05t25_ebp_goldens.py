"""Independent AC goldens for the EBP services and engines (A-05-T25; ADR-078): the Northwind
PY2025 figure book (`northwind_py2025.yaml`, DEC-1862) asserted with exact Decimal equality, the
remittance and eligibility engines on it, and hypothesis properties for footing and idempotent
recompute. An engine version bump changes every inputs hash, so dependent results read out of
date without being recomputed here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from abacus.modules.assurance.compute.ebp import eligibility, remittance

BOOK = cast(
    dict[str, dict[str, object]],
    yaml.safe_load((Path(__file__).parent / "northwind_py2025.yaml").read_text()),
)


def _d(section: str, key: str) -> Decimal:
    return Decimal(str(BOOK[section][key]))


def test_ebp01_plan_profile_figures() -> None:
    plan = BOOK["plan"]
    assert plan["participants_boy"] == 286
    assert plan["participants_eoy"] == 301
    assert Decimal(str(plan["match_max_pct"])) == eligibility.QACA_MATCH_PCT


def test_census_w3_and_payroll_foot_to_the_cent() -> None:
    assert _d("census", "compensation") == _d("w3", "total") == _d("payroll", "wages")
    assert _d("census", "compensation") == Decimal("14560000.00")
    assert _d("census", "deferrals") == _d("w3", "box12d") == _d("payroll", "deferrals")
    assert _d("w3", "box1") + _d("w3", "box12d") == _d("w3", "total")
    census = BOOK["census"]
    assert census["active"] + census["terminated"] == census["rows"]  # type: ignore[operator] -- the test reaches past the public type


def test_the_receivable_foots() -> None:
    assert _d("receivable", "regular") + _d("receivable", "late") == _d("receivable", "total")
    assert _d("receivable", "total") == Decimal("48600.00")


def test_the_late_remittance_is_9_business_days() -> None:
    late = BOOK["late_remittance"]
    paid = date.fromisoformat(str(late["pay_on"]))
    deposited = date.fromisoformat(str(late["deposited_on"]))
    holidays = frozenset({date(2026, 1, 1)})
    assert remittance.business_days_between(paid, deposited, holidays) == late["business_days"]
    assert Decimal(str(late["amount"])) == Decimal("33540.00")


def test_ebp03_entry_is_the_later_of_age_21_and_three_months() -> None:
    found = eligibility.entry(date(1990, 5, 15), date(2025, 3, 10))
    assert found.eligible_on == date(2025, 6, 10)
    assert found.entry_on == date(2025, 7, 1)


@given(st.decimals(min_value=0, max_value=Decimal("10000000"), places=2))
def test_missed_is_idempotent_and_exact(compensation: Decimal) -> None:
    first = eligibility.missed(compensation)
    second = eligibility.missed(compensation)
    assert first == second
    assert first.deferral == first.deferral.quantize(Decimal("0.01"))
    assert first.match == first.match.quantize(Decimal("0.01"))
    assert first.deferral >= first.match >= 0


@given(
    st.dates(min_value=date(1940, 1, 1), max_value=date(2005, 12, 31)),
    st.dates(min_value=date(2015, 1, 1), max_value=date(2025, 12, 31)),
)
def test_review_of_matching_dates_needs_none(dob: date, hire: date) -> None:
    assert eligibility.review(dob, hire, hire).requires_review is False


def test_a_version_bump_changes_every_inputs_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    before = eligibility.entry(date(1990, 5, 15), date(2025, 3, 10)).inputs_hash
    monkeypatch.setattr(eligibility, "ENGINE_VERSION", "2")
    after = eligibility.entry(date(1990, 5, 15), date(2025, 3, 10)).inputs_hash
    assert before != after
