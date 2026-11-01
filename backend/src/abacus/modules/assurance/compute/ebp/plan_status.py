"""The EBP plan-status engine (A-05-T10; A-05 §3 F1, §4.4; DEC-1955). Pure: no clock, no I/O.

- **Filer status** (Form 5500 instructions): a plan with 100 or more participants with account
  balances at the beginning of the plan year files as a large plan; the 80-120 rule lets a plan
  that filed small last year stay small while that count is 120 or fewer.
- **Due date**: the last day of the seventh month after the plan year ends; with a Form 5558 on
  file, two and a half months later (the 15th of the tenth month). A due date on a weekend or a
  holiday rolls to the next business day (holidays are passed in; `kernel.calendar`).
- **Plan number**: three digits, 001 to 999 (Form 5500 line 1b). 000 and a recordkeeper's plan
  ID are refused with the line 1b helper; code checks the format, a person enters the number.
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from abacus.kernel.calendar import roll

ENGINE_NAME: Final = "ebp_plan_status"
ENGINE_VERSION: Final = "1"
LARGE_PLAN_AT: Final = 100
EIGHTY_ONE_TWENTY: Final = 120
_PN: Final = re.compile(r"^[0-9]{3}$")
FORM_5500_HELPER: Final = "form_5500_line_1b"

Filer = Literal["large_plan", "small_plan"]


@dataclass(frozen=True)
class PlanStatus:
    filer_status: Filer
    eighty_one_twenty: bool  # the plan stays small under the 80-120 rule
    form5500_due_on: date
    extended: bool
    rolled: bool  # the due date fell on a weekend or holiday and moved


def filer_status(
    participants_boy_with_balances: int, prior_year_filer: Filer | None
) -> tuple[Filer, bool]:
    if participants_boy_with_balances < LARGE_PLAN_AT:
        return "small_plan", False
    if prior_year_filer == "small_plan" and participants_boy_with_balances <= EIGHTY_ONE_TWENTY:
        return "small_plan", True
    return "large_plan", False


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + n
    return total // 12, total % 12 + 1


def due_date(
    plan_year_end: date, *, form_5558_filed_on: date | None, holidays: frozenset[date]
) -> tuple[date, bool, bool]:
    """(due date, extended, rolled)."""
    year, month = _add_months(plan_year_end.year, plan_year_end.month, 7)
    due = _month_end(year, month)
    extended = form_5558_filed_on is not None
    if extended:
        year, month = _add_months(plan_year_end.year, plan_year_end.month, 10)
        due = date(year, month, 15)
    rolled_to, rolled = roll(due, holidays)
    return rolled_to, extended, rolled


def plan_status(
    *,
    plan_year_end: date,
    participants_boy_with_balances: int,
    prior_year_filer: Filer | None,
    form_5558_filed_on: date | None,
    holidays: frozenset[date],
) -> PlanStatus:
    status, kept_small = filer_status(participants_boy_with_balances, prior_year_filer)
    due, extended, rolled = due_date(
        plan_year_end, form_5558_filed_on=form_5558_filed_on, holidays=holidays
    )
    return PlanStatus(status, kept_small, due, extended, rolled)


def plan_number_problem(value: str, *, recordkeeper_plan_id: str | None) -> str | None:
    """None for a valid PN; else why not ("format", "zero", "recordkeeper_id")."""
    clean = value.strip()
    if recordkeeper_plan_id and clean == recordkeeper_plan_id.strip():
        return "recordkeeper_id"
    if not _PN.fullmatch(clean):
        return "format"
    if clean == "000":
        return "zero"
    return None
