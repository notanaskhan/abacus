"""A-07-T30 (ADR-090): `ReleaseWorkflow` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_release` with stub activities)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.api import ReleaseWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "release-v1-released.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_release_replays() -> None:
    history = WorkflowHistory.from_json("release:v1", HISTORY.read_text())
    await Replayer(workflows=[ReleaseWorkflow]).replay_workflow(history)
