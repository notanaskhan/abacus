"""T-05-T31 (TASK-7621; T-05 F2; DEC-4616): the `tax.entity_workbook` plan. Ten steps in six
groups as a DAG the run plan accepts; re-running the capital group runs only the capital and K-1
steps; a model step without §7216 consent waits on inputs; human cells are kept on a re-run."""

from __future__ import annotations

import pytest

from abacus.modules.agents.run_plan import PlanStep
from abacus.modules.tax import entity_run_plan as plan
from abacus.modules.tax.workbook_service import engine_may_write


def _dag_problems(steps: list[PlanStep]) -> list[str]:
    """The run plan's DAG rule: each dependency exists and sits on a lower level."""
    level = {s.key: s.level for s in steps}
    return [
        f"{s.key}->{d}"
        for s in steps
        for d in s.depends_on
        if d not in level or level[d] >= s.level
    ]


def test_ten_steps_in_six_groups() -> None:
    assert len(plan.STEPS) == 10
    assert [g for g in plan.GROUPS] == [
        "import",
        "map",
        "compute",
        "capital",
        "apportionment",
        "k1s",
    ]
    assert {s.group for s in plan.STEPS} == set(plan.GROUPS)


def test_the_full_plan_is_a_valid_dag() -> None:
    steps = plan.plan_steps(plan.selected("all", []), consent=True)
    assert _dag_problems(steps) == []
    assert all(s.tool == f"run_step.{s.key}" for s in steps)


def test_rerunning_the_capital_group_runs_only_capital_and_k1s() -> None:
    keys = [s.key for s in plan.selected("group", ["capital"])]
    assert keys == ["interim_closing_706d", "capital_m2", "federal_k1s", "state_k1s_k3s"]
    steps = plan.plan_steps(plan.selected("group", ["capital"]), consent=True)
    assert _dag_problems(steps) == []
    by_key = {s.key: s for s in steps}
    assert by_key["capital_m2"].depends_on == ("interim_closing_706d",)  # done steps dropped


def test_a_task_runs_with_its_dependants() -> None:
    keys = {s.key for s in plan.selected("task", ["apportionment_ptet"])}
    assert keys == {"apportionment_ptet", "federal_k1s", "state_k1s_k3s"}


@pytest.mark.parametrize(("scope", "keys"), [("group", []), ("group", ["nope"]), ("task", ["x"])])
def test_unknown_keys_are_refused(scope: str, keys: list[str]) -> None:
    with pytest.raises(plan.RunKeysInvalid):
        plan.selected(scope, keys)


def test_without_consent_model_steps_wait_on_inputs() -> None:
    steps = {s.key: s for s in plan.plan_steps(plan.selected("all", []), consent=False)}
    assert steps["map_lines"].kind == "question"
    assert steps["map_lines"].arguments["question_key"] == "consent_7216"
    assert steps["interim_closing_706d"].kind == "question"
    assert steps["import_trial_balance"].kind == "compute"


def test_every_step_keeps_human_cells() -> None:
    steps = plan.plan_steps(plan.selected("all", []), consent=True)
    assert all(s.arguments.get("keep_human") is True for s in steps)
    assert engine_may_write("formula") and engine_may_write(None)
    assert not engine_may_write("human")
