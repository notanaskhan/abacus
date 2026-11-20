"""S52 end pass (ADR-090): the three workflows S52 added replay their recorded histories
(offline; recorded by `abacus_tools.workflows.record_s52_package` and `record_s52_runs` with stub
activities): C-02-T28's package assembly, Q-05-T15's destruction and T-08-T14's standards run."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.closes.api import PackageAssemblyWorkflow
from abacus.modules.evidence.api import DestructionExecuteWorkflow
from abacus.modules.tax.api import StandardsRunWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
CASES: list[tuple[str, type]] = [
    ("package-assembly-v1-finished.json", PackageAssemblyWorkflow),
    ("destruction-execute-v1-certified.json", DestructionExecuteWorkflow),
    ("standards-run-v1-two-items.json", StandardsRunWorkflow),
]


@pytest.mark.parametrize(("name", "_kind"), CASES)
def test_the_history_is_committed(name: str, _kind: type) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize(("name", "kind"), CASES)
async def test_the_workflow_replays(name: str, kind: type) -> None:
    history = WorkflowHistory.from_json(name, (HISTORIES / name).read_text())
    await Replayer(workflows=[kind]).replay_workflow(history)
