"""Q-02-T41 (TASK-1287; ADR-169 §3, ADR-090): every patched specialist workflow replays the
histories recorded since `run_record_v1` (`abacus_tools.workflows.record_run_records`), each of
which persists the run record after the terminal state and before the slot is released; and a
workflow without the persist step no longer replays them (the patch is what keeps old and new
histories apart)."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.exceptions import ActivityError
from temporalio.worker import Replayer
from temporalio.workflow import NondeterminismError

from abacus.modules.agents.api import (
    EntryAssessWorkflow,
    GuidanceDraftWorkflow,
    InboxMatchWorkflow,
    ScreeningWorkflow,
    UploadReviewWorkflow,
)
from abacus.modules.agents.workflow_types import (
    FailInput,
    RunInput,
    ScreeningInput,
    ScreeningOutcome,
    SlotGrant,
)

HISTORIES = Path(__file__).resolve().parent / "histories"
PERSIST, FAIL, RELEASE = (
    "agents.persist_run_record",
    "screening.fail_run",
    "screening.release_slot",
)
WORKFLOWS: dict[str, tuple[str, type, str]] = {
    "screening": ("v3", ScreeningWorkflow, "screening.screen"),
    "upload-review": ("v2", UploadReviewWorkflow, "upload_review.review"),
    "inbox-match": ("v2", InboxMatchWorkflow, "inbox_match.match"),
    "guidance-draft": ("v3", GuidanceDraftWorkflow, "guidance_draft.draft"),
    "entry-assess": ("v2", EntryAssessWorkflow, "entry_assess.assess"),
}
CASES = [(name, case) for name in WORKFLOWS for case in ("completed", "failed")]
IDS = [f"{name}-{case}" for name, case in CASES]
Json = dict[str, object]


def _path(name: str, case: str) -> Path:
    return HISTORIES / f"{name}-{WORKFLOWS[name][0]}-{case}.json"


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-run-record-replay", path.read_text(encoding="utf-8"))


def _scheduled(path: Path) -> list[str]:
    events = cast(list[Json], cast(Json, json.loads(path.read_text(encoding="utf-8")))["events"])
    return [
        cast(
            str,
            cast(Json, cast(Json, e["activityTaskScheduledEventAttributes"])["activityType"])[
                "name"
            ],
        )
        for e in events
        if e["eventType"] == "EVENT_TYPE_ACTIVITY_TASK_SCHEDULED"
    ]


@pytest.mark.parametrize(("name", "case"), CASES, ids=IDS)
async def test_ac44_every_patched_workflow_replays_its_run_record_history(
    name: str, case: str
) -> None:
    await Replayer(workflows=[WORKFLOWS[name][1]]).replay_workflow(_history(_path(name, case)))


@pytest.mark.parametrize(("name", "case"), CASES, ids=IDS)
def test_ac44_the_record_is_persisted_after_the_terminal_state_before_the_release(
    name: str, case: str
) -> None:
    work = WORKFLOWS[name][2]
    ended = [work] if case == "completed" else [work, FAIL]
    assert _scheduled(_path(name, case))[-(len(ended) + 2) :] == [*ended, PERSIST, RELEASE]


_TIMEOUT = timedelta(minutes=2)


@workflow.defn(name="screening", sandboxed=False)
class WithoutPersist:
    """The v2 sequence (no run record): it must not replay a v3 history."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            "screening.create_run", input, result_type=str, start_to_close_timeout=_TIMEOUT
        )
        run = RunInput(input.tenant_id, run_id)
        workflow.patched("work-slots")
        await workflow.execute_activity(
            "screening.acquire_slot", run, result_type=SlotGrant, start_to_close_timeout=_TIMEOUT
        )
        workflow.patched("admission")
        try:
            return await workflow.execute_activity(
                "screening.screen",
                run,
                result_type=ScreeningOutcome,
                start_to_close_timeout=_TIMEOUT,
            )
        except ActivityError:
            return await workflow.execute_activity(
                FAIL,
                FailInput(run.tenant_id, run.run_id, "provider_unavailable"),
                result_type=ScreeningOutcome,
                start_to_close_timeout=_TIMEOUT,
            )
        finally:
            await workflow.execute_activity(RELEASE, run, start_to_close_timeout=_TIMEOUT)


async def test_ac44_a_workflow_without_the_persist_step_does_not_replay_a_v3_history() -> None:
    with pytest.raises(NondeterminismError):
        await Replayer(workflows=[WithoutPersist]).replay_workflow(
            _history(_path("screening", "completed")), raise_on_replay_failure=True
        )
