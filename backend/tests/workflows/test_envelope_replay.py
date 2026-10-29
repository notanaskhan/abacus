"""N-02-T14 (ADR-090): `Envelope` replays its recorded histories (offline; recorded by
`abacus_tools.workflows.record_envelope` with stub activities): a reminder, two provider hints
and the completion; and an expiry. A later change lands behind `workflow.patched`, so these v1
histories must keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.signatures.api import EnvelopeWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("envelope-v*.json"))
IDS = [p.stem for p in ALL]


def test_the_histories_are_committed() -> None:
    assert IDS == ["envelope-v1-completed", "envelope-v1-expired"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-envelope", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[EnvelopeWorkflow]).replay_workflow(history)
