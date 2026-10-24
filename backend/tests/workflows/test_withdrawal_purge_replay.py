"""P-06-T19 (ADR-162 §7; ADR-090): the withdrawal purge replays its recorded v1 history, and a
change to what it schedules is non-determinism. Offline; recorded by
`abacus_tools.workflows.record_withdrawal_purge` with a stub and never re-recorded: a later
change goes behind `workflow.patched(...)` with a v2 recorded beside it."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.evidence.api import EvidenceWithdrawalPurge, WithdrawalPurgeInput

HISTORIES = Path(__file__).resolve().parent / "histories"
PURGE = sorted(HISTORIES.glob("withdrawal-purge-v*.json"))


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-withdrawal-purge", path.read_text(encoding="utf-8"))


def test_the_history_is_committed() -> None:
    assert [p.stem for p in PURGE] == ["withdrawal-purge-v1-blocked-then-erased"]


def test_the_history_waits_then_retries_a_blocked_erase() -> None:
    recorded = PURGE[0].read_text(encoding="utf-8")
    assert recorded.count('"evidence_withdrawal.erase"') == 2
    assert recorded.count("TIMER_STARTED") == 2  # the window, then the blocked attempt's day


@pytest.mark.parametrize("path", PURGE, ids=[p.stem for p in PURGE])
async def test_the_purge_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[EvidenceWithdrawalPurge]).replay_workflow(_history(path))


@workflow.defn(name="evidence_withdrawal_purge")
class _ErasesAtOnce:
    """The same workflow without the window's timer: replay must refuse it."""

    @workflow.run
    async def run(self, given: WithdrawalPurgeInput) -> int:
        return await workflow.execute_activity(
            "evidence_withdrawal.erase",
            given,
            result_type=int,
            start_to_close_timeout=timedelta(minutes=3),
        )


async def test_skipping_the_window_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(workflows=[_ErasesAtOnce], workflow_runner=UnsandboxedWorkflowRunner())
        await replayer.replay_workflow(_history(PURGE[0]))
