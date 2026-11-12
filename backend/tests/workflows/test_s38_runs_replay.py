"""S38 (ADR-090): `AnalystModeWorkflow` (T-04-T38) replays its recorded histories (offline;
recorded by `abacus_tools.workflows.record_s38_runs` with stubbed activities)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.tax.api import AnalystModeWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = ["analyst-mode-v1-proposed.json", "analyst-mode-v1-refused.json"]


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_analyst_mode_workflow_replays(name: str) -> None:
    history = WorkflowHistory.from_json(f"s38:{name}", (HISTORIES / name).read_text())
    await Replayer(workflows=[AnalystModeWorkflow]).replay_workflow(history)
