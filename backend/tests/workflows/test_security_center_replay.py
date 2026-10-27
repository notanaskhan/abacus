"""G-02-T17 to T20 (ADR-090): the security center's workflows replay their recorded v1 histories,
and a change to what they schedule is non-determinism. Offline; recorded by
`abacus_tools.workflows.record_security_center` with stubs and never re-recorded: a later change
goes behind `workflow.patched(...)` with a v2 recorded beside it."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.audit_trail.api import AuditExportInput, AuditExportWorkflow
from abacus.modules.evidence.api import FirmExportScheduleWorkflow
from abacus.modules.platform.api import IncidentClockRemindersWorkflow, WispPackWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
CASES: dict[str, type] = {
    "audit-export-v1-ready": AuditExportWorkflow,
    "audit-export-v1-failed": AuditExportWorkflow,
    "incident-reminders-v1-sent": IncidentClockRemindersWorkflow,
    "firm-export-schedule-v1-skipped": FirmExportScheduleWorkflow,
    "wisp-pack-v1-ready": WispPackWorkflow,
    "wisp-pack-v1-failed": WispPackWorkflow,
}


def _history(name: str) -> WorkflowHistory:
    return WorkflowHistory.from_json(name, (HISTORIES / f"{name}.json").read_text("utf-8"))


def test_the_histories_are_committed() -> None:
    assert all((HISTORIES / f"{name}.json").exists() for name in CASES)


def test_a_failed_export_is_marked_failed_and_never_ready() -> None:
    recorded = (HISTORIES / "audit-export-v1-failed.json").read_text("utf-8")
    assert recorded.count('"audit_export.build"') == 1  # decided: not retried
    assert '"audit_export.mark_failed"' in recorded
    assert '"audit_export.mark_ready"' not in recorded


def test_a_ready_export_is_built_then_marked_ready() -> None:
    recorded = (HISTORIES / "audit-export-v1-ready.json").read_text("utf-8")
    assert recorded.index('"audit_export.build"') < recorded.index('"audit_export.mark_ready"')


@pytest.mark.parametrize("name", sorted(CASES))
async def test_each_workflow_replays_its_recorded_history(name: str) -> None:
    await Replayer(workflows=[CASES[name]]).replay_workflow(_history(name))


@workflow.defn(name="audit_export")
class _ReadyWithoutBuilding:
    """The export without its build: replay must refuse it."""

    @workflow.run
    async def run(self, given: AuditExportInput) -> str:
        return await workflow.execute_activity(
            "audit_export.mark_ready",
            given,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=2),
        )


async def test_skipping_the_build_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(
            workflows=[_ReadyWithoutBuilding], workflow_runner=UnsandboxedWorkflowRunner()
        )
        await replayer.replay_workflow(_history("audit-export-v1-ready"))
