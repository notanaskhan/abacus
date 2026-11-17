"""Q-02-T33: the incident register's FTC clock (Q-02 AC-38; I-CLOCKS)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from abacus.modules.platform.api import CLOCK_DAYS, NOTIFY_THRESHOLD, incident_clock
from abacus.modules.platform.incidents import (
    clock_day,
    discovered_on,
    notification_event,
    reason_sha256,
)

CHICAGO = "America/Chicago"


def test_ac38_a_sep_10_discovery_is_due_sat_oct_10_with_no_business_day_roll() -> None:
    discovered = datetime(2026, 9, 10, 14, 5, tzinfo=UTC)
    due = incident_clock(discovered, CHICAGO)
    assert due == date(2026, 10, 10)
    assert due.weekday() == 5  # a Saturday stays a Saturday
    assert CLOCK_DAYS == 30


def test_ac38_the_day_counts_in_the_firm_zone_day_4_of_30_on_mon_sep_14() -> None:
    discovered = datetime(2026, 9, 10, 14, 5, tzinfo=UTC)
    assert clock_day(discovered, CHICAGO, date(2026, 9, 14)) == 4
    assert clock_day(discovered, CHICAGO, date(2026, 9, 10)) == 0


def test_ac38_the_discovery_date_is_the_firm_zones_not_utcs() -> None:
    # 02:00 UTC on Sep 11 is still the evening of Sep 10 in Chicago.
    late = datetime(2026, 9, 11, 2, 0, tzinfo=UTC)
    assert discovered_on(late, CHICAGO) == date(2026, 9, 10)
    assert incident_clock(late, CHICAGO) == date(2026, 10, 10)
    assert incident_clock(late, "UTC") == date(2026, 10, 11)
    offset = datetime(2026, 9, 10, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    assert incident_clock(offset, CHICAGO) == date(2026, 10, 10)


def test_ac38_a_naive_discovery_is_refused() -> None:
    with pytest.raises(ValueError, match="time zone"):
        incident_clock(datetime(2026, 9, 10), CHICAGO)


@pytest.mark.parametrize(
    ("consumers", "unencrypted", "expected"),
    [
        (600, True, True),
        (NOTIFY_THRESHOLD, True, True),
        (499, True, False),
        (600, False, False),
        (600, None, False),
        (None, True, False),
    ],
)
def test_ac38_a_notification_event_is_500_or_more_unencrypted_consumers(
    consumers: int | None, unencrypted: bool | None, expected: bool
) -> None:
    assert notification_event(consumers, unencrypted) is expected


def test_q02t33_the_reason_is_kept_only_as_its_fingerprint() -> None:
    digest = reason_sha256("Accrued confirmed the exposure")
    assert len(digest) == 64 and "Accrued" not in digest
