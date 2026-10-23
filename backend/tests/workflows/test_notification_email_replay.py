"""P-01-T12 (ADR-090): `NotificationEmail` replays its recorded histories (offline; recorded by
`abacus_tools.workflows.record_notification_email` with stub activities): a sent email, and a
send that fails and is still settled. A later change lands behind `workflow.patched`, so these v1
histories must keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.notifications.api import NotificationEmailWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("notification-email-v*.json"))
IDS = [p.stem for p in ALL]


def test_the_histories_are_committed() -> None:
    assert IDS == ["notification-email-v1-failed", "notification-email-v1-sent"]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(
        "test-notification-email", path.read_text(encoding="utf-8")
    )
    await Replayer(workflows=[NotificationEmailWorkflow]).replay_workflow(history)
