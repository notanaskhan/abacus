"""C-01-T14 (C-01 §4.8, QC-7): the close engine's business-day arithmetic, on the platform's
`legal_holidays` reference set and `kernel.calendar`. It is the same calendar `practice` uses for
due dates, read directly: `practice` is an edge module that nothing imports (I-02)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final, cast

from abacus.kernel import calendar
from abacus.kernel.clock import today
from abacus.modules.platform.api import LegalHolidaysPayload, references_in_effect

# Look past the latest day asked about, so a holiday just beyond it still rolls (as practice does).
_ROLL_MARGIN: Final = timedelta(days=14)


async def _holidays(latest: date) -> frozenset[date]:
    as_of = max(await today(), latest + _ROLL_MARGIN)
    days: set[date] = set()
    for found in await references_in_effect("legal_holidays", as_of):
        days.update(row.date for row in cast(LegalHolidaysPayload, found.payload).rows)
    return frozenset(days)


async def add_business_days(start: date, n: int) -> date:
    """`start` plus `n` business days, skipping weekends and the legal holidays in effect."""
    holidays = await _holidays(start + timedelta(days=2 * max(n, 0)))
    return calendar.add_business_days(start, n, holidays)


async def business_days_between(start: date, end: date) -> int:
    """The business days after `start` up to and including `end` (0 when `end` is not after
    `start`): a close due Thu Sep 10 is 2 business days past due on Mon Sep 14."""
    if end <= start:
        return 0
    holidays = await _holidays(end)
    return sum(
        calendar.is_business_day(start + timedelta(days=d), holidays)
        for d in range(1, (end - start).days + 1)
    )
