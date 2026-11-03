"""The follow-up clock (N-04 US-7.4): sent date + days, calendar days, never rolled (I-CLOCKS)."""

from __future__ import annotations

from datetime import date, timedelta

DEFAULT_FOLLOW_UP_DAYS = 60


def follow_up_on(sent_on: date, days: int = DEFAULT_FOLLOW_UP_DAYS) -> date:
    if not 1 <= days <= 365:
        raise ValueError("follow-up days must be between 1 and 365")
    return sent_on + timedelta(days=days)
