"""T-02-T21 (T-02 §4.11; ADR-090): the K-1 release replays its recorded v1 histories, and a change
to what it schedules is non-determinism. Offline; recorded by
`abacus_tools.workflows.record_k1_release` with stubs and never re-recorded: a later change goes
behind `workflow.patched(...)` with a v2 recorded beside it."""

from __future__ import annotations

from pathlib import Path

import pytest
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer

from abacus.modules.tax.api import K1ReleaseWorkflow

HISTORIES = Path(__file__).resolve().parent / "histories"
RELEASE = sorted(HISTORIES.glob("k1-release-v*.json"))


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-k1-release", path.read_text(encoding="utf-8"))


def _named(case: str) -> str:
    path = next(p for p in RELEASE if p.stem == f"k1-release-v1-{case}")
    return path.read_text(encoding="utf-8")


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in RELEASE] == [
        "k1-release-v1-completed",
        "k1-release-v1-delivery-failed",
        "k1-release-v1-undone",
    ]


def test_each_history_waits_out_the_undo_window_before_the_grant() -> None:
    for path in RELEASE:
        recorded = path.read_text(encoding="utf-8")
        assert recorded.count("TIMER_STARTED") == 1
        assert recorded.index("TIMER_FIRED") < recorded.index('"schedule_k_release.start"')


def test_an_undone_release_delivers_nothing() -> None:
    recorded = _named("undone")
    assert '"schedule_k_release.deliver"' not in recorded
    assert '"schedule_k_release.complete"' not in recorded


def test_a_completed_release_delivers_each_recipient_once() -> None:
    recorded = _named("completed")
    assert recorded.count('"schedule_k_release.deliver"') == 2
    assert '"schedule_k_release.fail"' not in recorded


def test_a_refused_delivery_is_failed_and_never_completed() -> None:
    recorded = _named("delivery-failed")
    assert recorded.count('"schedule_k_release.deliver"') == 2  # decided: not retried
    assert '"schedule_k_release.fail"' in recorded
    assert '"schedule_k_release.complete"' not in recorded


@pytest.mark.parametrize("path", RELEASE, ids=[p.stem for p in RELEASE])
async def test_the_release_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[K1ReleaseWorkflow]).replay_workflow(_history(path))
