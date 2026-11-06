"""A-06-T25 (ADR-090): the statements workflows replay their recorded histories (offline; from
`abacus_tools.workflows.record_statements` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.reporting.statements_workflows import FsDraftWorkflow, TieOutWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted([*HISTORIES.glob("fs-draft-v*.json"), *HISTORIES.glob("tie-out-v*.json")])
IDS = [p.stem for p in ALL]


def test_ac_the_histories_are_committed() -> None:
    assert IDS == ["fs-draft-v1-drafted", "fs-draft-v1-failed", "tie-out-v1-tied"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(path.stem, path.read_text(encoding="utf-8"))
    replayer = Replayer(workflows=[FsDraftWorkflow, TieOutWorkflow])
    result = await replayer.replay_workflow(history)
    assert result.replay_failure is None
