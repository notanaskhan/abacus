"""K-02-T15 (TASK-2313; SPEC-500 AC-56 to AC-58; chapter 10 §10.9.3 I-CLOCKS): the calendar
engine against transcribed golden due dates and clocks, each with its source citation.

Written from the rules (IRC §6072, §6075, §7503, the extension regulations, the Form 5500/5558
instructions, AU-C 230 and 265, 16 CFR 314.4(j), Pub 1345), not from the engine. Every case
must pass and name its source; a case without one fails.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

from abacus.modules.practice.compute import calendar

GOLDEN = Path(__file__).resolve().parent / "calendar" / "i_clocks.yaml"
DATA = cast(dict[str, Any], yaml.safe_load(GOLDEN.read_text(encoding="utf-8")))
HOLIDAYS = frozenset(cast(list[date], DATA["holidays"]))


def _rule(form: str) -> calendar.Rule:
    r = DATA["rules"][form]
    return calendar.Rule(
        form=form,
        fye_rule="any",
        original=calendar.Offset(r["months"], r["day"]),
        extension_form=r["extension"],
        extension_months=r["ext_months"],
        extension_day=r["ext_day"],
    )


def _id(case: dict[str, Any]) -> str:
    return f"{case.get('form', case.get('kind'))}-{case.get('period_end', case.get('start'))}"


@pytest.mark.parametrize("case", DATA["due_dates"], ids=_id)
def test_ac56_due_dates_match_the_golden_with_their_source(case: dict[str, Any]) -> None:
    assert str(case.get("source", "")).strip(), "every golden case names its source"
    found = calendar.due_dates(_rule(case["form"]), case["period_end"], HOLIDAYS)
    assert found.original_due_on == case["original"]
    assert found.original_rolled == bool(case.get("rolled", False))
    assert found.extended_due_on == case["extended"]
    assert found.extended_rolled == bool(case.get("extended_rolled", False))


@pytest.mark.parametrize("case", DATA["clocks"], ids=_id)
def test_ac57_clocks_count_calendar_days_and_never_roll(case: dict[str, Any]) -> None:
    assert str(case.get("source", "")).strip()
    assert calendar.clock_due(case["kind"], case["start"]) == case["due"]


def test_ac58_a_postponement_moves_a_covered_date_never_earlier() -> None:
    notice = calendar.Postponement(
        notice_id="IR-2026-01",
        areas=(calendar.Area("CO", frozenset()),),
        start=date(2026, 3, 1),
        end=date(2026, 5, 31),
        postponed_to=date(2026, 7, 15),
    )
    moved = calendar.due_dates(
        _rule("1040"), date(2025, 12, 31), HOLIDAYS, [notice], calendar.Place("CO", "Denver")
    )
    assert moved.original_due_on == date(2026, 7, 15)
    assert moved.postponement_notice_id == "IR-2026-01"
    elsewhere = calendar.due_dates(
        _rule("1040"), date(2025, 12, 31), HOLIDAYS, [notice], calendar.Place("IL", "Cook")
    )
    assert elsewhere.original_due_on == date(2026, 4, 15)


def test_ac56_the_same_inputs_give_the_same_hash() -> None:
    inputs = {"form": "1065", "period_end": "2025-12-31", "holidays": sorted(map(str, HOLIDAYS))}
    assert calendar.inputs_hash(inputs) == calendar.inputs_hash(dict(reversed(inputs.items())))
