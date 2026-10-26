"""SPEC-030 AC-4 (TASK-059; ADR-090): the upload reviewer's workflow replays its recorded
histories (offline; recorded by `abacus_tools.workflows.record_upload_review` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.api import UploadReviewWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("upload-review-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac4_the_histories_are_committed() -> None:
    assert IDS == [
        "upload-review-v1-completed",
        "upload-review-v1-skipped",
        "upload-review-v2-completed",  # Q-02-T41: the run record is persisted (run_record_v1)
        "upload-review-v2-failed",
    ]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac4_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-upload-review", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[UploadReviewWorkflow]).replay_workflow(history)
