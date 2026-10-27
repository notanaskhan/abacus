"""Q-02-T43 (compliance-kernel §7; ADR-090): the firm export replays its recorded v1 histories, and
a change to what it schedules is non-determinism. Offline; recorded by
`abacus_tools.workflows.record_firm_export` with stubs and never re-recorded: a later change
(Q-02-T47's per-engagement packages) goes behind `workflow.patched(...)` with a v2 beside it."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.evidence.api import FirmExportInput, FirmExportWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
EXPORT = sorted(HISTORIES.glob("firm-export-v*.json"))


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-firm-export", path.read_text(encoding="utf-8"))


def _named(case: str) -> Path:
    return next(p for p in EXPORT if p.stem == f"firm-export-v1-{case}")


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in EXPORT] == ["firm-export-v1-failed", "firm-export-v1-ready"]


def test_a_ready_archive_is_packaged_then_marked_ready() -> None:
    recorded = _named("ready").read_text(encoding="utf-8")
    assert recorded.index('"firm_export.package"') < recorded.index('"firm_export.mark_ready"')
    assert '"firm_export.mark_failed"' not in recorded


def test_a_failed_build_is_marked_failed_and_never_ready() -> None:
    recorded = _named("failed").read_text(encoding="utf-8")
    assert '"firm_export.mark_failed"' in recorded
    assert '"firm_export.mark_ready"' not in recorded


@pytest.mark.parametrize("path", EXPORT, ids=[p.stem for p in EXPORT])
async def test_the_export_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[FirmExportWorkflow]).replay_workflow(_history(path))


@workflow.defn(name="firm_export")
class _ReadyWithoutBuilding:
    """The same workflow marking ready without packaging: replay must refuse it."""

    @workflow.run
    async def run(self, given: FirmExportInput) -> str:
        return await workflow.execute_activity(
            "firm_export.mark_ready",
            given,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=3),
        )


async def test_skipping_the_build_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(
            workflows=[_ReadyWithoutBuilding], workflow_runner=UnsandboxedWorkflowRunner()
        )
        await replayer.replay_workflow(_history(_named("ready")))
