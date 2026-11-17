"""S48 end pass (ADR-090): A-08-T21's flux compute, A-09-T27's instructions send and A-09-T28's
late sweep replay their recorded histories (offline; recorded by
`abacus_tools.workflows.record_s48_jobs` with stubbed activities). A change to any of them lands
behind a `workflow.patched(...)` id, so these v1 histories keep replaying."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.assurance.api import (
    ComponentLateSweep,
    FluxAnalyticsWorkflow,
    InstructionsSendWorkflow,
)

HISTORIES = Path(__file__).resolve().parent / "histories"
RUNS: dict[str, tuple[str, type]] = {
    "flux-analytics-v1-computed": (
        "flux:00000000-0000-4000-8000-0000000000b1:00000000-0000-4000-8000-000000004821:1",
        FluxAnalyticsWorkflow,
    ),
    "component-instructions-send-v1-completed": (
        "component_send:00000000-0000-4000-8000-0000000000b1:00000000-0000-4000-8000-000000004927",
        InstructionsSendWorkflow,
    ),
    "component-late-sweep-v1-swept": ("component_late:platform", ComponentLateSweep),
}


def test_the_histories_are_committed() -> None:
    assert all((HISTORIES / f"{name}.json").exists() for name in RUNS)


@pytest.mark.parametrize("name", sorted(RUNS))
async def test_each_s48_workflow_replays_its_recorded_history(name: str) -> None:
    workflow_id, workflow = RUNS[name]
    history = WorkflowHistory.from_json(
        workflow_id, (HISTORIES / f"{name}.json").read_text(encoding="utf-8")
    )
    await Replayer(workflows=[workflow]).replay_workflow(history)
