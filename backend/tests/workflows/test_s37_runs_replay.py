"""S37 (ADR-090): `WorkbenchSessionWorkflow` (P-10-T43) replays its recorded histories (offline;
recorded by `abacus_tools.workflows.record_s37_runs` with stubbed activities)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.api import RunEventsPruneWorkflow
from abacus.modules.workbench.api import WorkbenchSessionWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = [
    "session-v1-read-only.json",
    "session-v1-child-run.json",
    "session-v1-side-queue.json",
    "run-events-prune-v1.json",
]


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_session_workflow_replays(name: str) -> None:
    history = WorkflowHistory.from_json(f"s37:{name}", (HISTORIES / name).read_text())
    workflows = [WorkbenchSessionWorkflow, RunEventsPruneWorkflow]
    await Replayer(workflows=workflows).replay_workflow(history)
