"""Q-03-T195 (ADR-090): A-08's confirmation follow-up sweep, the integrations health sweep and
A-09's consolidation pull-all replay their recorded histories (offline; recorded by
`abacus_tools.workflows.record_s45_s48_jobs` with stubs). A change to any of them lands behind a
`workflow.patched(...)` id, so these v1 histories keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.confirmations_follow_up import ConfirmationFollowUpWorkflow
from abacus.modules.assurance.group_pull import ConsolidationPullAll
from abacus.modules.integrations.health_workflow import IntegrationHealthWorkflow
from abacus_tools.workflows.record_s45_s48_jobs import (
    FOLLOW_UP,
    FOLLOW_UP_ID,
    HEALTH,
    HEALTH_ID,
    PULL_ALL,
    PULL_ALL_ID,
)

HISTORIES = Path(__file__).resolve().parent / "histories"
CASES = [
    (FOLLOW_UP, FOLLOW_UP_ID, ConfirmationFollowUpWorkflow),
    (HEALTH, HEALTH_ID, IntegrationHealthWorkflow),
    (PULL_ALL, PULL_ALL_ID, ConsolidationPullAll),
]


@pytest.mark.parametrize(("name", "workflow_id", "workflow"), CASES, ids=[c[0] for c in CASES])
async def test_the_job_replays_its_recorded_history(
    name: str, workflow_id: str, workflow: type
) -> None:
    path = HISTORIES / name
    history = WorkflowHistory.from_json(workflow_id, path.read_text(encoding="utf-8"))
    await Replayer(workflows=[workflow]).replay_workflow(history)
