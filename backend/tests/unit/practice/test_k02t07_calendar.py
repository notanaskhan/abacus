"""K-02-T07 (TASK-2209; SPEC-500 AC-21 to AC-25; K-02 §3 F2): the calendar engine's pure
functions.

The row's acceptance: pure functions return Sep 15, 2026 for Ridgeline's extended 1065 and Nov 16,
2026 for a June-30 Form 990, and the same inputs always give the same inputs_hash. The rule rows
here are test inputs shaped like K-02 §2's US-2.1 cases, never shipped content (AGENTS 16); the
I-CLOCKS goldens with their citations are K-02-T15's.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.practice.compute import calendar
from abacus.modules.practice.compute.calendar import Offset, Place, Postponement, Rule

NO_HOLIDAYS: frozenset[date] = frozenset()


def _rule(
    form: str,
    months: int,
    day: int,
    ext: str | None,
    ext_months: int | None,
    *,
    fye: str = "any",
    ext_day: int | None = None,
) -> Rule:
    return Rule(form, fye, Offset(months, day), ext, ext_months, ext_day)  # type: ignore[arg-type] -- a fye literal


F1065 = _rule("1065", 3, 15, "7004", 6, fye="calendar_year")
F1040 = _rule("1040", 4, 15, "4868", 6, fye="calendar_year")
F990 = _rule("990", 5, 15, "8868", 6)
F1041 = _rule("1041", 4, 15, "7004", 5, fye="calendar_year", ext_day=30)
F5500 = _rule("5500", 7, 31, "5558", 3, ext_day=15)


def test_ac21_ridgelines_1065_rolls_off_a_sunday_and_extends_to_sep_15_2026() -> None:
    dates = calendar.due_dates(F1065, date(2025, 12, 31), NO_HOLIDAYS)
    assert (dates.original_due_on, dates.original_rolled) == (date(2026, 3, 16), True)
    assert (dates.extended_due_on, dates.extended_rolled) == (date(2026, 9, 15), False)
    assert dates.extension_form == "7004"


def test_ac21_a_june_30_990_is_due_nov_16_2026_and_extends_to_may_17_2027() -> None:
    dates = calendar.due_dates(F990, date(2026, 6, 30), NO_HOLIDAYS)
    assert dates.original_due_on == date(2026, 11, 16)  # Nov 15 is a Sunday
    assert dates.extended_due_on == date(2027, 5, 17)  # May 15 is a Saturday


def test_ac21_ty2026_extended_dates() -> None:
    end = date(2026, 12, 31)
    assert calendar.due_dates(F1065, end, NO_HOLIDAYS).extended_due_on == date(2027, 9, 15)
    assert calendar.due_dates(F1041, end, NO_HOLIDAYS).extended_due_on == date(2027, 9, 30)
    assert calendar.due_dates(F1040, end, NO_HOLIDAYS).extended_due_on == date(2027, 10, 15)
    five = calendar.due_dates(F5500, end, NO_HOLIDAYS)
    assert five.original_due_on == date(2027, 8, 2)  # Jul 31 is a Saturday
    assert five.extended_due_on == date(2027, 10, 15)


def test_ac21_the_feld_1040_extends_to_oct_15_2026() -> None:
    assert calendar.due_dates(F1040, date(2025, 12, 31), NO_HOLIDAYS).extended_due_on == date(
        2026, 10, 15
    )


def test_ac22_a_legal_holiday_rolls_like_a_weekend() -> None:
    # A DC-style holiday on a Friday moves a Friday due date to Monday (IRC §7503).
    holiday = frozenset({date(2027, 4, 16)})
    probe = _rule("probe", 4, 16, None, None, fye="calendar_year")
    dates = calendar.due_dates(probe, date(2026, 12, 31), holiday)
    assert (dates.original_due_on, dates.original_rolled) == (date(2027, 4, 19), True)
    assert dates.extended_due_on is None


def test_ac22_a_calendar_year_rule_does_not_answer_a_fiscal_year() -> None:
    assert calendar.pick_rule([F1065], "1065", date(2026, 6, 30)) is None
    fiscal = _rule("1065", 3, 15, "7004", 6, fye="fiscal_year")
    assert calendar.pick_rule([F1065, fiscal], "1065", date(2026, 6, 30)) == fiscal
    anyone = _rule("1065", 3, 15, "7004", 6)
    assert calendar.pick_rule([anyone, F1065], "1065", date(2025, 12, 31)) == F1065


def test_ac23_a_covered_location_gets_the_postponed_date_with_its_notice() -> None:
    notice = Postponement(
        "PROBE-01",
        (calendar.Area("CA", frozenset({"Probe County"})),),
        date(2026, 1, 7),
        date(2026, 10, 14),
        date(2026, 10, 15),
    )
    covered = calendar.due_dates(
        F1065, date(2025, 12, 31), NO_HOLIDAYS, [notice], Place("CA", "Probe County")
    )
    assert covered.postponement_notice_id == "PROBE-01"
    assert covered.extended_due_on == date(2026, 10, 15)
    assert covered.original_due_on == date(2026, 10, 15)
    assert covered.postponed_to == date(2026, 10, 15)
    elsewhere = calendar.due_dates(
        F1065, date(2025, 12, 31), NO_HOLIDAYS, [notice], Place("CA", "Other County")
    )
    assert elsewhere.postponement_notice_id is None
    assert elsewhere.extended_due_on == date(2026, 9, 15)
    nowhere = calendar.due_dates(F1065, date(2025, 12, 31), NO_HOLIDAYS, [notice], None)
    assert nowhere.postponement_notice_id is None


def test_ac23_a_whole_state_notice_covers_every_county() -> None:
    notice = Postponement(
        "PROBE-02",
        (calendar.Area("TX", frozenset()),),
        date(2026, 3, 1),
        date(2026, 3, 31),
        date(2026, 6, 15),
    )
    assert calendar.postpone(date(2026, 3, 16), [notice], Place("TX"), None) == (
        date(2026, 6, 15),
        "PROBE-02",
    )


def test_ac24_clocks_are_calendar_days_and_never_roll() -> None:
    assert calendar.clock_due("au_c_230_assembly", date(2026, 10, 9)) == date(2026, 12, 8)
    assert calendar.clock_due("au_c_265_communication", date(2026, 10, 9)) == date(2026, 12, 8)
    assert calendar.clock_due("ftc_notice", date(2026, 9, 10)) == date(2026, 10, 10)  # a Saturday
    assert calendar.clock_due("form_8879_retention", date(2026, 4, 15)) == date(2029, 4, 15)
    assert calendar.clock_due("form_8879_retention", date(2028, 2, 29)) == date(2031, 2, 28)


def test_ac24_add_business_days_skips_weekends_and_holidays() -> None:
    holidays = frozenset({date(2026, 11, 26)})  # a Thursday
    assert calendar.add_business_days(date(2026, 11, 24), 2, holidays) == date(2026, 11, 27)
    assert calendar.add_business_days(date(2026, 11, 28), 0, holidays) == date(2026, 11, 30)
    with pytest.raises(ValueError):
        calendar.add_business_days(date(2026, 11, 24), -1, holidays)


def test_ac25_the_same_inputs_give_the_same_hash() -> None:
    inputs = {"form": "1065", "period_end": date(2025, 12, 31), "ids": ["a", "b"]}
    assert calendar.inputs_hash(inputs) == calendar.inputs_hash(dict(reversed(inputs.items())))
    assert calendar.inputs_hash(inputs) != calendar.inputs_hash({**inputs, "form": "1120"})
    assert calendar.inputs_hash(inputs).startswith("sha256:")


# --- properties ---------------------------------------------------------------------------------

days = st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31))
holiday_sets = st.frozensets(days, max_size=30)


@settings(max_examples=200, deadline=None)
@given(days, holiday_sets)
def test_ac22_a_rolled_date_is_the_first_business_day_on_or_after(
    day: date, holidays: frozenset[date]
) -> None:
    rolled, moved = calendar.roll(day, holidays)
    assert rolled >= day and calendar.is_business_day(rolled, holidays)
    assert moved is (rolled != day)
    assert calendar.roll(rolled, holidays) == (rolled, False)  # idempotent


@settings(max_examples=200, deadline=None)
@given(days, st.integers(min_value=0, max_value=40), holiday_sets)
def test_ac24_business_days_are_monotonic(day: date, n: int, holidays: frozenset[date]) -> None:
    later = calendar.add_business_days(day, n + 1, holidays)
    assert later > calendar.add_business_days(day, n, holidays)


@settings(max_examples=200, deadline=None)
@given(days, st.sampled_from(["au_c_230_assembly", "au_c_265_communication", "ftc_notice"]))
def test_ac24_a_clock_is_a_fixed_number_of_calendar_days(day: date, kind: str) -> None:
    due = calendar.clock_due(kind, day)  # type: ignore[arg-type] -- a clock kind
    assert (due - day).days == calendar.CLOCK_DAYS[kind]  # type: ignore[index] -- a clock kind


@settings(max_examples=200, deadline=None)
@given(days, st.integers(min_value=0, max_value=24), st.integers(min_value=1, max_value=31))
def test_ac21_add_months_lands_in_the_right_month(day: date, months: int, dom: int) -> None:
    moved = calendar.add_months(day, months, dom)
    assert (moved.year * 12 + moved.month) - (day.year * 12 + day.month) == months
    assert moved.day <= dom
