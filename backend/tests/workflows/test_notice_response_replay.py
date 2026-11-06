"""N-04-T16 (ADR-090): `NoticeResponseWorkflow` replays its recorded history (offline; recorded by
`abacus_tools.workflows.record_notice_response` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.notices.response_workflow import NoticeResponseWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("notice-response-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac_the_history_is_committed() -> None:
    assert IDS == ["notice-response-v1-replied"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-notice-response", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[NoticeResponseWorkflow]).replay_workflow(history)
