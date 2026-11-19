"""Q-03-T195 (ADR-090): C-02-T18's `PostingBatchWorkflow` replays its recorded history (offline;
recorded by `abacus_tools.workflows.record_s51_posting` with a stub). A change to the workflow
lands behind a `workflow.patched(...)` id, so this v1 history keeps replaying."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.adjustments.posting_workflow import PostingBatchWorkflow
from abacus_tools.workflows.record_s51_posting import POSTING, POSTING_ID

HISTORIES = Path(__file__).resolve().parent / "histories"


async def test_the_posting_batch_replays_its_recorded_history() -> None:
    path = HISTORIES / POSTING
    history = WorkflowHistory.from_json(POSTING_ID, path.read_text(encoding="utf-8"))
    await Replayer(workflows=[PostingBatchWorkflow]).replay_workflow(history)
