"""T-08-T12 (TASK-8725; DEC-5719): only a person at manager or above approves a cohort (never an
agent or the system), withdrawal stops once execution starts, cohorts run FIFO, and a re-run row
skips the steps already done."""

from __future__ import annotations

from datetime import UTC, datetime

from abacus.modules.engagements.season_execution import (
    STEPS,
    Approved,
    approval_refusal,
    fifo,
    pending_steps,
    step_key,
    withdraw_refusal,
)

T = datetime(2026, 9, 14, 9, 24, tzinfo=UTC)


def test_ac_human_manager_only_approves() -> None:
    assert approval_refusal("agent", "manager") == "not_a_person"
    assert approval_refusal("system", "engagement_partner") == "not_a_person"
    assert approval_refusal("human", "senior") == "role_below_manager"
    assert approval_refusal("human", "manager") is None


def test_ac_withdraw_before_start_and_fifo() -> None:
    assert withdraw_refusal(None) is None
    assert withdraw_refusal(T) == "already_started"
    later = T.replace(hour=10)
    assert fifo([Approved("c5", later), Approved("c2", T)]) == ["c2", "c5"]


def test_ac_a_rerun_creates_nothing_already_created() -> None:
    done = [step_key("TY2025", "r1", s) for s in STEPS[:3]]
    assert pending_steps("TY2025", "r1", done) == list(STEPS[3:])
    assert pending_steps("TY2025", "r1", [step_key("TY2025", "r1", s) for s in STEPS]) == []
