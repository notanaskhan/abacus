"""P-11-T26 (ADR-090): `FormExtractionWorkflow` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_form_extraction` with a stub)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.evidence.form_extraction_workflow import FormExtractionWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("form-extraction-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac_the_history_is_committed() -> None:
    assert IDS == ["form-extraction-v1-recorded"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-form-extraction", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[FormExtractionWorkflow]).replay_workflow(history)
