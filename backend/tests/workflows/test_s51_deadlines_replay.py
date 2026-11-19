"""Q-03-T195 (ADR-090): T-08-T10's `FilingDeadlineRecomputeWorkflow` replays its recorded history
(offline; recorded by `abacus_tools.workflows.record_s51_deadlines` with a stub)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.practice.workflows import FilingDeadlineRecomputeWorkflow
from abacus_tools.workflows.record_s51_deadlines import SWEPT, SWEPT_ID

HISTORIES = Path(__file__).resolve().parent / "histories"


async def test_the_deadline_recompute_replays_its_recorded_history() -> None:
    path = HISTORIES / SWEPT
    history = WorkflowHistory.from_json(SWEPT_ID, path.read_text(encoding="utf-8"))
    await Replayer(workflows=[FilingDeadlineRecomputeWorkflow]).replay_workflow(history)
