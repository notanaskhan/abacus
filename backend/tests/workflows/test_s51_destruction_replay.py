"""Q-03-T195 (ADR-090): Q-05-T11's `DestructionAssembleWorkflow` replays its recorded history
(offline; recorded by `abacus_tools.workflows.record_s51_destruction` with a stub)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.evidence.destruction_workflow import DestructionAssembleWorkflow
from abacus_tools.workflows.record_s51_destruction import SWEPT, SWEPT_ID

HISTORIES = Path(__file__).resolve().parent / "histories"


async def test_the_assembly_sweep_replays_its_recorded_history() -> None:
    path = HISTORIES / SWEPT
    history = WorkflowHistory.from_json(SWEPT_ID, path.read_text(encoding="utf-8"))
    await Replayer(workflows=[DestructionAssembleWorkflow]).replay_workflow(history)
