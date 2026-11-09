"""P-09-T14 (TASK-6534; DEC-3134): the run view lists every human action the dock binds, and its
header carries the plan's version for a plan decision's `expected_version`."""

from __future__ import annotations

import yaml

from abacus.modules.agents.run_views import V2Facts
from abacus.modules.agents.runs import RUN_ACTIONS, RunHeader
from abacus.modules.agents.runs_routes import RunHeaderOut


def test_the_view_lists_every_bound_action() -> None:
    for action in (
        "agent_run.approve_plan",
        "agent_run.answer",
        "agent_run.control",
        "agent_run.sign_off",
        "agent_run.start",
        "agent_feedback.create",
    ):
        assert action in RUN_ACTIONS, action


def test_no_bound_action_is_an_agents() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[4]
    matrix = yaml.safe_load((root / "docs/architecture/permission-matrix/agents.yaml").read_text())
    for action in RUN_ACTIONS:
        if action in ("agent_run.read", "run_trace.export"):
            continue
        row = matrix["actions"][action]
        assert row.get("agent") == "deny", action


def test_the_header_carries_the_plan_version() -> None:
    assert "plan_version" in RunHeaderOut.model_fields
    assert "plan_version" in V2Facts.__dataclass_fields__
    assert "plan_version" in RunHeader.__dataclass_fields__
