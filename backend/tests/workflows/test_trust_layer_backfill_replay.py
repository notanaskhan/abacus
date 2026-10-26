"""P-03-T05 (ADR-090): the trust layer backfill replays its recorded history, and a change to
what it schedules is detected as non-determinism.

Offline: `Replayer` needs no Temporal server. The history was recorded by
`abacus_tools.workflows.record_trust_layer_backfill` with stub activities; it is never
re-recorded. A later change goes behind `workflow.patched(...)` and adds `v2`.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.evidence.api import BackfillInput, TrustLayerBackfill

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("trust-layer-backfill-v*.json"))
IDS = [p.stem for p in ALL]


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-trust-layer-backfill", path.read_text(encoding="utf-8"))


def test_p03t05_the_histories_are_committed() -> None:
    assert IDS == [
        "trust-layer-backfill-v1-done",
        # Security review: an upload whose step fails for good is passed, never a wedge.
        "trust-layer-backfill-v1-skipped",
        # v2 (P-03-T15): `patched("masks")`, words, PII scan and masked rendition per upload.
        "trust-layer-backfill-v2-done",
    ]


def test_p03t15_v2_masks_every_pending_upload_after_its_scan() -> None:
    text = (HISTORIES / "trust-layer-backfill-v2-done.json").read_text(encoding="utf-8")
    assert "trust_layer.pending_masks" in text and "trust_layer.pending_words" not in text
    assert text.count('"upload.masked_preview"') == 2
    assert text.index('"upload.pii_scan"') < text.index('"upload.masked_preview"')
    for path in ALL[:2]:
        assert "upload.masked_preview" not in path.read_text(encoding="utf-8")


def test_review_a_failing_upload_is_passed_and_the_rest_still_get_layers() -> None:
    text = (HISTORIES / "trust-layer-backfill-v1-skipped.json").read_text(encoding="utf-8")
    assert "EVENT_TYPE_ACTIVITY_TASK_FAILED" in text
    assert text.count('"upload.words"') == 2  # the failing version, then the inbox file
    assert "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED" in text
    assert "EVENT_TYPE_WORKFLOW_EXECUTION_FAILED" not in text


def test_p03t05_each_pending_upload_gets_its_word_layer() -> None:
    text = (HISTORIES / "trust-layer-backfill-v1-done.json").read_text(encoding="utf-8")
    assert text.count('"upload.words"') == 2
    assert text.index("trust_layer.pending_words") < text.index("upload.words")


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_p03t05_the_workflow_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[TrustLayerBackfill]).replay_workflow(_history(path))


@workflow.defn(name="trust_layer_backfill")
class _Renamed:
    """The same workflow scheduling a differently named activity: replay must refuse it."""

    @workflow.run
    async def run(self, given: BackfillInput) -> int:
        return await workflow.execute_activity(
            "trust_layer.renamed",
            given,
            result_type=int,
            start_to_close_timeout=timedelta(minutes=3),
        )


async def test_p03t05_a_changed_activity_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(workflows=[_Renamed], workflow_runner=UnsandboxedWorkflowRunner())
        await replayer.replay_workflow(_history(ALL[0]))
