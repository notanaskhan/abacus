"""Q-05-T08 (S51 partials, TASK-8733; DEC-5727): the monitoring finding's title states the rate
and tolerance by code, the evaluation notice falls thirty days before the evaluation date, and the
nightly Schedule and both signals are registered."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from abacus.modules.practice import api, quality_dashboard
from abacus.modules.practice.agent_monitoring import evaluation_notice_due, title_of
from abacus.modules.practice.workflows import AGENT_MONITORING_ID, AgentMonitoringWorkflow


def test_ac_the_title_is_the_codes_rate_and_tolerance() -> None:
    title = title_of("ebp_audit_workpapers", Decimal("11.2"), Decimal(8))
    assert title == (
        "Agent monitoring: ebp_audit_workpapers overrides at 11.2% over 30 days, "
        "above the 8% tolerance"
    )


def test_ac_the_evaluation_notice_is_thirty_days_before() -> None:
    assert evaluation_notice_due(date(2026, 11, 15), "12-15")
    assert not evaluation_notice_due(date(2026, 11, 14), "12-15")
    assert evaluation_notice_due(date(2027, 1, 29), "02-29")  # Feb 28 off-leap


def test_ac_the_nightly_schedule_and_signals_are_registered() -> None:
    found = [s for s in api.SCHEDULES if s.id == AGENT_MONITORING_ID]
    assert len(found) == 1 and found[0].workflow is AgentMonitoringWorkflow
    assert AgentMonitoringWorkflow in api.WORKFLOWS
    registered = quality_dashboard._signals  # pyright: ignore[reportPrivateUsage] -- the registry under test
    assert set(registered) == set(quality_dashboard.SIGNALS)
