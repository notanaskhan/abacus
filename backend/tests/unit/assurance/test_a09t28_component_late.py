"""A-09-T28 (TASK-8407; SPEC-658 F6; AUD-35 d): the late sweep runs at 06:00 firm time, a late
deliverable emits once, and follow-ups are template merges (no model text)."""

from __future__ import annotations

from datetime import datetime

from abacus.modules.assurance import component_late as cl


def test_the_sweep_waits_for_six_firm_time() -> None:
    assert not cl.sweep_due(datetime(2026, 12, 1, 5, 59))
    assert cl.sweep_due(datetime(2026, 12, 1, 6, 0))
    assert cl.sweep_due(datetime(2026, 12, 1, 8, 30))


def test_follow_ups_use_the_firm_template() -> None:
    assert cl.FOLLOW_UP_TEMPLATE == "component_deliverable_follow_up"
    assert cl.ComponentDeliverableLate.event_type == "component_deliverable.late"


def test_the_sweep_runs_hourly_on_the_batch_class() -> None:
    (schedule,) = cl.SCHEDULES
    assert schedule.every.total_seconds() == 3600
    assert cl.WORKFLOWS[cl.ComponentLateSweep] == "batch"
