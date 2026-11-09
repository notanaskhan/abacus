"""P-09-T07 (TASK-6304; SPEC-648; P-09 Story 1.1; DEC-57, DEC-3004): the run projection by level,
computed by code from the plan's steps and their latest step states, and the v2 item mapping.

Row acceptance (projection half): "Seeded #4127 at 9:41 returns 1/0/0/0/0 done of 1/5/1/4/3 with
1 blocked and 1 running."
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from abacus.modules.agents.run_recorder import (
    RecordedItem,
    RecordedRun,
    RecordedStep,
    _check,  # pyright: ignore[reportPrivateUsage] -- the rule under test
)
from abacus.modules.agents.run_views import (
    BUCKET,
    ITEM_KINDS,
    LevelCount,
    PlanStep,
    item_of,
    plan_steps,
    project_levels,
)

# Run #4127 at 9:41 (P-09 Story 1.1, Story 4.2): Foundation 1, Planning 5, Sampling 1, Testing 4,
# Completion 3 = 14 workpapers. Trial balance succeeded; materiality blocked on a partner;
# risk assessment running; general planning waiting on inputs; SOC 1 queued with no step row.
PLAN_4127 = [
    PlanStep("trial_balance", 1),
    PlanStep("materiality", 2),
    PlanStep("risk_assessment", 2),
    PlanStep("general_planning", 2),
    PlanStep("service_organizations", 2),
    PlanStep("planning_analytics", 2),
    PlanStep("sampling", 3),
    *(PlanStep(f"testing_{n}", 4) for n in range(4)),
    *(PlanStep(f"completion_{n}", 5) for n in range(3)),
]
LATEST_4127 = {
    "trial_balance": "succeeded",
    "materiality": "blocked",
    "risk_assessment": "running",
    "general_planning": "waiting_on_inputs",
}


def test_ac_4127_at_9_41_projects_1_0_0_0_0_done_of_1_5_1_4_3() -> None:
    levels = project_levels(PLAN_4127, LATEST_4127)
    assert [lv.total for lv in levels] == [1, 5, 1, 4, 3]
    assert [lv.done for lv in levels] == [1, 0, 0, 0, 0]
    planning = levels[1]
    assert (planning.blocked, planning.running, planning.waiting, planning.queued) == (1, 1, 1, 2)
    assert sum(lv.total for lv in levels) == 14


def test_every_level_s_counts_sum_to_its_total() -> None:
    for lv in project_levels(PLAN_4127, LATEST_4127):
        assert lv.done + lv.running + lv.blocked + lv.waiting + lv.queued + lv.failed == lv.total


def test_a_step_with_no_row_is_queued_and_has_no_tool_card() -> None:
    assert project_levels([PlanStep("soc1", 2)], {}) == [LevelCount(2, 1, queued=1)]


@pytest.mark.parametrize(
    ("state", "bucket"),
    [
        ("succeeded", "done"),
        ("skipped", "done"),
        ("running", "running"),
        ("dispatched", "running"),
        ("blocked", "blocked"),
        ("waiting_on_inputs", "waiting"),
        ("queued", "queued"),
        ("failed", "failed"),
        ("cancelled", "failed"),
    ],
)
def test_every_step_state_has_one_bucket(state: str, bucket: str) -> None:
    assert BUCKET[state] == bucket


def test_a_plan_without_levels_is_one_level() -> None:
    assert project_levels([PlanStep("a", 0), PlanStep("b", 0)], {"a": "succeeded"}) == [
        LevelCount(1, 2, done=1, queued=1)
    ]


def test_plan_steps_read_the_stored_json_and_skip_what_is_not_a_step() -> None:
    raw = [{"key": "tb", "label": "TB", "level": 1}, {"label": "no key"}, "x", {"key": 3}]
    assert plan_steps(raw) == [PlanStep("tb", 1)]
    assert plan_steps({"not": "a list"}) == []


def test_an_unknown_item_kind_is_skipped() -> None:
    at = datetime(2026, 9, 14, 14, 41, tzinfo=UTC)
    assert item_of(1, {"kind": "shell", "code": "x"}, at) is None
    found = item_of(2, {"kind": "tool", "code": "workpapers.tb", "outcome": "succeeded"}, at)
    assert found is not None and (found.kind, found.code, found.outcome) == (
        "tool", "workpapers.tb", "succeeded",
    )  # fmt: skip


def test_the_item_kinds_are_the_c6_v2_wire_set() -> None:
    assert {
        "user", "line", "block", "tool", "progress", "question", "answer", "error", "plan",
        "approval", "decision_ref", "artifact", "run_card", "notice",
    } == ITEM_KINDS  # fmt: skip


def test_the_recorder_refuses_unknown_states_kinds_and_duplicate_keys() -> None:
    import uuid

    base = RecordedRun("audit.planning", uuid.uuid4(), uuid.uuid4(), 4127, "running", steps=[])
    at = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
    with pytest.raises(ValueError, match="state"):
        _check(dataclasses.replace(base, steps=[RecordedStep("a", 1, "A", "done")]))
    with pytest.raises(ValueError, match="once"):
        _check(
            dataclasses.replace(
                base,
                steps=[RecordedStep("a", 1, "A", "running"), RecordedStep("a", 1, "A", "running")],
            )
        )
    with pytest.raises(ValueError, match="kind"):
        _check(dataclasses.replace(base, items=[RecordedItem("thought", "x", at)]))
