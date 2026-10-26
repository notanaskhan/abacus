"""A-01-T19 (A-01 §4.5; ADR-090): the engagement export replays its recorded v1 histories, and a
change to what it schedules is non-determinism. Offline; recorded by
`abacus_tools.workflows.record_engagement_export` with stubs and never re-recorded: a later change
goes behind `workflow.patched(...)` with a v2 recorded beside it."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.evidence.api import EngagementExportInput, EngagementExportWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
EXPORT = sorted(HISTORIES.glob("engagement-export-v*.json"))


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-engagement-export", path.read_text(encoding="utf-8"))


def _named(case: str) -> Path:
    return next(p for p in EXPORT if p.stem == f"engagement-export-v1-{case}")


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in EXPORT] == [
        "engagement-export-v1-integrity-mismatch",
        "engagement-export-v1-ready",
        "engagement-export-v1-undone",
    ]


def test_each_history_waits_out_the_window_before_the_grant() -> None:
    for path in EXPORT:
        recorded = path.read_text(encoding="utf-8")
        assert recorded.count("TIMER_STARTED") == 1
        assert recorded.index("TIMER_FIRED") < recorded.index('"engagement_export.consume_grant"')


def test_an_undone_export_builds_nothing() -> None:
    recorded = _named("undone").read_text(encoding="utf-8")
    assert '"engagement_export.snapshot"' not in recorded
    assert '"engagement_export.package"' not in recorded


def test_a_mismatch_is_marked_failed_and_never_ready() -> None:
    recorded = _named("integrity-mismatch").read_text(encoding="utf-8")
    assert recorded.count('"engagement_export.package"') == 1  # decided: not retried
    assert '"engagement_export.mark_failed"' in recorded
    assert '"engagement_export.mark_ready"' not in recorded


@pytest.mark.parametrize("path", EXPORT, ids=[p.stem for p in EXPORT])
async def test_the_export_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[EngagementExportWorkflow]).replay_workflow(_history(path))


@workflow.defn(name="engagement_export")
class _BuildsAtOnce:
    """The same workflow without the Undo window's timer: replay must refuse it."""

    @workflow.run
    async def run(self, given: EngagementExportInput) -> str:
        return await workflow.execute_activity(
            "engagement_export.consume_grant",
            given,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=3),
        )


async def test_skipping_the_window_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(workflows=[_BuildsAtOnce], workflow_runner=UnsandboxedWorkflowRunner())
        await replayer.replay_workflow(_history(_named("ready")))
