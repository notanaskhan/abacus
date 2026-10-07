"""SPEC-003 AC-6, AC-13, AC-14: replay of the slot-waiting workflows (TASK-018 interface contract
018b, "Workflows", and contract revision 1; ADR-017, ADR-090).

Every `retrieval-v2-*` and `screening-v2-*` history replays against the current workflow, and the
v1 histories (recorded before the work slots) still replay too: the slot steps sit behind
`workflow.patched("work-slots")`. The v2 set covers a plain run, a failure, a run queued over
several asks and timers, a `capacity_timeout`, and a cancel while queued. Offline: `Replayer` needs
no server and no codec. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.common import RetryPolicy
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.kernel.crypto.payload_codec import ENCODING
from abacus.modules.agents.api import ScreeningWorkflow
from abacus.modules.agents.workflow_types import RunInput, ScreeningInput, ScreeningOutcome
from abacus.modules.connections.api import RetrievalInput, RetrievalOutcome, RetrievalWorkflow
from abacus_tools.synthetic import generate

HISTORIES = Path(__file__).resolve().parent / "histories"
Json = dict[str, object]
RETRIEVAL_V2 = sorted(HISTORIES.glob("retrieval-v2-*.json"))
SCREENING_V2 = sorted(HISTORIES.glob("screening-v2-*.json"))
RETRIEVAL_V1 = sorted(HISTORIES.glob("retrieval-v1-*.json"))
SCREENING_V1 = sorted(HISTORIES.glob("screening-v1-*.json"))
ALL_V2 = [*RETRIEVAL_V2, *SCREENING_V2]
_TIMEOUT = timedelta(minutes=5)
_RETRY = RetryPolicy(maximum_attempts=6)


def _ids(paths: list[Path]) -> list[str]:
    return [p.stem for p in paths]


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-slots-replay", path.read_text(encoding="utf-8"))


def _replayer(*workflows: type, sandboxed: bool = True) -> Replayer:
    if sandboxed:
        return Replayer(workflows=list(workflows))
    return Replayer(workflows=list(workflows), workflow_runner=UnsandboxedWorkflowRunner())


def _events(path: Path) -> list[Json]:
    return cast(list[Json], cast(Json, json.loads(path.read_text(encoding="utf-8")))["events"])


def _scheduled(path: Path) -> list[str]:
    return [
        cast(
            str,
            cast(Json, cast(Json, e["activityTaskScheduledEventAttributes"])["activityType"])[
                "name"
            ],
        ).split(".")[1]
        for e in _events(path)
        if e["eventType"] == "EVENT_TYPE_ACTIVITY_TASK_SCHEDULED"
    ]


def _timers(path: Path) -> list[float]:
    return [
        float(str(cast(Json, e["timerStartedEventAttributes"])["startToFireTimeout"]).rstrip("s"))
        for e in _events(path)
        if e["eventType"] == "EVENT_TYPE_TIMER_STARTED"
    ]


def _last(path: Path) -> str:
    return cast(str, _events(path)[-1]["eventType"])


def _walk(node: object) -> Iterator[object]:
    yield node
    if isinstance(node, dict):
        for value in cast(Json, node).values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in cast(list[object], node):
            yield from _walk(item)


def _patches(path: Path) -> list[str]:
    found: list[str] = []
    for e in _events(path):
        if e["eventType"] == "EVENT_TYPE_MARKER_RECORDED":
            attrs = cast(Json, e["markerRecordedEventAttributes"])
            if attrs["markerName"] == "core_patch":
                [payload] = cast(
                    list[Json], cast(Json, cast(Json, attrs["details"])["patch-data"])["payloads"]
                )
                found.append(json.loads(base64.b64decode(cast(str, payload["data"])))["id"])
    return found


# --- the recorded set is what the contract asks for ----------------------------------------------


def test_ac14_the_v2_set_has_every_scenario_and_nothing_is_silently_missing() -> None:
    assert {p.stem for p in RETRIEVAL_V2} >= {
        "retrieval-v2-succeeded",
        "retrieval-v2-failed-validation",
        "retrieval-v2-queued-then-succeeded",
        "retrieval-v2-capacity-timeout",
        "retrieval-v2-cancelled-while-queued",
    }
    assert {p.stem for p in SCREENING_V2} >= {
        "screening-v2-completed",
        "screening-v2-skipped",
        "screening-v2-provider-unavailable",
        "screening-v2-queued-then-completed",
        "screening-v2-capacity-timeout",
        "screening-v2-cancelled-while-queued",
    }


def test_ac16_the_v1_histories_are_all_still_there() -> None:
    assert len(RETRIEVAL_V1) >= 2
    assert len(SCREENING_V1) >= 3


# --- replay --------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", RETRIEVAL_V2, ids=_ids(RETRIEVAL_V2))
async def test_ac13_every_retrieval_v2_history_replays(path: Path) -> None:
    await _replayer(RetrievalWorkflow).replay_workflow(_history(path))


@pytest.mark.parametrize("path", SCREENING_V2, ids=_ids(SCREENING_V2))
async def test_ac13_every_screening_v2_history_replays(path: Path) -> None:
    await _replayer(ScreeningWorkflow).replay_workflow(_history(path))


@pytest.mark.parametrize("path", RETRIEVAL_V1, ids=_ids(RETRIEVAL_V1))
async def test_ac16_every_retrieval_v1_history_still_replays(path: Path) -> None:
    await _replayer(RetrievalWorkflow).replay_workflow(_history(path))


@pytest.mark.parametrize("path", SCREENING_V1, ids=_ids(SCREENING_V1))
async def test_ac16_every_screening_v1_history_still_replays(path: Path) -> None:
    await _replayer(ScreeningWorkflow).replay_workflow(_history(path))


# --- the patch: v2 has the marker, v1 does not ---------------------------------------------------


@pytest.mark.parametrize("path", ALL_V2, ids=_ids(ALL_V2))
def test_ac16_a_v2_history_records_the_work_slots_patch(path: Path) -> None:
    if path.name == "screening-v2-skipped.json":
        assert _patches(path) == []  # skipped before the patch is reached: no slot, no marker
    else:
        assert _patches(path) == ["work-slots"]


@pytest.mark.parametrize(
    "path", [*RETRIEVAL_V1, *SCREENING_V1], ids=_ids([*RETRIEVAL_V1, *SCREENING_V1])
)
def test_ac16_a_v1_history_has_no_patch_and_no_slot_activity(path: Path) -> None:
    assert _patches(path) == []
    assert not [n for n in _scheduled(path) if n.endswith("_slot")]


# --- what each v2 scenario shows -----------------------------------------------------------------


def _v2(name: str) -> Path:
    return HISTORIES / f"{name}.json"


def test_ac13_a_plain_v2_run_asks_once_runs_and_releases() -> None:
    assert _scheduled(_v2("retrieval-v2-succeeded")) == [
        "acquire_slot",
        "pull_raw",
        "normalise_raw",
        "validate_run",
        "snapshot",
        "render",
        "release_slot",
    ]
    assert _scheduled(_v2("screening-v2-completed")) == [
        "create_run",
        "acquire_slot",
        "screen",
        "release_slot",
    ]
    assert _timers(_v2("retrieval-v2-succeeded")) == []


def test_ac6_a_failed_v2_run_ends_the_run_then_releases_in_the_finally() -> None:
    assert _scheduled(_v2("retrieval-v2-failed-validation"))[-2:] == ["fail_run", "release_slot"]
    assert _scheduled(_v2("screening-v2-provider-unavailable"))[-2:] == [
        "fail_run",
        "release_slot",
    ]


def test_ac13_a_skipped_screening_takes_no_slot() -> None:
    assert _scheduled(_v2("screening-v2-skipped")) == ["create_run"]


@pytest.mark.parametrize(
    ("name", "pipeline_starts"),
    [
        ("retrieval-v2-queued-then-succeeded", "pull_raw"),
        ("screening-v2-queued-then-completed", "screen"),
    ],
)
def test_ac13_a_queued_run_asks_more_than_once_with_timers_between_and_then_runs(
    name: str, pipeline_starts: str
) -> None:
    names = _scheduled(_v2(name))
    asks = [i for i, n in enumerate(names) if n == "acquire_slot"]
    assert len(asks) >= 2
    assert names.index(pipeline_starts) > asks[-1]  # nothing runs before the slot is granted
    assert names[-1] == "release_slot"
    assert len(_timers(_v2(name))) >= 1
    assert _last(_v2(name)) == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"


@pytest.mark.parametrize(
    "name", ["retrieval-v2-queued-then-succeeded", "screening-v2-queued-then-completed"]
)
def test_ac13_the_timers_between_asks_back_off_from_a_second_with_jitter(name: str) -> None:
    timers = _timers(_v2(name))
    assert 0.5 <= timers[0] <= 1.5
    assert 1.0 <= timers[1] <= 3.0
    assert all(t <= 90 for t in timers)  # a 60 s cap, jittered up to 1.5x


@pytest.mark.parametrize(
    ("name", "never"),
    [("retrieval-v2-capacity-timeout", "pull_raw"), ("screening-v2-capacity-timeout", "screen")],
)
def test_ac14_a_capacity_timeout_ends_the_run_through_fail_run_and_never_starts_the_work(
    name: str, never: str
) -> None:
    names = _scheduled(_v2(name))
    assert names.count("acquire_slot") >= 2
    assert names[-2:] == ["fail_run", "release_slot"]
    assert never not in names
    assert len(_timers(_v2(name))) >= 1
    assert _last(_v2(name)) == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"  # returned, not dropped


@pytest.mark.parametrize(
    "name", ["retrieval-v2-cancelled-while-queued", "screening-v2-cancelled-while-queued"]
)
def test_ac14_a_cancel_while_queued_ends_the_run_then_releases_and_the_workflow_is_cancelled(
    name: str,
) -> None:
    names = _scheduled(_v2(name))
    assert names.count("acquire_slot") >= 1
    assert names[-2:] == ["fail_run", "release_slot"]
    assert _last(_v2(name)) == "EVENT_TYPE_WORKFLOW_EXECUTION_CANCELED"
    assert not {"pull_raw", "screen"} & set(names)


# --- the recordings hold identifiers only --------------------------------------------------------


@pytest.mark.parametrize("path", ALL_V2, ids=_ids(ALL_V2))
def test_ac15_the_v2_histories_are_decoded_scrubbed_and_hold_identifiers_only(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    encodings: set[str] = set()
    for node in _walk(json.loads(text)):
        if isinstance(node, dict) and "payloads" in node:
            for payload in cast(list[Json], cast(Json, node)["payloads"]):
                metadata = cast(dict[str, str], payload.get("metadata", {}))
                encodings.add(base64.b64decode(metadata.get("encoding", "")).decode())
    assert encodings
    assert ENCODING.decode() not in encodings
    assert encodings <= {"json/plain", "binary/null"}
    identities = {
        cast(str, n["identity"])
        for n in _walk(json.loads(text))
        if isinstance(n, dict) and "identity" in n
    }
    assert identities <= {"worker@recorder"}
    assert "encryption-key-id" not in text
    lowered = text.lower()
    for word in ("account", "debit", "credit", "balance_sheet", "rationale"):
        assert f'"{word}' not in lowered
    ledger = generate(1).client_entities[0].trial_balances[-1]
    for line in ledger.lines:
        assert line.account_name not in text


@pytest.mark.parametrize("path", ALL_V2, ids=_ids(ALL_V2))
def test_ac15_the_v2_slot_asks_carry_no_queue_text_and_no_other_firms(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert "recorder-blocker" not in text  # the other work's holder never reaches a history
    assert not re.search(r"firm_cap|engagement_cap|class_capacity", text)  # reasons stay in the db


# --- an unguarded change is detected -------------------------------------------------------------


@workflow.defn(name="retrieval")
class AlwaysAcquireFirst:
    """The v2 shape without the patch: asks for a slot even on a v1 history."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        await workflow.execute_activity(
            "retrieval.acquire_slot", input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
        )
        for name in (
            "retrieval.pull_raw",
            "retrieval.normalise_raw",
            "retrieval.validate_run",
            "retrieval.snapshot",
        ):
            await workflow.execute_activity(
                name, input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
            )
        version_id = await workflow.execute_activity(
            "retrieval.render",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        return RetrievalOutcome("succeeded", None, version_id)


@workflow.defn(name="retrieval")
class AsksOnceAndRuns:
    """Patched, but never waits: a queued history's timer has no command to match."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        workflow.patched("work-slots")
        await workflow.execute_activity(
            "retrieval.acquire_slot", input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
        )
        await workflow.execute_activity(
            "retrieval.pull_raw", input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
        )
        return RetrievalOutcome("succeeded")


@workflow.defn(name="screening")
class ScreensWithoutSlot:
    """Drops the slot steps from the screening workflow."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            "screening.create_run",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        return await workflow.execute_activity(
            "screening.screen",
            RunInput(input.tenant_id, run_id),
            result_type=ScreeningOutcome,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )


async def test_ac16_an_unpatched_slot_step_fails_replay_of_a_v1_history() -> None:
    with pytest.raises(workflow.NondeterminismError):
        await _replayer(AlwaysAcquireFirst, sandboxed=False).replay_workflow(
            _history(HISTORIES / "retrieval-v1-succeeded.json")
        )


async def test_ac13_a_workflow_that_never_waits_fails_replay_of_the_queued_history() -> None:
    with pytest.raises(workflow.NondeterminismError):
        await _replayer(AsksOnceAndRuns, sandboxed=False).replay_workflow(
            _history(_v2("retrieval-v2-queued-then-succeeded"))
        )


@pytest.mark.parametrize("name", ["screening-v2-completed", "screening-v2-queued-then-completed"])
async def test_ac16_a_screening_without_the_slot_steps_fails_replay_of_a_v2_history(
    name: str,
) -> None:
    with pytest.raises(workflow.NondeterminismError):
        await _replayer(ScreensWithoutSlot, sandboxed=False).replay_workflow(_history(_v2(name)))
