"""Q-01-T45 (ADR-156, ADR-090): the tenant provisioning workflow replays its recorded history
(offline; recorded by `abacus_tools.workflows.record_tenant_provisioning` with a stub). Every
later step (Q-01-T27's key, entitlements, first admins, G-04's `g04_plan_v2`) lands behind its own
patch, so this v1 history must keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.platform.api import TenantProvisioningWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("tenant-provisioning-v*.json"))
IDS = [p.stem for p in ALL]


def test_the_histories_are_committed() -> None:
    assert IDS == [
        "tenant-provisioning-v1-provisioned",
        "tenant-provisioning-v2-provisioned",  # 0107: entitlements and first admins
    ]


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_workflow_replays_its_recorded_history(path: Path) -> None:
    history = WorkflowHistory.from_json(
        "test-tenant-provisioning", path.read_text(encoding="utf-8")
    )
    await Replayer(workflows=[TenantProvisioningWorkflow]).replay_workflow(history)
