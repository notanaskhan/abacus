"""A-03-T21 (SPEC-580 AC-5): kernel.calendar, business days over a holiday set passed in."""

from __future__ import annotations

import inspect
from datetime import date

import pytest

from abacus.kernel import calendar as kernel_calendar
from abacus.kernel.calendar import add_business_days, is_business_day, roll
from abacus.modules.practice.compute import calendar as practice_calendar

JULY_4 = frozenset({date(2027, 7, 5)})  # observed Monday


def test_ac5_weekends_and_passed_holidays_are_not_business_days() -> None:
    assert is_business_day(date(2027, 7, 2), frozenset())  # Friday
    assert not is_business_day(date(2027, 7, 3), frozenset())  # Saturday
    assert not is_business_day(date(2027, 7, 5), JULY_4)
    assert is_business_day(date(2027, 7, 5), frozenset())


def test_ac5_roll_moves_forward_and_says_whether_it_moved() -> None:
    assert roll(date(2027, 7, 3), JULY_4) == (date(2027, 7, 6), True)
    assert roll(date(2027, 7, 6), JULY_4) == (date(2027, 7, 6), False)


def test_ac5_add_business_days_skips_weekends_and_holidays() -> None:
    assert add_business_days(date(2027, 7, 2), 1, JULY_4) == date(2027, 7, 6)
    assert add_business_days(date(2027, 7, 3), 0, JULY_4) == date(2027, 7, 6)
    assert add_business_days(date(2027, 7, 1), 5, frozenset()) == date(2027, 7, 8)
    with pytest.raises(ValueError):
        add_business_days(date(2027, 7, 1), -1, frozenset())


def test_ac5_practice_re_imports_the_kernel_functions_unchanged() -> None:
    assert practice_calendar.add_business_days is kernel_calendar.add_business_days
    assert practice_calendar.is_business_day is kernel_calendar.is_business_day
    assert practice_calendar.roll is kernel_calendar.roll


def test_ac5_the_kernel_holds_no_holiday_data() -> None:
    source = inspect.getsource(kernel_calendar)
    assert "holidays: frozenset[date]" in source
    assert "date(" not in source.replace("def ", "")  # no literal dates (DEC-76)
