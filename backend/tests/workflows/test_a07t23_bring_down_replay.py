"""A-07-T23 (ADR-090): `BringDown` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_bring_down` with a stub activity)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.bring_down import BringDownWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "bring-down-v1-fired.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_bring_down_replays() -> None:
    history = WorkflowHistory.from_json("bring_down:v1", HISTORY.read_text())
    await Replayer(workflows=[BringDownWorkflow]).replay_workflow(history)
