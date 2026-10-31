"""K-01-T21 (TASK-2808; ADR-090): the Methodology importer's workflow replays its recorded
histories (offline; recorded by `abacus_tools.workflows.record_methodology_import` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.methodology_import_workflow import MethodologyImportWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("methodology-import-v*.json"))
IDS = [p.stem for p in ALL]


def test_the_histories_are_committed() -> None:
    assert IDS == [
        "methodology-import-v1-completed",
        "methodology-import-v1-failed",
        "methodology-import-v1-held",
        "methodology-import-v1-stopped",
    ]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(
        "test-methodology-import", path.read_text(encoding="utf-8")
    )
    await Replayer(workflows=[MethodologyImportWorkflow]).replay_workflow(history)
