"""S42 (ADR-090): `MemoDraftWorkflow` (T-05-T54) and the Workbench session's v2 turn (W-02-T15,
`workflow.patched("w02-session-v2")`) replay their recorded histories (offline; recorded by
`abacus_tools.workflows.record_s42_runs` with stubbed activities). The v1 histories (S37) keep
replaying unpatched."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.tax.api import MemoDraftWorkflow
from abacus.modules.workbench.api import WorkbenchSessionWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = [
    "memo-draft-v1-drafted.json",
    "memo-draft-v1-failed.json",
    "workbench-session-v2-read-only.json",
    "workbench-session-v2-child-run.json",
    "workbench-session-v2-side-queue.json",
]


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_s42_workflows_replay(name: str) -> None:
    history = WorkflowHistory.from_json(f"s42:{name}", (HISTORIES / name).read_text())
    workflows = [MemoDraftWorkflow, WorkbenchSessionWorkflow]
    await Replayer(workflows=workflows).replay_workflow(history)
