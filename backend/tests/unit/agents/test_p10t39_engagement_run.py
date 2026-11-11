"""P-10-T39 (TASK-6804; SPEC-647 §3.6 AC-E1, AC-E2; DEC-3404): the engagement run's code plan.

Row acceptance: "Northwind's run projects 14 = 1 + 5 + 1 + 4 + 3 workpapers over 5 levels, holds
Planning on the materiality card, and Auto mode cannot be on for a real firm."
"""

from __future__ import annotations

import pytest

from abacus.modules.agents import engagement_run
from abacus.modules.agents.engagement_run import (
    MATERIALITY_KIND,
    missing_handlers,
    plan_from_steps,
    projection,
    register_run_step,
    run_step_handler,
    static_plan,
)
from abacus.modules.agents.run_plan import PlanContext, validate_plan


def test_ac_e1_the_static_list_projects_14_over_5_levels() -> None:
    plan = static_plan()
    assert projection(plan) == [1, 5, 1, 4, 3]
    assert sum(projection(plan)) == 14


def test_ac_e1_planning_holds_on_the_materiality_card() -> None:
    materiality = next(s for s in static_plan() if s.key == "workpapers.materiality")
    assert (materiality.kind, materiality.level) == ("decision", 2)
    assert materiality.arguments["decision_kind"] == MATERIALITY_KIND == "planning_materiality"


def test_the_static_plan_passes_code_validation() -> None:
    context = PlanContext(
        declared_writes=frozenset(), client_scope=frozenset(), approver_holds={}, tool_actions={}
    )
    assert validate_plan(static_plan(), context) == []


def test_ac_e2_methodology_steps_map_onto_run_levels() -> None:
    plan = plan_from_steps(
        [
            ("tb", "foundation", "Trial balance", (), ("BH-EBP-100",)),
            ("mat", "planning", "Planning materiality", ("tb",), ()),
            ("risk", "planning", "Risk assessment", ("tb", "mat"), ()),
            ("elig", "testing", "Eligibility sampling", ("risk",), ()),
            ("contrib", "testing", "Contributions", ("elig",), ()),
            ("wrap", "completion", "Completion memo", ("contrib",), ()),
            ("none", "", "No level", (), ()),
        ]
    )
    assert projection(plan) == [1, 2, 1, 1, 1]
    by_key = {s.key: s for s in plan}
    assert by_key["mat"].kind == "decision"
    assert by_key["risk"].depends_on == ("tb",)  # the same-level "mat" is dropped
    assert by_key["elig"].level == 3  # a sampling step sits on Sampling
    assert by_key["tb"].arguments == {"workpaper_code": "BH-EBP-100"}
    assert "none" not in by_key


def test_ac_e2_an_unregistered_kind_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engagement_run, "_HANDLERS", {})
    assert missing_handlers(static_plan()) == ["workpaper"]


def test_the_built_in_workpaper_step_is_registered() -> None:
    assert run_step_handler("run_step.workpaper") is not None
    assert run_step_handler("ledger.read_tb") is None


def test_register_run_step_refuses_a_bad_or_second_handler() -> None:
    async def other(*_: object) -> object:
        return None

    with pytest.raises(ValueError):
        register_run_step("Bad Kind", other)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        register_run_step("workpaper", other)  # type: ignore[arg-type]
