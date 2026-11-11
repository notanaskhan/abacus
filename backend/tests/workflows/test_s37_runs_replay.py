"""S37 (ADR-090): `WorkbenchSessionWorkflow` (P-10-T43) replays its recorded histories (offline;
recorded by `abacus_tools.workflows.record_s37_runs` with stubbed activities)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.api import AgentRunInput
from abacus.modules.workbench.session_workflow import WorkbenchSessionWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = [
    "session-v1-read-only.json",
    "session-v1-child-run.json",
    "session-v1-side-queue.json",
]


@workflow.defn(name="AgentRunWorkflow")
class _StubRun:
    @workflow.run
    async def run(self, p: AgentRunInput) -> str:
        return "awaiting_plan_approval"


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_session_workflow_replays(name: str) -> None:
    history = WorkflowHistory.from_json(f"s37:{name}", (HISTORIES / name).read_text())
    await Replayer(workflows=[WorkbenchSessionWorkflow, _StubRun]).replay_workflow(history)
