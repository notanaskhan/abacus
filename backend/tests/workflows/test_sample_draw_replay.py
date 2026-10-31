"""A-03-T10 (ADR-090; A-03 §4.4): the sample draw workflow replays its recorded histories
(offline; recorded by `abacus_tools.workflows.record_sample_draw` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.sampling.api import SampleDrawWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("sample-draw-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac_the_histories_are_committed() -> None:
    assert IDS == ["sample-draw-v1-drafted", "sample-draw-v1-failed"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-sample-draw", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[SampleDrawWorkflow]).replay_workflow(history)
