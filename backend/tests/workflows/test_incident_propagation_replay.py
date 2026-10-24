"""Q-02-T33 (ADR-090): `IncidentPropagation` replays its recorded v1 and v2 histories, and a change
to what it schedules is non-determinism. Offline; recorded by
`abacus_tools.workflows.record_incident_propagation` with stubs and never re-recorded. v2
(`incident_isolated_v2`, security review S7) isolates each firm and ends with
`platform.finish_incident_propagation`; the v1 history (one firm at a time) keeps replaying."""

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


def test_the_histories_are_committed_with_one_step_per_firm() -> None:
    assert [p.stem for p in RUNS] == [
        "incident-propagation-v1-three-firms",
        "incident-propagation-v2-one-firm-fails",
    ]
    assert RUNS[0].read_text(encoding="utf-8").count('"platform.propagate_incident"') == 3
    v2 = RUNS[1].read_text(encoding="utf-8")
    assert v2.count('"platform.propagate_incident_v2"') == 4
    assert v2.count('"platform.finish_incident_propagation"') == 1
    assert '"EVENT_TYPE_MARKER_RECORDED"' in v2  # the patch marker (its id is encoded)
    assert v2.rindex("platform.propagate_incident_v2") < v2.index(
        "platform.finish_incident_propagation"
    )


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


@workflow.defn(name="IncidentPropagation")
class _StopsAtTheFailedFirm:
    """v2 without isolation: no finishing step after a failed firm. Replay must refuse it."""

    @workflow.run
    async def run(self, given: IncidentPropagationInput) -> None:
        workflow.patched("incident_isolated_v2")
        for tenant_id in given.tenant_ids:
            await workflow.execute_activity(
                "platform.propagate_incident_v2",
                IncidentPropagationStep(
                    given.accrued_ref,
                    tenant_id,
                    given.facts,
                    given.staff_id,
                    given.reason_sha256,
                ),
                start_to_close_timeout=timedelta(seconds=30),
            )


async def test_running_firms_one_after_another_in_v2_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(
            workflows=[_StopsAtTheFailedFirm], workflow_runner=UnsandboxedWorkflowRunner()
        )
        await replayer.replay_workflow(_history(RUNS[1]))
