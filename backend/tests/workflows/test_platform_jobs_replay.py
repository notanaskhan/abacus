"""Q-01-T26 (ADR-090): the platform jobs moved off the worker replay their recorded histories
(offline; recorded by `abacus_tools.workflows.record_platform_jobs` with stubs). A change to
either workflow lands behind a `workflow.patched(...)` id, so these v1 histories keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.audit_trail.workflows import (
    AuditChainVerifyWorkflow,
    AuditCheckpointWorkflow,
    AuditPartitionsWorkflow,
)
from abacus.modules.communications.api import DrainSesEventsWorkflow
from abacus.modules.evidence.workflows import AuditAnchorWorkflow
from abacus.modules.identity.api import AccessEndSweepWorkflow
from abacus.modules.notifications.api import NotificationPurgeWorkflow
from abacus.modules.platform.api import SpendAnomalyWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ANOMALY = sorted(HISTORIES.glob("spend-anomaly-v*.json"))
PURGE = sorted(HISTORIES.glob("notification-purge-v*.json"))
DRAIN = sorted(HISTORIES.glob("ses-drain-v*.json"))
ACCESS_END = sorted(HISTORIES.glob("access-end-v*.json"))
# Q-02-T20, T21: the audit trail's jobs and evidence's anchor, by Schedule id.
AUDIT_JOBS: dict[str, tuple[str, type]] = {
    "audit-partitions-v1-ensured": ("audit_partitions:platform", AuditPartitionsWorkflow),
    "audit-checkpoint-v1-sealed": ("audit_checkpoint:platform", AuditCheckpointWorkflow),
    "audit-chain-verify-v1-verified": ("audit_chain_verify:platform", AuditChainVerifyWorkflow),
    "audit-anchor-v1-anchored": ("audit_anchor:platform", AuditAnchorWorkflow),
}


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in ANOMALY] == ["spend-anomaly-v1-flagged"]
    assert [p.stem for p in PURGE] == ["notification-purge-v1-purged"]
    assert [p.stem for p in DRAIN] == ["ses-drain-v1-drained"]
    assert [p.stem for p in ACCESS_END] == ["access-end-v1-swept"]  # G-01-T13
    assert all((HISTORIES / f"{name}.json").exists() for name in AUDIT_JOBS)  # Q-02-T20, T21


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


@pytest.mark.parametrize("path", DRAIN, ids=[p.stem for p in DRAIN])
async def test_the_ses_drain_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("ses_events:platform", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[DrainSesEventsWorkflow]).replay_workflow(history)


@pytest.mark.parametrize("path", ACCESS_END, ids=[p.stem for p in ACCESS_END])
async def test_the_access_end_sweep_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json("access_end:platform", path.read_text(encoding="utf-8"))
    await Replayer(workflows=[AccessEndSweepWorkflow]).replay_workflow(history)


@pytest.mark.parametrize("name", sorted(AUDIT_JOBS))
async def test_the_audit_jobs_replay_their_recorded_histories(name: str) -> None:
    workflow_id, workflow = AUDIT_JOBS[name]
    path = HISTORIES / f"{name}.json"
    history = WorkflowHistory.from_json(workflow_id, path.read_text(encoding="utf-8"))
    await Replayer(workflows=[workflow]).replay_workflow(history)
