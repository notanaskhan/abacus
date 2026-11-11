"""T-05-T10 (TASK-6811; SPEC-651 AC-5.3, AC-10.1; Reg. §1.706-4; DEC-3409): allocation by ownership
period on Ridgeline's 2025 structure (TXP-06 A, verbatim).

Row acceptance: "Ridgeline allocates 628,100 per period, partner totals sum to 1,256,200, and Pell
Street II LLC receives nothing in period 1."
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from abacus.modules.tax.compute.entity.allocation import (
    AllocationInvalid,
    Segment,
    allocate_item,
    boundary,
    segments,
)

D = Decimal
GP, SHAH, PSV, PS2, FELD = (
    "Ridgeline GP LLC",
    "Meera Shah",
    "Pell Street Ventures LLC",
    "Pell Street II LLC",
    "Jonah Feld",
)
OPENING = {GP: D(2), SHAH: D(38), PSV: D(35), FELD: D(25)}
AFTER = {GP: D(2), SHAH: D(38), PSV: D(30), PS2: D(5), FELD: D(25)}  # the 6/30/2025 assignment


def _ridgeline() -> tuple[Segment, ...]:
    return segments(
        date(2025, 1, 1),
        date(2025, 12, 31),
        [(None, OPENING), (date(2025, 6, 30), AFTER)],
        "monthly",
    )


def test_ac_5_3_two_periods_of_628100_and_partner_totals() -> None:
    result = allocate_item(
        D("1256200"),
        _ridgeline(),
        method="interim_closing",
        convention="monthly",
        segment_amounts=[D("628100"), D("628100")],
    )
    assert result.segment_amounts == (D("628100"), D("628100"))
    first, second = result.shares
    assert first == {GP: D(12562), SHAH: D(238678), PSV: D(219835), FELD: D(157025), PS2: D(0)}
    assert first[PS2] == 0  # Pell Street II receives nothing in period 1
    assert second == {
        GP: D(12562),
        SHAH: D(238678),
        PSV: D(188430),
        PS2: D(31405),
        FELD: D(157025),
    }
    assert result.totals == {
        GP: D(25124),
        SHAH: D(477356),
        PSV: D(408265),
        FELD: D(314050),
        PS2: D(31405),
    }
    assert sum(result.totals.values()) == D("1256200")
    assert all(
        sum(s.values()) == a for s, a in zip(result.shares, result.segment_amounts, strict=True)
    )


def test_the_segments_follow_the_convention() -> None:
    assert boundary(date(2025, 6, 18), "monthly") == date(2025, 6, 30)
    assert boundary(date(2025, 6, 10), "semi_monthly") == date(2025, 6, 15)
    assert boundary(date(2025, 6, 18), "semi_monthly") == date(2025, 6, 30)
    assert boundary(date(2025, 6, 18), "calendar_day") == date(2025, 6, 18)
    first, second = _ridgeline()
    assert (first.start, first.end, second.start, second.end) == (
        date(2025, 1, 1),
        date(2025, 6, 30),
        date(2025, 7, 1),
        date(2025, 12, 31),
    )


def test_proration_splits_by_calendar_day_and_foots() -> None:
    segs = segments(
        date(2025, 1, 1),
        date(2025, 12, 31),
        [(None, OPENING), (date(2025, 6, 30), AFTER)],
        "calendar_day",
    )
    result = allocate_item(D("1256200"), segs, method="proration", convention="calendar_day")
    assert sum(result.segment_amounts) == D("1256200")
    assert result.segment_amounts[0] == D(
        "622938"
    )  # 1,256,200 * 181 / 365 = 622,938.08, largest remainder
    assert sum(result.totals.values()) == D("1256200")


def test_proration_is_calendar_day_only() -> None:
    with pytest.raises(AllocationInvalid) as raised:
        allocate_item(D("100"), _ridgeline(), method="proration", convention="monthly")
    assert raised.value.code == "proration_is_calendar_day_only"


def test_interim_closing_needs_segments_that_sum_to_the_year() -> None:
    with pytest.raises(AllocationInvalid) as raised:
        allocate_item(
            D("1256200"),
            _ridgeline(),
            method="interim_closing",
            convention="monthly",
            segment_amounts=[D("628100"), D("628099")],
        )
    assert raised.value.code == "segments_do_not_sum_to_the_year"


def test_interests_must_sum_to_100() -> None:
    with pytest.raises(AllocationInvalid):
        segments(date(2025, 1, 1), date(2025, 12, 31), [(None, {GP: D(50)})], "monthly")


def test_the_stamp_names_the_inputs() -> None:
    a = allocate_item(
        D("1256200"),
        _ridgeline(),
        method="interim_closing",
        convention="monthly",
        segment_amounts=[D("628100"), D("628100")],
    )
    b = allocate_item(
        D("1256200"),
        _ridgeline(),
        method="interim_closing",
        convention="monthly",
        segment_amounts=[D("628100"), D("628100")],
    )
    assert a.stamp == b.stamp and a.stamp.engine_name == "entity.allocation"
