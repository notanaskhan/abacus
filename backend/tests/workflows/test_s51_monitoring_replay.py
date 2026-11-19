"""Q-03-T195 (ADR-090): Q-05-T08's `AgentMonitoringWorkflow` replays its recorded history
(offline; recorded by `abacus_tools.workflows.record_s51_monitoring` with a stub)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.practice.workflows import AgentMonitoringWorkflow
from abacus_tools.workflows.record_s51_monitoring import SWEPT, SWEPT_ID

HISTORIES = Path(__file__).resolve().parent / "histories"


async def test_the_monitoring_sweep_replays_its_recorded_history() -> None:
    path = HISTORIES / SWEPT
    history = WorkflowHistory.from_json(SWEPT_ID, path.read_text(encoding="utf-8"))
    await Replayer(workflows=[AgentMonitoringWorkflow]).replay_workflow(history)
