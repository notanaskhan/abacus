"""A-05-T24 (TASK-3211; DEC-2211): the contributions and remittance engine.

Row acceptance: "Dec 26 to Jan 9 is 9 business days with Jan 1 excluded, lost earnings are 64.38
with an excise exposure of 9.66, and the waterfall foots to 1,366,900." Figures from A-05 §1
(Northwind 401(k), EBP-04 a).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.assurance.compute.ebp import remittance as r

HOLIDAYS = frozenset({date(2025, 12, 25), date(2026, 1, 1)})
D = Decimal


def test_ac_nine_business_days_with_jan_1_excluded() -> None:
    found = r.timing(
        date(2025, 12, 26),
        date(2026, 1, 9),
        established_practice_days=2,
        participants=412,
        holidays=HOLIDAYS,
    )
    assert found.business_days == 9
    assert found.due_on == date(2025, 12, 30)
    assert found.late
    assert len(found.stamp.inputs_hash) == 64


def test_ac_a_large_plan_never_gets_the_seven_day_safe_harbor() -> None:
    large = r.timing(
        date(2025, 12, 26), date(2026, 1, 6), established_practice_days=2, participants=100,
        holidays=HOLIDAYS,
    )  # fmt: skip
    small = r.timing(
        date(2025, 12, 26), date(2026, 1, 6), established_practice_days=2, participants=99,
        holidays=HOLIDAYS,
    )  # fmt: skip
    assert large.late
    assert not small.late  # 7 business days from Dec 26 is Jan 7


def test_ac_lost_earnings_and_excise() -> None:
    found = r.lost_earnings(D("33540.00"), date(2025, 12, 30), date(2026, 1, 9))
    assert found.interest_days == 10
    assert found.lost_earnings == D("64.38")
    assert found.excise_exposure == D("9.66")
    assert found.rate_refs == ("2025-Q4", "2026-Q1")


def test_ac_a_missing_quarter_is_refused_never_guessed() -> None:
    with pytest.raises(r.RateMissing):
        r.lost_earnings(D("100.00"), date(2030, 1, 1), date(2030, 1, 5))


def test_ac_line_4a_is_deferrals_only() -> None:
    assert r.schedule_h_4a([D("33540")]) == D("33540")


def test_ac_the_waterfall_foots_to_the_statements() -> None:
    found = r.waterfall(
        deferrals=D("878400"),
        match=D("392100"),
        deposited_after_year_end=D("48600"),
        rollovers=D("96400"),
        receivable=D("48600"),
        per_statements=D("1366900"),
    )
    assert [s.running for s in found.steps] == [
        D("878400"),
        D("1270500"),
        D("1221900"),
        D("1318300"),
        D("1366900"),
    ]
    assert found.foots
    assert D("48600") == D("33540") + D("15060")  # the receivable: deferrals and match
