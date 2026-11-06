"""P-11-T25 (ADR-090): `LongOcr` and `OcrBackfill` replay their recorded histories (offline; from
`abacus_tools.workflows.record_ocr_long` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.evidence.api import LongOcr, OcrBackfill

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted([*HISTORIES.glob("long-ocr-v*.json"), *HISTORIES.glob("ocr-backfill-v*.json")])
IDS = [p.stem for p in ALL]


def test_ac_the_histories_are_committed() -> None:
    assert IDS == ["long-ocr-v1-read", "ocr-backfill-v1-read"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(path.stem, path.read_text(encoding="utf-8"))
    result = await Replayer(workflows=[LongOcr, OcrBackfill]).replay_workflow(history)
    assert result.replay_failure is None
