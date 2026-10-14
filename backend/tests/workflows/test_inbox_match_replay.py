"""SPEC-033 AC-3 (TASK-066; ADR-090): the matcher's workflow replays its recorded histories
(offline; recorded by `abacus_tools.workflows.record_inbox_match` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.api import InboxMatchWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("inbox-match-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac3_the_histories_are_committed() -> None:
    assert IDS == ["inbox-match-v1-completed", "inbox-match-v1-skipped"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac3_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-inbox-match", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[InboxMatchWorkflow]).replay_workflow(history)
