"""SPEC-034 AC-3, AC-4 (TASK-069; ADR-090): the general ledger import workflow replays its
recorded histories (offline; recorded by `abacus_tools.workflows.record_gl_import`)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.connections.api import GlImportWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("gl-import-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac3_the_histories_are_committed() -> None:
    assert IDS == ["gl-import-v1-reconciled", "gl-import-v1-waiting"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac3_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-gl-import", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[GlImportWorkflow]).replay_workflow(history)
