"""P-10-T32 (ADR-090): `AgentRunWorkflow` replays its recorded histories (offline; recorded by
`abacus_tools.workflows.record_agent_run` with stub activities)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.run_workflow import AgentRunWorkflow
from abacus_tools.workflows.record_agent_run import PLANS

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = [f"agent-run-v2-{scenario}.json" for scenario in PLANS]


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_agent_run_replays(name: str) -> None:
    history = WorkflowHistory.from_json(f"agent_run:{name}", (HISTORIES / name).read_text())
    await Replayer(workflows=[AgentRunWorkflow]).replay_workflow(history)
