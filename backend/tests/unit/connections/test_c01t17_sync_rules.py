"""C-01-T17 (TASK-8069): the ledger sync's pure rules: business hours in the firm's zone, the next
opening, month bounds, the content digest and the register's footing."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from abacus.modules.connections.ledger_sync import in_business_hours, next_opening
from abacus.modules.connections.ledger_sync_contract import _meter_state
from abacus.modules.ledger.month_ledger import (
    MonthAccount,
    MonthRegisterLine,
    _check_register,
    _sides,
    content_fingerprint,
    month_bounds,
)
from abacus.modules.ledger.normalise import LedgerLine, NormalisedTrialBalance
from abacus.modules.ledger.service import Unvalidated

CT = ZoneInfo("America/Chicago")
HOURS = {"start": "07:00", "end": "19:00"}


def test_ac_ticks_only_inside_firm_business_hours() -> None:
    # Tue Sep 8, 2026 10:02 AM CDT is 15:02 UTC.
    assert in_business_hours(datetime(2026, 9, 8, 15, 2, tzinfo=UTC), HOURS, CT)
    assert not in_business_hours(datetime(2026, 9, 8, 11, 59, tzinfo=UTC), HOURS, CT)  # 6:59
    assert not in_business_hours(datetime(2026, 9, 9, 0, 0, tzinfo=UTC), HOURS, CT)  # 19:00
    assert not in_business_hours(datetime(2026, 9, 12, 15, 0, tzinfo=UTC), HOURS, CT)  # Sat


def test_next_opening_is_seven_am_firm_time_on_the_next_weekday() -> None:
    friday_night = datetime(2026, 9, 12, 1, 0, tzinfo=UTC)  # Fri 8 PM CDT
    assert next_opening(friday_night, HOURS, CT) == datetime(2026, 9, 14, 7, 0, tzinfo=CT)


def test_month_bounds() -> None:
    assert month_bounds("2026-08") == (date(2026, 8, 1), date(2026, 8, 31))
    assert month_bounds("2026-12") == (date(2026, 12, 1), date(2026, 12, 31))
    assert month_bounds("2028-02") == (date(2028, 2, 1), date(2028, 2, 29))


def _accounts() -> list[MonthAccount]:
    return [
        MonthAccount(
            "35", "1000", "Operating", "asset", "Bank", "Checking", None, None, False, True
        ),
        MonthAccount("60", "6000", "Repairs", "expense", "Expense", None, None, None, False, True),
        MonthAccount(
            "80", "2000", "Card", "liability", "Credit Card", None, None, None, False, True
        ),
    ]


def _line(ref: str, account: str, amount: str) -> MonthRegisterLine:
    return MonthRegisterLine(
        ref, account, "t1", date(2026, 8, 14), "Expense", None, None, None, None, Decimal(amount)
    )


def test_ac_the_register_must_foot_in_natural_signs() -> None:
    kinds = {a.external_id: a.classification for a in _accounts()}
    balanced = [_line("a", "60", "2560.00"), _line("b", "80", "2560.00")]
    _check_register(balanced, kinds, date(2026, 8, 1), date(2026, 8, 31))
    assert _sides("expense", Decimal(5)) == (Decimal(5), Decimal(0))
    assert _sides("liability", Decimal(5)) == (Decimal(0), Decimal(5))
    with pytest.raises(Unvalidated, match="register_unbalanced"):
        _check_register(balanced[:1], kinds, date(2026, 8, 1), date(2026, 8, 31))
    with pytest.raises(Unvalidated, match="register_outside_month"):
        _check_register(balanced, kinds, date(2026, 9, 1), date(2026, 9, 30))
    with pytest.raises(Unvalidated, match="register_unknown_account"):
        _check_register([_line("c", "99", "1")], kinds, date(2026, 8, 1), date(2026, 8, 31))


def test_ac_an_unchanged_month_digests_the_same() -> None:
    tb = NormalisedTrialBalance(
        date(2026, 8, 1), date(2026, 8, 31), "USD",
        (LedgerLine("35", "Operating", Decimal(10), Decimal(0), "35"),
         LedgerLine("80", "Card", Decimal(0), Decimal(10), "80")),
        Decimal(10), Decimal(10),
    )  # fmt: skip
    register = [_line("a", "60", "2560.00"), _line("b", "80", "2560.00")]
    first = content_fingerprint(tb, _accounts(), register)
    assert first == content_fingerprint(tb, list(reversed(_accounts())), register)
    changed = [_line("a", "60", "2561.00"), _line("b", "80", "2561.00")]
    assert first != content_fingerprint(tb, _accounts(), changed)


def test_meter_warns_at_80_percent_and_stops_at_100() -> None:
    assert _meter_state(10, None).value == "ok"
    assert _meter_state(799, 1000).value == "ok"
    assert _meter_state(800, 1000).value == "warning"
    assert _meter_state(1000, 1000).value == "exhausted"
