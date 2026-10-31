"""Business-day arithmetic for the compute packages (A-03-T21; chapter 03 §10.1; DEC-76).

Pure functions over a holiday set the caller passes in: the kernel holds no holiday data. Services
resolve the set from K-02's published reference sets (`platform.api`) and pass it down. K-02-T07's
IRC §7503 roll and business-day count moved here from `practice/compute/calendar.py`, which
re-imports them, so the I-CLOCKS goldens are unchanged.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final

_SATURDAY: Final = 5


def is_business_day(day: date, holidays: frozenset[date]) -> bool:
    """A weekday that is not one of `holidays`."""
    return day.weekday() < _SATURDAY and day not in holidays


def roll(day: date, holidays: frozenset[date]) -> tuple[date, bool]:
    """IRC §7503: the next business day on or after `day`, and whether it moved."""
    moved = day
    while not is_business_day(moved, holidays):
        moved += timedelta(days=1)
    return moved, moved != day


def add_business_days(start: date, n: int, holidays: frozenset[date]) -> date:
    """`start` plus `n` business days (`n` ≥ 0); 0 is `start` rolled forward."""
    if n < 0:
        raise ValueError("n must not be negative")
    day, _ = roll(start, holidays)
    for _ in range(n):
        day += timedelta(days=1)
        day, _ = roll(day, holidays)
    return day
