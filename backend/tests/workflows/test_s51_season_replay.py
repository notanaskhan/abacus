"""Q-03-T195 (ADR-090): T-08-T12's `SeasonSetupExecutionWorkflow` replays its recorded history
(offline; recorded by `abacus_tools.workflows.record_s51_season` with a stub). A change to the
workflow lands behind a `workflow.patched(...)` id, so this v1 history keeps replaying."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.engagements.season_execution_workflow import SeasonSetupExecutionWorkflow
from abacus_tools.workflows.record_s51_season import SEASON, SEASON_ID

HISTORIES = Path(__file__).resolve().parent / "histories"


async def test_the_cohort_execution_replays_its_recorded_history() -> None:
    path = HISTORIES / SEASON
    history = WorkflowHistory.from_json(SEASON_ID, path.read_text(encoding="utf-8"))
    await Replayer(workflows=[SeasonSetupExecutionWorkflow]).replay_workflow(history)
