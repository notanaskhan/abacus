"""T-03-T18 (TASK-6004; DEC-2604): the tax-year rollover's drafts.

The drafts are reviewed before `refdata draft` and never written inside the repository (DEC-76);
holidays are computed by statute and observed on the weekday rule; rolled sets move their year and
carry everything else over for a person to re-verify (DEC-85: tolerances are never defaulted).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import cast

import pytest

from abacus_tools.refdata import Refused
from abacus_tools.refdata_rollover import REPO, holidays, observed, roll, write_draft


def test_ac_the_2028_holidays_are_the_statutes_dates_observed() -> None:
    assert [(r["date"], r["jurisdiction"]) for r in holidays(2028)] == [
        ("2027-12-31", "US"),  # Sat Jan 1, 2028, observed Friday
        ("2028-01-17", "US"),
        ("2028-02-21", "US"),
        ("2028-04-17", "DC"),  # Sun Apr 16, observed Monday: TY2027's 1040s are due Apr 18
        ("2028-05-29", "US"),
        ("2028-06-19", "US"),
        ("2028-07-04", "US"),
        ("2028-09-04", "US"),
        ("2028-10-09", "US"),
        ("2028-11-10", "US"),  # Sat Nov 11, observed Friday
        ("2028-11-23", "US"),
        ("2028-12-25", "US"),
    ]


def test_inauguration_day_is_a_dc_holiday_in_its_year_only() -> None:
    # Sat Jan 20, 2029 stays on the Saturday: only a Sunday moves it (5 U.S.C. 6103(c)).
    assert ("2029-01-20", "DC") in [(r["date"], r["jurisdiction"]) for r in holidays(2029)]
    assert not [r for r in holidays(2028) if r["name"] == "Inauguration Day"]


def test_the_weekend_rule() -> None:
    assert observed(date(2027, 7, 4)) == date(2027, 7, 5)
    assert observed(date(2027, 12, 25)) == date(2027, 12, 24)
    assert observed(date(2027, 11, 11)) == date(2027, 11, 11)


def test_ac_rolled_sets_move_their_year_and_carry_the_rest() -> None:
    form = {
        "kind": "form_8879_set",
        "rows": [
            {"return_type": "1040", "tax_year": 2026, "jurisdiction": "US",
             "authorization_form": "8879", "revision": "2026"},
        ],
        "tolerances": {"total_income_or_agi_usd": 50, "tax_withholding_refund_balance_usd": 14},
    }  # fmt: skip
    rolled = roll("form_8879_set", form, 2027)
    first = cast(list[dict[str, object]], form["rows"])[0]
    assert rolled["rows"] == [{**first, "tax_year": 2027}]
    assert rolled["tolerances"] == form["tolerances"]
    thresholds = {
        "kind": "information_return_thresholds",
        "rows": [{"form": "1099-MISC", "payment_year": 2026, "threshold_usd": 600,
                  "min_transactions": None}],
    }  # fmt: skip
    moved = cast(
        list[dict[str, object]], roll("information_return_thresholds", thresholds, 2027)["rows"]
    )
    assert moved[0]["payment_year"] == 2027
    rules = {"kind": "due_date_rules", "rows": [{"form": "1040", "fye_rule": "calendar_year"}]}
    assert roll("due_date_rules", rules, 2027)["rows"] == rules["rows"]


def test_ac_roll_refuses_a_kind_it_does_not_roll_or_a_mismatched_version() -> None:
    with pytest.raises(Refused):
        roll("retention_minimums", {"kind": "retention_minimums", "rows": []}, 2027)
    with pytest.raises(Refused):
        roll("form_8879_set", {"kind": "due_date_rules", "rows": []}, 2027)


@pytest.mark.source_scan  # reads the repository layout: left out under mutmut (DEC-599)
def test_ac_no_draft_is_written_inside_the_repository(tmp_path: Path) -> None:
    payload = {"kind": "legal_holidays", "rows": holidays(2028)}
    with pytest.raises(Refused):
        write_draft(REPO / "docs", "legal_holidays", 2028, payload, None)
    path = write_draft(tmp_path, "legal_holidays", 2028, payload, None)
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["review"]["status"].startswith("draft")
    assert body["rows"] == payload["rows"]
