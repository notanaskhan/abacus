"""P-10-T29 (ADR-090): `AgentRunWorkflow` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_agent_run_v1` with stub activities)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.api import AgentRunWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "agent-run-v1-succeeded.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_agent_run_replays() -> None:
    history = WorkflowHistory.from_json("agent_run:v1", HISTORY.read_text())
    await Replayer(workflows=[AgentRunWorkflow]).replay_workflow(history)
