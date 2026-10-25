"""Q-01-T26 (ADR-090): the platform jobs moved off the worker replay their recorded histories
(offline; recorded by `abacus_tools.workflows.record_platform_jobs` with stubs). A change to
either workflow lands behind a `workflow.patched(...)` id, so these v1 histories keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.notifications.api import NotificationPurgeWorkflow
from abacus.modules.platform.api import SpendAnomalyWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ANOMALY = sorted(HISTORIES.glob("spend-anomaly-v*.json"))
PURGE = sorted(HISTORIES.glob("notification-purge-v*.json"))


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in ANOMALY] == ["spend-anomaly-v1-flagged"]
    assert [p.stem for p in PURGE] == ["notification-purge-v1-purged"]


@pytest.mark.parametrize("path", ANOMALY, ids=[p.stem for p in ANOMALY])
async def test_the_spend_anomaly_job_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("spend_anomaly:platform", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[SpendAnomalyWorkflow]).replay_workflow(history)


@pytest.mark.parametrize("path", PURGE, ids=[p.stem for p in PURGE])
async def test_the_notification_purge_job_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(
        "notification_purge:platform", path.read_text(encoding="utf-8")
    )
    await Replayer(workflows=[NotificationPurgeWorkflow]).replay_workflow(history)
