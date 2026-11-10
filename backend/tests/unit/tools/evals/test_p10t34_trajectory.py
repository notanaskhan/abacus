"""P-10-T34 (SPEC-647 §6): each trajectory grader catches its seeded failing case, the suite passes
in full and in its fast subset, and the taxonomy lists every grader's failure code."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from abacus_tools.evals import trajectory as tr
from abacus_tools.evals.taxonomy import TRAJECTORY_CATEGORIES

REPO = Path(__file__).resolve().parents[5]
CASES = tr.load()


def test_the_suite_passes_in_full_and_fast() -> None:
    full = tr.run_suite(CASES, "full")
    assert full["status"] == "passed", full["reasons"]
    assert full["graders_without_a_seeded_case"] == []
    fast = tr.run_suite(CASES, "fast")
    assert fast["status"] == "passed"
    assert int(str(fast["cases"])) < int(str(full["cases"]))


@pytest.mark.parametrize("grader", sorted(tr.GRADERS))
def test_each_grader_catches_its_seeded_case(grader: str) -> None:
    seeded = [c for c in CASES if grader in c.seeded_failures]
    assert seeded, f"no seeded case for {grader}"
    for case in seeded:
        result = tr.grade_case(case)
        assert result.passed, result.reason
        assert grader in result.failed_graders


def test_the_passing_case_passes_every_grader() -> None:
    case = next(c for c in CASES if c.id == "pass_northwind_materiality")
    assert case.trajectory is not None
    assert all(g.passed for g in tr.grade_trajectory(case.expected, case.trajectory))


def test_a_case_whose_seeded_failure_is_not_caught_fails() -> None:
    case = next(c for c in CASES if c.id == "pass_northwind_materiality")
    wrong = case.model_copy(update={"seeded_failures": ["access_containment"]})
    assert not tr.grade_case(wrong).passed


def test_a_conversation_is_graded_turn_by_turn() -> None:
    case = next(c for c in CASES if c.kind == "conversation")
    assert len(case.trajectories()) == 2
    assert tr.grade_case(case).failed_graders == ("access_containment",)


def test_a_grader_that_raises_fails_its_case() -> None:
    # A malformed case, built past validation (a loaded case is validated; the grader still
    # must not crash the suite on one that is not).
    broken = tr.Expected.model_construct(tool_args={"x.y": {"required": None}})
    seen = tr.Trajectory(calls=[tr.ToolCall(name="x.y")])
    grades = {g.grader: g for g in tr.grade_trajectory(broken, seen)}
    assert grades["args_valid"].passed is False
    assert str(grades["args_valid"].reason).startswith("grader_error")


def test_reserved_actions_follow_the_plan_rule() -> None:
    seen = tr.Trajectory(writes=["materiality.decide"])
    assert not tr.reserved_actions_absent(tr.Expected(), seen).passed
    assert tr.reserved_actions_absent(
        tr.Expected(), tr.Trajectory(writes=["materiality.propose"])
    ).passed


def test_the_taxonomy_lists_every_graders_code() -> None:
    assert set(tr.FAILURE_CODES) == set(tr.GRADERS)
    assert set(tr.FAILURE_CODES.values()) == TRAJECTORY_CATEGORIES
    text = (REPO / "docs" / "product" / "failure-taxonomy.md").read_text()
    section = text.split("## Agent trajectory failures")[1].split("## Changing")[0]
    assert set(re.findall(r"^- `([a-z_]+)`", section, re.M)) == TRAJECTORY_CATEGORIES


def test_a_tool_prompt_change_selects_the_fast_subset() -> None:
    paths = [
        "backend/src/abacus/ai_gateway/prompts/tool.ledger.read_trial_balance/v1.md",
        "backend/src/abacus/modules/agents/run_plan.py",
    ]
    assert tr.changed_tool_prompts(paths) == ["ledger.read_trial_balance"]
