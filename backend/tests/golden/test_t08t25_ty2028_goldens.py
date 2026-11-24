"""T-08-T25 (TASK-8918; T-08 AC2.12; SPEC-710 AC-19; chapter 10 §10.9.3 I-CLOCKS; DEC-5920): the
TY2028 golden due dates and the HOME-03 seed dates, against the calendar engine.

Row acceptance: "Goldens prove Apr 17, 2029, Jan 16, 2029, Sep 17, 2029, Oct 1, 2029, Mar 16,
2026 and Nov 16, 2026, and the tax CPA signs them." The cases are transcribed from the law and
OPM's schedule in `calendar/i_clocks_ty2028.yaml`, each with its source; the CPA's signature is
recorded in the TY2028 review memo (a person's step). The holiday list is also the federal and DC
part of the TY2028 holiday drafts, so a published set cannot drift from the goldens unnoticed.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus.modules.practice.compute import calendar
from abacus_tools import refdata_rollover as rollover

GoldenCase = dict[str, Any]  # Any: the golden YAML is untyped data

GOLDEN = Path(__file__).resolve().parent / "calendar" / "i_clocks_ty2028.yaml"
DATA = cast(GoldenCase, yaml.safe_load(GOLDEN.read_text(encoding="utf-8")))
HOLIDAYS = frozenset(cast(list[date], DATA["holidays"]))
REQUIRED = {date(2029, 4, 17), date(2029, 1, 16), date(2029, 9, 17), date(2029, 10, 1),
            date(2026, 3, 16), date(2026, 11, 16)}  # fmt: skip


def _rule(form: str) -> calendar.Rule:
    r = DATA["rules"][form]
    return calendar.Rule(
        form=form, fye_rule="any", original=calendar.Offset(r["months"], r["day"]),
        extension_form=r["extension"], extension_months=r["ext_months"],
        extension_day=r["ext_day"],
    )  # fmt: skip


def _id(case: GoldenCase) -> str:
    return f"{case['form']}-{case['period_end']}-{case.get('quarter', '')}"


@pytest.mark.parametrize("case", DATA["due_dates"], ids=_id)
def test_ty2028_and_seed_due_dates(case: GoldenCase) -> None:
    assert str(case.get("source", "")).strip(), "every golden case names its source"
    found = calendar.due_dates(_rule(case["form"]), case["period_end"], HOLIDAYS)
    assert found.original_due_on == case["original"]
    assert found.original_rolled == bool(case.get("rolled", False))
    assert found.extended_due_on == case["extended"]
    assert found.extended_rolled == bool(case.get("extended_rolled", False))


@pytest.mark.parametrize("case", DATA["installment_dates"], ids=_id)
def test_ty2028_installments(case: GoldenCase) -> None:
    assert str(case.get("source", "")).strip()
    rule = calendar.Rule(
        form=case["form"], fye_rule="calendar_year", original=calendar.Offset(4, 15),
        extension_form=None, extension_months=None,
        installments=tuple(tuple(q) for q in DATA["installments"][case["form"]]),
    )  # fmt: skip
    found = {i.quarter: i for i in calendar.installment_dates(rule, case["period_end"], HOLIDAYS)}
    assert found[case["quarter"]].due_on == case["due"]
    assert found[case["quarter"]].rolled == bool(case.get("rolled", False))


def test_the_rows_acceptance_dates_are_all_proven() -> None:
    proven: set[date] = set()
    for c in DATA["due_dates"]:
        proven |= {c["original"], c["extended"]}
    proven |= {c["due"] for c in DATA["installment_dates"]}
    assert proven >= REQUIRED


def test_the_holiday_drafts_federal_rows_equal_the_goldens() -> None:
    drafted = {
        date.fromisoformat(str(r["date"]))
        for year in (2028, 2029)
        for r in rollover.holidays(year)
    }
    golden = {d for d in HOLIDAYS if date(2027, 12, 31) <= d <= date(2029, 12, 31)}
    assert drafted == golden
