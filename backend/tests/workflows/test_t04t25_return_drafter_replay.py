"""T-04-T25 (ADR-090): `ReturnDrafterWorkflow` replays its recorded histories (offline; recorded by
`abacus_tools.workflows.record_return_drafter` with a stubbed draft activity)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.tax.drafter_workflow import ReturnDrafterWorkflow
from abacus_tools.workflows.record_return_drafter import SCENARIOS

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = [f"return-drafter-v1-{scenario}.json" for scenario in SCENARIOS]


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_return_drafter_replays(name: str) -> None:
    history = WorkflowHistory.from_json(f"return_drafter:{name}", (HISTORIES / name).read_text())
    await Replayer(workflows=[ReturnDrafterWorkflow]).replay_workflow(history)
