"""Q-01-T30 (ADR-090): the canary replays its recorded histories (offline; recorded by
`abacus_tools.workflows.record_canary` with stubs), a pass and a failure at the outbox step. A
change to the workflow lands behind a `workflow.patched(...)` id, so these keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.platform.api import CanaryWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("canary-v*.json"))


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in ALL] == ["canary-v1-failed", "canary-v1-passed"]


@pytest.mark.parametrize("path", ALL, ids=[p.stem for p in ALL])
async def test_the_canary_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("canary", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[CanaryWorkflow]).replay_workflow(history)
