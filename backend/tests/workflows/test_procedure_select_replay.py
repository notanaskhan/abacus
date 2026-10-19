"""SPEC-037 AC-1 (TASK-077; ADR-090): the procedure selection workflow replays its recorded
histories (offline; recorded by `abacus_tools.workflows.record_procedure_select` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.fieldwork.api import ProcedureSelectWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("procedure-select-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac1_the_histories_are_committed() -> None:
    assert IDS == ["procedure-select-v1-failed", "procedure-select-v1-selected"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac1_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-procedure-select", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[ProcedureSelectWorkflow]).replay_workflow(history)
