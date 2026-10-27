"""R-01-T24 (TASK-1421; DEC-74, DEC-563): `next_send_at`, the one rule the GET and the scheduler
share: the cadence in calendar days from the last send's local date, a weekend moved to the
Monday when `weekdays_only`, at `send_local_time` in the recipient's zone; and the per-binder
override (P-06's `follow_up_override`) winning over the firm's cadence and maximum."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

import pytest

from abacus.modules.communications.follow_up_policy import (
    DEFAULT,
    FollowUpPolicy,
    next_send_at,
    next_send_on,
)

CT = "America/Chicago"
MON_14_9AM_CT = datetime(2026, 9, 14, 14, 0, tzinfo=UTC)  # 9:00 AM CDT


def test_ac_seven_days_after_mon_sep_14_9am_is_mon_sep_21_9am() -> None:
    found = next_send_at(DEFAULT, MON_14_9AM_CT, CT)
    assert found.next_send_at == datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    assert found.shifted_from is None


def test_ac_five_days_lands_on_saturday_and_moves_to_monday() -> None:
    found = next_send_at(FollowUpPolicy(cadence_days=5), MON_14_9AM_CT, CT)
    assert found.next_send_at == datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    assert found.shifted_from == date(2026, 9, 19)


def test_without_weekdays_only_the_weekend_day_stands() -> None:
    day, shifted = next_send_on(
        date(2026, 9, 14), FollowUpPolicy(cadence_days=6, weekdays_only=False)
    )
    assert day == date(2026, 9, 20) and shifted is None


def test_the_send_time_is_in_the_recipients_zone() -> None:
    policy = FollowUpPolicy(send_local_time=time(9, 0))
    eastern = next_send_at(policy, MON_14_9AM_CT, "America/New_York")
    assert eastern.next_send_at == datetime(2026, 9, 21, 13, 0, tzinfo=UTC)  # 9:00 AM EDT
    late = datetime(2026, 9, 15, 4, 30, tzinfo=UTC)  # Mon Sep 14, 11:30 PM CT
    assert next_send_at(policy, late, CT).next_send_at == datetime(2026, 9, 21, 14, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("override", "cadence", "most"),
    [
        (None, 7, 4),
        ({"every_days": 5, "max": 2}, 5, 2),
        ({"every_days": 99, "max": 2}, 7, 4),  # out of range: ignored, the firm's applies
        ({"every_days": "5", "max": 2}, 7, 4),
    ],
)
def test_the_binders_override_wins_when_it_is_well_formed(
    override: dict[str, object] | None, cadence: int, most: int
) -> None:
    applied = DEFAULT.overridden(override)
    assert (applied.cadence_days, applied.max_reminders) == (cadence, most)
