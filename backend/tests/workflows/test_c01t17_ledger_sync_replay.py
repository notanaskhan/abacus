"""C-01-T17 (ADR-090): `LedgerSyncWorkflow` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_ledger_sync` with stub activities)."""

from __future__ import annotations

from pathlib import Path

from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.connections.ledger_sync_workflow import LedgerSyncWorkflow

HISTORY = Path(__file__).resolve().parent / "histories" / "ledger-sync-v1-ticks.json"


def test_the_history_is_committed() -> None:
    assert HISTORY.exists()


async def test_the_ledger_sync_replays() -> None:
    history = WorkflowHistory.from_json("ledger_sync:v1", HISTORY.read_text())
    await Replayer(workflows=[LedgerSyncWorkflow]).replay_workflow(history)
