"""A-07-T37 (ADR-090): `ArchiveLockWorkflow` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_archive_lock` with stub activities)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.api import ArchiveLockWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "archive-lock-v1-locked.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_archive_lock_replays() -> None:
    history = WorkflowHistory.from_json("archive_lock:v1", HISTORY.read_text())
    await Replayer(workflows=[ArchiveLockWorkflow]).replay_workflow(history)
