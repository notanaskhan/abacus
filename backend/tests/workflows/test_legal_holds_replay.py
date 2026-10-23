"""Q-02-T29 (ADR-090): the legal-hold workflows replay their recorded v1 histories, and a change
to what they schedule is non-determinism. Offline; recorded by
`abacus_tools.workflows.record_legal_holds` with stubs and never re-recorded: a later change goes
behind `workflow.patched(...)` with a v2 recorded beside these."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.evidence.api import LegalHoldApply, LegalHoldInput, LegalHoldRelease

HISTORIES = Path(__file__).resolve().parent / "histories"
APPLY = sorted(HISTORIES.glob("legal-hold-apply-v*.json"))
RELEASE = sorted(HISTORIES.glob("legal-hold-release-v*.json"))


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-legal-hold", path.read_text(encoding="utf-8"))


def test_the_histories_are_committed() -> None:
    assert [p.stem for p in APPLY] == ["legal-hold-apply-v1-active"]
    assert [p.stem for p in RELEASE] == ["legal-hold-release-v1-released"]


def test_each_history_loops_over_two_batches_before_its_last_step() -> None:
    apply = APPLY[0].read_text(encoding="utf-8")
    assert apply.count('"legal_hold.apply_batch"') == 2
    assert apply.rindex("legal_hold.apply_batch") < apply.index("legal_hold.activate")
    release = RELEASE[0].read_text(encoding="utf-8")
    assert release.count('"legal_hold.release_batch"') == 2
    assert release.rindex("legal_hold.release_batch") < release.index("legal_hold.finish_release")


@pytest.mark.parametrize("path", APPLY, ids=[p.stem for p in APPLY])
async def test_apply_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[LegalHoldApply]).replay_workflow(_history(path))


@pytest.mark.parametrize("path", RELEASE, ids=[p.stem for p in RELEASE])
async def test_release_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[LegalHoldRelease]).replay_workflow(_history(path))


@workflow.defn(name="legal_hold_apply")
class _ActivatesFirst:
    """The same workflow skipping the batches: replay must refuse it."""

    @workflow.run
    async def run(self, given: LegalHoldInput) -> str:
        return await workflow.execute_activity(
            "legal_hold.activate",
            given,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=3),
        )


async def test_skipping_the_batches_is_non_determinism() -> None:
    with pytest.raises(workflow.NondeterminismError):
        replayer = Replayer(
            workflows=[_ActivatesFirst], workflow_runner=UnsandboxedWorkflowRunner()
        )
        await replayer.replay_workflow(_history(APPLY[0]))
