"""Q-02-T33 (ADR-090): `IncidentPropagation` replays its recorded v1 history, and a change to what
it schedules is non-determinism. Offline; recorded by
`abacus_tools.workflows.record_incident_propagation` with a stub and never re-recorded: a later
change goes behind `workflow.patched(...)` with a v2 recorded beside this one."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.platform.api import (
    IncidentPropagationInput,
    IncidentPropagationStep,
    IncidentPropagationWorkflow,
)

HISTORIES = Path(__file__).resolve().parent / "histories"
RUNS = sorted(HISTORIES.glob("incident-propagation-v*.json"))


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-incident-propagation", path.read_text(encoding="utf-8"))


def test_the_history_is_committed_with_one_step_per_firm() -> None:
    assert [p.stem for p in RUNS] == ["incident-propagation-v1-three-firms"]
    assert RUNS[0].read_text(encoding="utf-8").count('"platform.propagate_incident"') == 3


@pytest.mark.parametrize("path", RUNS, ids=[p.stem for p in RUNS])
async def test_propagation_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[IncidentPropagationWorkflow]).replay_workflow(_history(path))


@workflow.defn(name="IncidentPropagation")
class _FirstFirmOnly:
    """The same workflow writing only the first firm: replay must refuse it."""

    @workflow.run
    async def run(self, given: IncidentPropagationInput) -> list[str]:
        ref = await workflow.execute_activity(
            "platform.propagate_incident",
            IncidentPropagationStep(
                given.accrued_ref,
                given.tenant_ids[0],
                given.facts,
                given.staff_id,
                given.reason_sha256,
            ),
            result_type=str,
            start_to_close_timeout=timedelta(seconds=30),
        )
        return [ref]


async def test_dropping_a_firm_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(
            workflows=[_FirstFirmOnly], workflow_runner=UnsandboxedWorkflowRunner()
        )
        await replayer.replay_workflow(_history(RUNS[0]))
