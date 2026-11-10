"""A-04-T41 (ADR-090): `SectionDraftWorkflow` replays its recorded history (offline). The plan's
`DecisionRecommendWorkflow` is one call in the proposer's request (DEC-1953), so it has no
history."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.agents.workflows import SectionDraftWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("section-draft-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac_the_history_is_committed() -> None:
    assert IDS == ["section-draft-v1-drafted"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-section-draft", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[SectionDraftWorkflow]).replay_workflow(history)
