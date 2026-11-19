"""Q-05-T11 (S51 partials, TASK-8731; DEC-5725): the assembly runs on the first business day after
a quarter ends (weekends and legal holidays roll it forward) and on no other day; the Schedule is
daily and registered with the evidence module."""

from __future__ import annotations

from datetime import date

from abacus.modules.evidence import api
from abacus.modules.evidence.destruction_jobs import (
    ASSEMBLE_ID,
    DestructionAssembleWorkflow,
    first_business_day_after_quarter_end,
)

NEW_YEAR = frozenset({date(2027, 1, 1)})


def test_ac_the_first_business_day_of_a_quarter_only() -> None:
    assert first_business_day_after_quarter_end(date(2026, 10, 1), frozenset())  # a Thursday
    assert not first_business_day_after_quarter_end(date(2026, 10, 2), frozenset())
    assert not first_business_day_after_quarter_end(date(2026, 9, 30), frozenset())
    assert not first_business_day_after_quarter_end(date(2026, 11, 2), frozenset())


def test_ac_weekends_and_holidays_roll_it_forward() -> None:
    # Jan 1, 2027 is a Friday and a holiday: the first business day is Monday Jan 4.
    assert not first_business_day_after_quarter_end(date(2027, 1, 1), NEW_YEAR)
    assert first_business_day_after_quarter_end(date(2027, 1, 4), NEW_YEAR)
    # Aug 1, 2026 is a Saturday (not a quarter start either way); Jul 1, 2028 is a Saturday.
    assert first_business_day_after_quarter_end(date(2028, 7, 3), frozenset())


def test_ac_the_schedule_is_registered_daily_with_the_module() -> None:
    found = [s for s in api.SCHEDULES if s.id == ASSEMBLE_ID]
    assert len(found) == 1 and found[0].workflow is DestructionAssembleWorkflow
    assert found[0].every.days == 1
    assert DestructionAssembleWorkflow in api.WORKFLOWS
