"""SPEC-037 Q4 (TASK-085; ADR-090): the entry assessor's workflow replays its recorded
histories (offline; recorded by `abacus_tools.workflows.record_entry_assess` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.api import EntryAssessWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("entry-assess-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac3_the_histories_are_committed() -> None:
    assert IDS == ["entry-assess-v1-completed", "entry-assess-v1-skipped"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac3_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-entry-assess", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[EntryAssessWorkflow]).replay_workflow(history)
