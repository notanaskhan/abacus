"""N-01-T14 (ADR-090): `IntakeWithdrawalPurge` replays its recorded histories (offline; recorded
by `abacus_tools.workflows.record_intake_purge` with a stub activity): erased at once, and held
once before the erase."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.communications.api import IntakeWithdrawalPurgeWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("intake-purge-v*.json"))
IDS = [p.stem for p in ALL]


def test_the_histories_are_committed() -> None:
    assert IDS == ["intake-purge-v1-erased", "intake-purge-v1-held"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-intake-purge", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[IntakeWithdrawalPurgeWorkflow]).replay_workflow(history)
