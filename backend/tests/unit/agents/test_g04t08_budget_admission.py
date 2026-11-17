"""G-04-T08 (red): the over-limit admission rule (SPEC-680 AC-37; DEC-5420)."""

from __future__ import annotations

import pytest

from abacus.modules.agents.budget_admission import BUDGET_100PCT, refusal

STARTS = (
    "manual", "session", "agent_trigger", "engagement_trigger", "agent_column", "event_policy",
    "retry", "test",
)  # fmt: skip


def test_ac37_a_scheduled_run_at_20860_of_20000_is_refused_with_budget_100pct() -> None:
    assert refusal("schedule", pause_scheduled=True, at_or_over=True) == BUDGET_100PCT


@pytest.mark.parametrize("trigger", STARTS)
def test_ac37_every_other_trigger_starts(trigger: str) -> None:
    assert refusal(trigger, pause_scheduled=True, at_or_over=True) is None


def test_keep_running_or_under_the_limit_refuses_nothing() -> None:
    assert refusal("schedule", pause_scheduled=False, at_or_over=True) is None
    assert refusal("schedule", pause_scheduled=True, at_or_over=False) is None
