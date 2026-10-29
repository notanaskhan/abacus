"""R-01-T30: independent tests (ADR-078) for R-01-T24's follow-up policy rules, written from R-01
§3.8 and §3.9 (DEC-74), not from the implementing suite: cadence and weekend moves, the maximum,
P-06's per-binder override, and the one day the preparer hears the limit was reached."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from abacus.modules.communications.follow_up_policy import (
    DEFAULT,
    FollowUpPolicy,
    Sent,
    limit_reached_today,
    next_send_at,
    next_sequence_by_policy,
)

MON_SEP_14: date = date(2026, 9, 14)


def test_s81_cadence_five_from_monday_lands_on_saturday_and_moves_to_monday() -> None:
    last = datetime(2026, 9, 14, 14, 0, tzinfo=UTC)  # 9:00 AM CDT
    five = next_send_at(FollowUpPolicy(cadence_days=5), last, "America/Chicago")
    assert five.shifted_from == date(2026, 9, 19)
    assert five.next_send_at == datetime(2026, 9, 21, 14, 0, tzinfo=UTC)
    seven = next_send_at(DEFAULT, last, "America/Chicago")
    assert (seven.next_send_at, seven.shifted_from) == (
        datetime(2026, 9, 21, 14, 0, tzinfo=UTC),
        None,
    )
    assert DEFAULT.send_local_time == time(9, 0)


def test_s91_at_most_four_and_never_before_the_due_date() -> None:
    due = MON_SEP_14
    assert next_sequence_by_policy(due, Sent(0, None), due, DEFAULT) is None  # not yet overdue
    assert next_sequence_by_policy(due, Sent(0, None), date(2026, 9, 15), DEFAULT) == 1
    assert (
        next_sequence_by_policy(due, Sent(1, date(2026, 9, 15)), date(2026, 9, 21), DEFAULT)
        is None
    )
    assert (
        next_sequence_by_policy(due, Sent(1, date(2026, 9, 15)), date(2026, 9, 22), DEFAULT) == 2
    )
    assert (
        next_sequence_by_policy(due, Sent(4, date(2026, 10, 6)), date(2026, 12, 1), DEFAULT)
        is None
    )


def test_s91_the_per_binder_override_wins_and_bad_overrides_are_ignored() -> None:
    assert DEFAULT.overridden({"every_days": 3, "max": 2}).cadence_days == 3
    assert DEFAULT.overridden({"every_days": 3, "max": 2}).max_reminders == 2
    bad_overrides: list[dict[str, object]] = [
        {"every_days": 0, "max": 2},
        {"every_days": 3, "max": 9},
        {"every_days": "3"},
    ]
    for bad in bad_overrides:
        assert DEFAULT.overridden(bad) == DEFAULT


def test_s91_the_limit_is_raised_on_one_day_only() -> None:
    sent = Sent(4, date(2026, 10, 5))  # a Monday
    due = date(2026, 10, 12)
    assert limit_reached_today(sent, due, DEFAULT) is True
    assert limit_reached_today(sent, date(2026, 10, 13), DEFAULT) is False
    assert limit_reached_today(Sent(3, date(2026, 10, 5)), due, DEFAULT) is False
