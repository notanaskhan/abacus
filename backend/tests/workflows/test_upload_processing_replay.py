"""SPEC-029 AC-2 (TASK-054; ADR-090): the upload processing workflow replays its recorded
history, and a change to what it schedules is detected as non-determinism.

Offline: `Replayer` needs no Temporal server and no codec. The history was recorded by
`abacus_tools.workflows.record_upload_processing` with a stub activity; it is never re-recorded.
TASK-055 and TASK-056 add steps behind `workflow.patched(...)` and must keep it replaying; so do
P-03-T05's `words` step (v4), P-03-T13's `pii_scan` step (v5), R-01-T09's
`portal_drop_sort` step (v6) and P-03-T15's `masked_preview` step (v7), which replaces the
unmasked preview for new runs.
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
        # Security review: a words step that fails for good never fails the run.
        "upload-processing-v4-words-failed",
        # v4 (P-03-T05): `patched("words")`, the word layer.
        "upload-processing-v4-words",
        # P-03-T13: a PII scan that fails for good never fails the run.
        "upload-processing-v5-pii-scan-failed",
        # v5 (P-03-T13): `patched("pii_scan")`, PII detection over the word layer.
        "upload-processing-v5-pii-scan",
        # v6 (R-01-T09): `patched("portal_drop_sort")`, an inbox file's code-rule sort.
        "upload-processing-v6-portal-drop-sort",
        # P-03-T15: a masked rendition that fails for good never fails the run.
        "upload-processing-v7-masked-preview-failed",
        # v7 (P-03-T15): `patched("masked_preview")`, the masked rendition after the scan.
        "upload-processing-v7-masked-preview",
    ]


def test_review_a_failed_word_layer_leaves_the_run_complete() -> None:
    text = (HISTORIES / "upload-processing-v4-words-failed.json").read_text(encoding="utf-8")
    assert "EVENT_TYPE_ACTIVITY_TASK_FAILED" in text
    assert "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED" in text


def test_p03t05_v4_reads_words_after_previews() -> None:
    text = (HISTORIES / "upload-processing-v4-words.json").read_text(encoding="utf-8")
    assert text.index("upload.preview") < text.index("upload.words")
    assert text.count("EVENT_TYPE_MARKER_RECORDED") == 3  # checks, previews, words


def test_p03t13_v5_scans_for_pii_after_the_word_layer() -> None:
    text = (HISTORIES / "upload-processing-v5-pii-scan.json").read_text(encoding="utf-8")
    assert text.index("upload.words") < text.index("upload.pii_scan")
    assert text.count("EVENT_TYPE_MARKER_RECORDED") == 4  # checks, previews, words, pii_scan
    failed = (HISTORIES / "upload-processing-v5-pii-scan-failed.json").read_text(encoding="utf-8")
    assert "EVENT_TYPE_ACTIVITY_TASK_FAILED" in failed
    assert "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED" in failed


def test_r01t09_v6_sorts_a_drop_last_and_earlier_histories_never_do() -> None:
    text = (HISTORIES / "upload-processing-v6-portal-drop-sort.json").read_text(encoding="utf-8")
    assert text.index("upload.pii_scan") < text.index("upload.portal_drop_sort")
    assert text.count("EVENT_TYPE_MARKER_RECORDED") == 5
    for path in ALL[:7]:  # v1 to v5: every history before v6
        assert "upload.portal_drop_sort" not in path.read_text(encoding="utf-8")


def test_p03t15_v7_masks_after_the_scan_and_never_renders_unmasked() -> None:
    text = (HISTORIES / "upload-processing-v7-masked-preview.json").read_text(encoding="utf-8")
    assert text.index("upload.pii_scan") < text.index("upload.masked_preview")
    assert '"upload.preview"' not in text  # no unmasked rendition is ever made
    # checks, previews, masked_preview, words, pii_scan, portal_drop_sort
    assert text.count("EVENT_TYPE_MARKER_RECORDED") == 6
    failed = (HISTORIES / "upload-processing-v7-masked-preview-failed.json").read_text(
        encoding="utf-8"
    )
    assert "EVENT_TYPE_ACTIVITY_TASK_FAILED" in failed
    assert "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED" in failed


def test_p03t15_v1_to_v6_never_mask_and_still_preview() -> None:
    for path in ALL[:8]:
        text = path.read_text(encoding="utf-8")
        assert "upload.masked_preview" not in text
        if path.stem >= "upload-processing-v3":
            assert '"upload.preview"' in text


def test_p03t13_v1_to_v4_never_scan_for_pii() -> None:
    for path in ALL[:5]:
        assert "upload.pii_scan" not in path.read_text(encoding="utf-8")


def test_p03t05_v1_to_v3_never_read_words() -> None:
    for path in ALL[:3]:
        assert "upload.words" not in path.read_text(encoding="utf-8")


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
