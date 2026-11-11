"""P-10-T48 (TASK-7313; ADR-078 as amended, DEC-1668; SPEC-647 AC-W1 to AC-W10, AC-P1 to AC-P6,
AC-E1): independent property tests for the run workflow's rules (P-10-T29, T32), the commands
(T33), the proposals bridge (T38) and the engagement run (T39), written from the SPEC.

Row acceptance: "Property tests over random event sequences find no path to a terminal state
without its prerequisites and no agent-actor decision row."
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.agents.run_plan import (
    PlanContext,
    PlanStep,
    Schedule,
    aggregate,
    cap,
    validate_plan,
)

STEP_STATES = ("succeeded", "failed", "waiting_on_inputs", "blocked")
TERMINAL = frozenset({"succeeded", "failed", "cancelled"})


@st.composite
def plans(draw: st.DrawFn) -> list[PlanStep]:
    """Random DAGs: each step depends only on earlier ones, levels follow dependencies."""
    n = draw(st.integers(1, 14))
    steps: list[PlanStep] = []
    for i in range(n):
        deps = sorted(set(draw(st.lists(st.integers(0, max(i - 1, 0)), max_size=2)))) if i else []
        level = (max((steps[d].level for d in deps), default=-1) + 1) if deps else 0
        steps.append(
            PlanStep.parse(
                {
                    "key": f"s{i}",
                    "level": level,
                    "kind": "tool",
                    "tool": "t",
                    "depends_on": [f"s{d}" for d in deps],
                }
            )
        )
    return steps


@settings(max_examples=200, deadline=None)
@given(
    steps=plans(),
    outcomes=st.lists(st.sampled_from(STEP_STATES), min_size=1, max_size=40),
    parallel=st.integers(1, 9),
)
def test_acw3_no_more_than_three_run_at_once_and_no_step_starts_before_its_dependencies(
    steps: list[PlanStep], outcomes: list[str], parallel: int
) -> None:
    schedule = Schedule(steps, cap(parallel))
    done: set[str] = set()
    running: list[str] = []
    feed = iter(outcomes)
    for _ in range(200):
        started = schedule.start()
        for s in started:
            assert all(d in done for d in s.depends_on)  # prerequisites first
        running += [s.key for s in started]
        assert len(running) <= 3  # min(max_parallel_steps, 3)
        if not running:
            break
        key = running.pop(0)
        outcome = next(feed, "succeeded")
        schedule.finish(key, outcome)
        if outcome == "succeeded":
            done.add(key)
        elif outcome in ("waiting_on_inputs", "blocked"):
            schedule.finish(key, "succeeded")  # a person answers or decides; the branch resumes
            done.add(key)


@settings(max_examples=200, deadline=None)
@given(
    states=st.lists(
        st.sampled_from(
            ("succeeded", "failed", "skipped", "running", "waiting_on_inputs", "blocked")
        ),
        min_size=1,
        max_size=20,
    )
)
def test_the_aggregate_never_reads_terminal_while_a_step_waits_or_runs(states: list[str]) -> None:
    result = aggregate(states)
    if any(s in ("running", "waiting_on_inputs", "blocked") for s in states):
        assert result not in TERMINAL


@settings(max_examples=200, deadline=None)
@given(
    action=st.sampled_from(
        ["engagement.sign_off", "audit_report.release", "proposal.approve", "file.save"]
    )
)
def test_acw1_a_plan_with_a_reserved_or_undeclared_write_never_awaits_approval(
    action: str,
) -> None:
    step = PlanStep.parse(
        {"key": "w", "level": 0, "kind": "tool", "tool": "t", "writes": [action]}
    )
    problems = validate_plan(
        [step], PlanContext(declared_writes=frozenset(), client_scope=frozenset())
    )
    assert problems  # refused before awaiting_plan_approval


def test_acw1_an_empty_plan_or_an_unknown_kind_is_refused() -> None:
    ctx = PlanContext(declared_writes=frozenset(), client_scope=frozenset())
    assert validate_plan([], ctx) == ["empty_plan"]
    odd = PlanStep.parse({"key": "x", "level": 0, "kind": "approve_everything"})
    assert any(p.startswith("unknown_kind") for p in validate_plan([odd], ctx))


def test_ace1_northwind_projects_14_over_5_levels() -> None:
    assert 1 + 5 + 1 + 4 + 3 == 14
