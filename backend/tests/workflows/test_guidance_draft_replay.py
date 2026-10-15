"""SPEC-035 AC-1 (TASK-073; ADR-090): the guidance drafter's workflow replays its recorded
histories (offline; recorded by `abacus_tools.workflows.record_guidance_draft` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.api import GuidanceDraftWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("guidance-draft-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac3_the_histories_are_committed() -> None:
    assert IDS == [
        "guidance-draft-v1-completed",
        "guidance-draft-v1-skipped",
        "guidance-draft-v2-completed",  # TASK-074: the input names a template item, or not
        "guidance-draft-v2-skipped",
        "guidance-draft-v2-template",
    ]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac3_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-guidance-draft", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[GuidanceDraftWorkflow]).replay_workflow(history)
