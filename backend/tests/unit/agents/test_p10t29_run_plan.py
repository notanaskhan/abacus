"""P-10-T29 (TASK-6607; SPEC-647 AC-W1, AC-W3, AC-W8): the run's plan rules, without Temporal.

Row acceptance: "A 14-step plan over 5 levels runs at most 3 steps at once, a failing branch leaves
the others running, and a plan with a reserved action is refused before approval."
"""

from __future__ import annotations

import pytest

from abacus.modules.agents.run_plan import (
    PlanContext,
    PlanStep,
    Schedule,
    aggregate,
    cap,
    validate_plan,
)

OK = PlanContext(declared_writes=frozenset(), client_scope=frozenset({"northwind"}))


def _fourteen() -> list[PlanStep]:
    """Five levels: 4, 4, 3, 2, 1 steps; each level depends on the first step of the one before,
    except branch b, which hangs off a1 alone."""
    sizes = (4, 4, 3, 2, 1)
    steps: list[PlanStep] = []
    for level, size in enumerate(sizes):
        for n in range(size):
            key = f"l{level}s{n}"
            deps = () if level == 0 else (f"l{level - 1}s0",)
            if level == 1 and n == 3:
                deps = ("l0s1",)  # the independent branch
            steps.append(PlanStep(key, key, level, "tool", "engagements.read", depends_on=deps))
    assert len(steps) == 14
    return steps


def _run(schedule: Schedule, fail: frozenset[str] = frozenset()) -> None:
    while not schedule.done:
        started = schedule.start()
        if not started:
            break
        for step in started:
            schedule.finish(step.key, "failed" if step.key in fail else "succeeded")


def test_ac_w3_a_14_step_plan_never_runs_more_than_3_at_once() -> None:
    schedule = Schedule(_fourteen(), cap(None))
    _run(schedule)
    assert schedule.peak == 3
    assert aggregate(schedule.states.values()) == "succeeded"
    assert cap(8) == 3 and cap(2) == 2 and cap(0) == 3


def test_ac_w3_a_failing_branch_leaves_the_independent_ones_running() -> None:
    schedule = Schedule(_fourteen(), cap(None))
    _run(schedule, fail=frozenset({"l0s0"}))
    assert schedule.states["l0s0"] == "failed"
    assert schedule.states["l1s0"] == "skipped"  # depends on the failure
    assert schedule.states["l4s0"] == "skipped"  # downstream of it
    assert schedule.states["l1s3"] == "succeeded"  # the branch off l0s1 kept running
    assert schedule.states["l0s1"] == schedule.states["l0s3"] == "succeeded"
    assert aggregate(schedule.states.values()) == "failed"


def test_ac_w8_a_pause_dispatches_nothing_new() -> None:
    schedule = Schedule(_fourteen(), cap(None))
    assert schedule.start(paused=True) == []
    assert len(schedule.start()) == 3


@pytest.mark.parametrize(
    "action", ["report.release", "workpaper.sign_off", "agent_run.approve_plan"]
)
def test_ac_w1_a_plan_with_a_reserved_action_is_refused(action: str) -> None:
    step = PlanStep("s1", "Release", 0, "tool", "reporting.release_report")
    problems = validate_plan([step], PlanContext(frozenset(), frozenset(), tool_actions={
        "reporting.release_report": action}))  # fmt: skip
    assert "reserved_action:s1" in problems


def test_ac_w1_undeclared_writes_unheld_approvals_and_out_of_scope_reads_are_refused() -> None:
    write = PlanStep("w", "Save", 0, "approval", writes=("file.save",), approver_user_id="hannah")
    read = PlanStep("r", "Read Granite", 0, "tool", "engagements.read", reads_clients=("granite",))
    problems = validate_plan([write, read], OK)
    assert "undeclared_write:w" in problems
    assert "approver_lacks_action:w" in problems
    assert "read_out_of_scope:r" in problems
    held = PlanContext(
        frozenset({"file.save"}), frozenset({"northwind"}), {("hannah", "file.save"): True}
    )
    assert validate_plan([write], held) == []


def test_ac_w1_cycles_unknown_dependencies_and_level_order_are_refused() -> None:
    a = PlanStep("a", "A", 1, "tool", "engagements.read", depends_on=("b",))
    b = PlanStep("b", "B", 1, "tool", "engagements.read", depends_on=("a",))
    problems = validate_plan([a, b], OK)
    assert "cycle" in problems and "level_order:a" in problems
    assert "unknown_dependency:c" in validate_plan(
        [PlanStep("c", "C", 1, "tool", "engagements.read", depends_on=("zz",))], OK
    )
    assert validate_plan([], OK) == ["empty_plan"]


def test_the_aggregate_rule() -> None:
    assert aggregate(["succeeded", "running"]) == "running"
    assert aggregate(["succeeded", "blocked"]) == "blocked_on_decision"
    assert aggregate(["waiting_on_inputs", "succeeded"]) == "needs_input"
    assert aggregate(["succeeded", "skipped"]) == "succeeded"
    assert aggregate(["cancelled", "cancelled"]) == "cancelled"


def test_a_plan_step_round_trips_through_its_json() -> None:
    step = PlanStep("k", "Label", 2, "compute", "ledger.tie_out", {"expected": "1.00"}, ("j",))
    assert PlanStep.parse(step.dump()) == step
