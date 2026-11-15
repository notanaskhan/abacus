"""S45 (ADR-090): `InstrumentReaderWorkflow` (T-07-T13) replays its recorded histories (offline;
recorded by `abacus_tools.workflows.record_s45_runs` with stubbed activities)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.tax.api import InstrumentReaderWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = ["instrument-reader-v1-proposed.json", "instrument-reader-v1-refused.json"]


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_instrument_reader_workflow_replays(name: str) -> None:
    history = WorkflowHistory.from_json(f"s45:{name}", (HISTORIES / name).read_text())
    await Replayer(workflows=[InstrumentReaderWorkflow]).replay_workflow(history)
