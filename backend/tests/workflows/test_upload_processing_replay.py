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
    assert IDS == [
        "upload-processing-v1-extracted",
        # v2 (TASK-055): `patched("checks")`; v1 still replays against the same code.
        "upload-processing-v2-extracted",
        # v3 (TASK-056): `patched("previews")`.
        "upload-processing-v3-extracted",
    ]


def test_ac12_v3_previews_after_checking() -> None:
    text = (HISTORIES / "upload-processing-v3-extracted.json").read_text(encoding="utf-8")
    assert text.index("upload.check") < text.index("upload.preview")


def test_ac2_v2_checks_after_extracting() -> None:
    text = (HISTORIES / "upload-processing-v2-extracted.json").read_text(encoding="utf-8")
    assert "upload.check" in text
    assert "EVENT_TYPE_MARKER_RECORDED" in text  # the `patched("checks")` version marker


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
