"""A-08-T12 (ADR-090): `JeScoringWorkflow` replays its recorded histories, the scored run and the
failed one (offline; recorded by `abacus_tools.workflows.record_je_scoring` with stub
activities)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.sampling.api import JeScoringWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
NAMES = ("je-scoring-v1-scored.json", "je-scoring-v1-failed.json")


@pytest.mark.parametrize("name", NAMES)
def test_the_history_is_committed(name: str) -> None:
    assert (HISTORIES / name).exists()


@pytest.mark.parametrize("name", NAMES)
async def test_the_je_scoring_replays(name: str) -> None:
    history = WorkflowHistory.from_json(f"je_scoring:{name}", (HISTORIES / name).read_text())
    await Replayer(workflows=[JeScoringWorkflow]).replay_workflow(history)
