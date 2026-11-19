"""The filing-deadlines read model's derived fields (T-08-T10; TASK-8727; SPEC-710; HOME-03;
DEC-5721), pure: risk tier and day counts computed on read in the firm's zone (never stored), a
postponement moving the effective date, and the month and week groupings.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

Risk = Literal["overdue", "due_7", "due_30", "later", "done"]


@dataclass(frozen=True, slots=True)
class Deadline:
    item: str
    due_on: date
    postponed_to: date | None = None
    done: bool = False

    @property
    def effective(self) -> date:
        return self.postponed_to or self.due_on


def firm_today(now: datetime, zone: str) -> date:
    return now.astimezone(ZoneInfo(zone)).date()


def days_left(d: Deadline, today: date) -> int:
    return (d.effective - today).days


def risk(d: Deadline, today: date) -> Risk:
    if d.done:
        return "done"
    left = days_left(d, today)
    if left < 0:
        return "overdue"
    if left <= 7:
        return "due_7"
    if left <= 30:
        return "due_30"
    return "later"


def on_day(deadlines: Iterable[Deadline], day: date) -> list[Deadline]:
    return [d for d in deadlines if d.effective == day]


def week_of(day: date) -> tuple[date, date]:
    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


__all__ = ["Deadline", "Risk", "days_left", "firm_today", "on_day", "risk", "week_of"]
