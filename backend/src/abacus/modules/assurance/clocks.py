"""The post-release clocks (A-07-T36; A-07 F7; SPEC-644 AC-36; AU-C 230, AU-C 265). Pure date
code: the workflow, AUD-24, AUD-25 and AUD-22 read the same answers.

- **Archive** (AU-C 230): the documentation completion date is the release date + 60 days. The
  clock reads "Archive in N days · by <date>"; at 7 days or fewer it is at risk (red tint, a
  notification); the day after the deadline it is overdue.
- **AU-C 265**: the significant deficiencies and material weaknesses letter is due 60 days after
  the release; overdue the next day until it is sent.
- **Form 5500** (EBP): due the last day of the seventh month after the plan year end, extended by
  Form 5558 to the fifteenth day of the tenth month. Accrued tracks the client's filing; it never
  files.

Golden (AC-36): an Oct 9, 2026 release gives Dec 8 for both clocks; Dec 3 reads "Archive in 5 days"
at risk; Dec 9 is overdue.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal

ARCHIVE_DAYS: Final = 60  # AU-C 230
AU_C_265_DAYS: Final = 60
RISK_DAYS: Final = 7
ClockKind = Literal["archive", "au_c_265"]
ClockState = Literal["running", "at_risk", "due_today", "overdue", "stopped"]


@dataclass(frozen=True)
class Clock:
    kind: ClockKind
    deadline: date
    days_left: int  # negative once overdue
    state: ClockState


def deadline(kind: ClockKind, release_date: date) -> date:
    days = ARCHIVE_DAYS if kind == "archive" else AU_C_265_DAYS
    return release_date + timedelta(days=days)


def read(kind: ClockKind, release_date: date, today: date, *, stopped: bool = False) -> Clock:
    """The clock on `today` (the firm's business date). `stopped`: the archive locked, or the
    265 letter sent."""
    due = deadline(kind, release_date)
    left = (due - today).days
    if stopped:
        state: ClockState = "stopped"
    elif left < 0:
        state = "overdue"
    elif left == 0:
        state = "due_today"
    elif left <= RISK_DAYS:
        state = "at_risk"
    else:
        state = "running"
    return Clock(kind, due, left, state)


@dataclass(frozen=True)
class Timer:
    """When the workflow wakes for a clock, and what it then reports."""

    kind: ClockKind
    at: date
    event: Literal["deadline_risk", "deadline", "overdue"]


def timers(release_date: date) -> list[Timer]:
    """The durable timers a release starts, in order: the archive at deadline - 7 days, the
    deadline and the day after; AU-C 265 at its due date and the day after."""
    archive = deadline("archive", release_date)
    letter = deadline("au_c_265", release_date)
    found = [
        Timer("archive", archive - timedelta(days=RISK_DAYS), "deadline_risk"),
        Timer("archive", archive, "deadline"),
        Timer("archive", archive + timedelta(days=1), "overdue"),
        Timer("au_c_265", letter, "deadline"),
        Timer("au_c_265", letter + timedelta(days=1), "overdue"),
    ]
    return sorted(found, key=lambda t: (t.at, t.kind))


def _end_of_month(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _add_months(day: date, months: int) -> tuple[int, int]:
    total = day.year * 12 + (day.month - 1) + months
    return total // 12, total % 12 + 1


def form_5500_due(plan_year_end: date) -> tuple[date, date]:
    """(due, extended due) for a plan year ending `plan_year_end`."""
    year, month = _add_months(plan_year_end, 7)
    due = _end_of_month(year, month)
    year, month = _add_months(plan_year_end, 10)
    return due, date(year, month, 15)
