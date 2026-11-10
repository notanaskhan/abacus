"""N-04-T07 (ADR-090): `NoticeIntakeWorkflow` replays its recorded histories (offline; recorded by
`abacus_tools.workflows.record_notice_intake` with stubs)."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.notices.intake_workflow import (
    NoticeIntakeRereadWorkflow,
    NoticeIntakeWorkflow,
)

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("notice-intake-v*.json"))
IDS = [p.stem for p in ALL]


def test_ac_the_histories_are_committed() -> None:
    assert IDS == ["notice-intake-v1-already", "notice-intake-v1-read", "notice-intake-v1-refused"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("test-notice-intake", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[NoticeIntakeWorkflow]).replay_workflow(history)


async def test_ac_the_reread_replays_its_recorded_history() -> None:
    path = HISTORIES / "notice-intake-reread-v1.json"
    history = WorkflowHistory.from_json("test-notice-reread", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[NoticeIntakeRereadWorkflow]).replay_workflow(history)
