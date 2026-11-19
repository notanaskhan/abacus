"""T-08-T10 (TASK-8727; DEC-5721): risk tiers are computed on read in the firm's zone (9:24 AM CT
on Sep 14 is Sep 14 there), a postponement moves the effective date, and a day's items count by
their effective date."""

from __future__ import annotations

from datetime import UTC, date, datetime

from abacus.modules.practice.compute.deadlines import Deadline, firm_today, on_day, risk

NOW = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)


def test_ac_risk_tiers_on_read_in_the_firm_zone() -> None:
    today = firm_today(NOW, "America/Chicago")
    assert today == date(2026, 9, 14)
    assert risk(Deadline("a", date(2026, 9, 15)), today) == "due_7"
    assert risk(Deadline("b", date(2026, 9, 1)), today) == "overdue"
    assert risk(Deadline("c", date(2026, 10, 1)), today) == "due_30"
    assert risk(Deadline("d", date(2026, 9, 1), done=True), today) == "done"
    late = Deadline("e", date(2026, 9, 15), postponed_to=date(2026, 11, 16))
    assert risk(late, today) == "later"


def test_ac_items_count_on_their_effective_day() -> None:
    items = [Deadline(f"r{i}", date(2026, 9, 15)) for i in range(12)]
    items.append(Deadline("moved", date(2026, 9, 15), postponed_to=date(2026, 10, 15)))
    assert len(on_day(items, date(2026, 9, 15))) == 12
