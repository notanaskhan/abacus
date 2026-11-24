"""T-06-T41 (TASK-8910; DEC-5912; ADR-090): "Replay of the pre-change histories passes". The live
run steps are activity bodies the run workflow dispatches by kind (`run_step.<kind>`), so the
workflow's code path is unchanged and every recorded `AgentRunWorkflow` history replays."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.run_workflow import AgentRunWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = sorted(p.name for p in HISTORIES.glob("agent-run-v2-*.json"))


def test_there_are_pre_change_histories() -> None:
    assert len(NAMES) >= 5


@pytest.mark.parametrize("name", NAMES)
async def test_the_pre_change_history_replays(name: str) -> None:
    history = WorkflowHistory.from_json(f"agent_run:{name}", (HISTORIES / name).read_text())
    await Replayer(workflows=[AgentRunWorkflow]).replay_workflow(history)
