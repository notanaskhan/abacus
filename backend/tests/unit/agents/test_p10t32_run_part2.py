"""P-10-T32 (SPEC-647 AC-W4, AC-W5, AC-W6, AC-W10): AgentRunWorkflow part 2's plan rules, pure.

The held branch, the retry as a new row, the redirect merge and stop are `Schedule`'s, which the
workflow replays; the workflow's command order is pinned by the recorded histories
(`tests/workflows/test_p10t32_agent_run_replay.py`)."""

from __future__ import annotations

import pytest

from abacus.modules.agents.run_activities import StepOutcome
from abacus.modules.agents.run_commands import (
    RunNotEnded,
    StepNotFailed,
    _person,  # pyright: ignore[reportPrivateUsage] -- the live-person rule under test
)
from abacus.modules.agents.run_plan import PlanStep, Schedule, aggregate
from abacus.modules.agents.run_waits import QUESTION_KINDS, run_workflow_id


def _s(key: str, level: int, kind: str = "tool", *deps: str) -> PlanStep:
    return PlanStep.parse({"key": key, "level": level, "kind": kind, "depends_on": list(deps)})


def _northwind() -> list[PlanStep]:
    return [
        _s("tb", 0),
        _s("materiality", 1, "decision", "tb"),
        _s("ic", 1, "tool", "tb"),
        _s("sampling", 2, "tool", "materiality"),
        _s("deficiencies", 2, "tool", "ic"),
    ]


def test_acw4_a_decision_holds_only_its_branch() -> None:
    schedule = Schedule(_northwind(), 3)
    assert [s.key for s in schedule.start()] == ["tb"]
    schedule.finish("tb", "succeeded")
    assert {s.key for s in schedule.start()} == {"materiality", "ic"}
    schedule.finish("materiality", "blocked")
    schedule.finish("ic", "succeeded")
    assert [s.key for s in schedule.start()] == ["deficiencies"]
    assert schedule.waiting == ["materiality"]
    schedule.finish("deficiencies", "succeeded")
    assert aggregate(schedule.states.values()) == "blocked_on_decision"
    assert schedule.stalled and not schedule.done
    schedule.finish("materiality", "succeeded")  # Margaret decided at 11:12
    assert [s.key for s in schedule.start()] == ["sampling"]


def test_acw5_a_question_reads_needs_input_and_a_skip_without_default_skips_its_branch() -> None:
    schedule = Schedule(
        [_s("population", 0, "question"), _s("eligibility", 1, "tool", "population")], 3
    )
    schedule.start()
    schedule.finish("population", "waiting_on_inputs")
    assert aggregate(schedule.states.values()) == "needs_input"
    schedule.finish("population", "skipped")
    assert schedule.start() == []
    assert schedule.states["eligibility"] == "skipped"
    assert "question" in QUESTION_KINDS and "approval" in QUESTION_KINDS


def test_acw6_a_retry_queues_the_step_and_what_its_failure_skipped() -> None:
    schedule = Schedule(_northwind(), 3)
    schedule.start()
    schedule.finish("tb", "succeeded")
    schedule.start()
    schedule.finish("ic", "failed")
    schedule.finish("materiality", "succeeded")
    schedule.start()
    assert schedule.states["deficiencies"] == "skipped"
    assert schedule.retry("ic") is True
    assert schedule.states["ic"] == "queued" and schedule.states["deficiencies"] == "queued"
    assert schedule.retry("tb") is False  # only a failed step is retried
    assert "ic" in {s.key for s in schedule.start()}


def test_acw10_a_redirect_cancels_dropped_queued_steps_and_adds_new_ones() -> None:
    schedule = Schedule(_northwind(), 3)
    schedule.start()
    schedule.finish("tb", "succeeded")
    edited = [*_northwind()[:3], _s("sampling_monday", 2, "tool", "materiality")]
    cancelled = schedule.replace(edited)
    assert cancelled == ["sampling", "deficiencies"]
    assert schedule.states["sampling_monday"] == "queued"
    assert schedule.states["tb"] == "succeeded"


def test_stop_cancels_queued_and_held_steps() -> None:
    schedule = Schedule(_northwind(), 3)
    schedule.start()
    schedule.finish("tb", "succeeded")
    schedule.start()
    schedule.finish("materiality", "blocked")
    cancelled = schedule.stop()
    assert set(cancelled) == {"materiality", "sampling", "deficiencies"}
    assert schedule.states["ic"] == "running"  # the workflow cancels what runs


def test_a_held_outcome_carries_its_reference_and_old_outcomes_still_load() -> None:
    assert StepOutcome("succeeded").wait_ref is None
    assert StepOutcome("blocked", wait_ref="c").wait_ref == "c"


def test_the_run_workflow_id_is_part_1s() -> None:
    assert run_workflow_id("t", "r") == "agent_run:t:r"


def test_commands_refuse_anything_but_a_live_person() -> None:
    from types import SimpleNamespace

    for kind in ("agent", "system", "support"):
        ctx = SimpleNamespace(tenant=SimpleNamespace(actor_kind=kind), client=None)
        with pytest.raises(Exception, match="role"):
            _person(ctx, "agent_run.retry")  # type: ignore[arg-type]  # a duck-typed context
    assert RunNotEnded.code == "run_not_ended" and StepNotFailed.code == "step_not_failed"
