"""SPEC-029 AC-2 (TASK-054; ADR-090): the upload processing workflow replays its recorded
history, and a change to what it schedules is detected as non-determinism.

Offline: `Replayer` needs no Temporal server and no codec. The history was recorded by
`abacus_tools.workflows.record_upload_processing` with a stub activity; it is never re-recorded.
TASK-055 and TASK-056 add steps behind `workflow.patched(...)` and must keep it replaying.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.evidence.api import UploadInput, UploadProcessing

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("upload-processing-v*.json"))
IDS = [p.stem for p in ALL]


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-upload-processing", path.read_text(encoding="utf-8"))


def test_ac2_the_histories_are_committed() -> None:
    assert IDS == ["upload-processing-v1-extracted"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac2_the_workflow_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[UploadProcessing]).replay_workflow(_history(path))


@workflow.defn(name="upload_processing")
class _Renamed:
    """The same workflow scheduling a differently named activity: replay must refuse it."""

    @workflow.run
    async def run(self, given: UploadInput) -> str:
        return await workflow.execute_activity(
            "upload.renamed",
            given,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=3),
        )


async def test_ac2_a_changed_activity_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        # Unsandboxed: the test module itself defines the changed workflow.
        replayer = Replayer(workflows=[_Renamed], workflow_runner=UnsandboxedWorkflowRunner())
        await replayer.replay_workflow(_history(ALL[0]))
