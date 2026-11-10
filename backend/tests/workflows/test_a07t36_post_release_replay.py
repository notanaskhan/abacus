"""A-07-T36 (ADR-090): `PostReleaseClocksWorkflow` replays its recorded history (offline; recorded
by `abacus_tools.workflows.record_post_release` with a stub activity)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.api import PostReleaseClocksWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "post-release-v1-stopped.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_post_release_clocks_replay() -> None:
    history = WorkflowHistory.from_json("post_release:v1", HISTORY.read_text())
    await Replayer(workflows=[PostReleaseClocksWorkflow]).replay_workflow(history)
