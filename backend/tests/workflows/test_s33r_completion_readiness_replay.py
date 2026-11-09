"""#4231 (ADR-090): `CompletionReadinessWorkflow` replays its recorded history (offline; recorded
by `abacus_tools.workflows.record_completion_readiness` with a stub activity)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.api import CompletionReadinessWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "completion-readiness-v1-checked.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_readiness_run_replays() -> None:
    history = WorkflowHistory.from_json("completion_readiness:v1", HISTORY.read_text())
    await Replayer(workflows=[CompletionReadinessWorkflow]).replay_workflow(history)
