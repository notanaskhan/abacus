"""AC-19: the screening workflow replays its recorded histories, and a change to its activity
sequence is detected as non-determinism (TASK-011b contract revision 1, "Replay histories";
ADR-017, ADR-090).

Offline: `Replayer` needs no Temporal server and no codec. The recorded histories
(`tests/workflows/histories/screening-v1-*.json`) are decoded and scrubbed: plain payloads,
identifiers only.
"""

from __future__ import annotations

import base64
import json
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.kernel.crypto.payload_codec import ENCODING
from abacus.modules.agents.api import ScreeningWorkflow
from abacus.modules.agents.workflow_types import (
    FailInput,
    RunInput,
    ScreeningInput,
    ScreeningOutcome,
)
from abacus_tools.synthetic import generate

HISTORIES = Path(__file__).resolve().parent / "histories"
COMPLETED = HISTORIES / "screening-v1-completed.json"
SKIPPED = HISTORIES / "screening-v1-skipped.json"
UNAVAILABLE = HISTORIES / "screening-v1-provider-unavailable.json"
ALL = [COMPLETED, SKIPPED, UNAVAILABLE]
IDS = ["completed", "skipped", "provider-unavailable"]
Json = dict[str, object]
_TIMEOUT = timedelta(minutes=2)
_RETRY = RetryPolicy(maximum_attempts=4)
CREATE, SCREEN, FAIL = "screening.create_run", "screening.screen", "screening.fail_run"


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-screening-replay", path.read_text(encoding="utf-8"))


def _replayer(*workflows: type, sandboxed: bool = True) -> Replayer:
    """No data converter: the recorded histories carry plain payloads."""
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
        )
        for e in _events(path)
        if e["eventType"] == "EVENT_TYPE_ACTIVITY_TASK_SCHEDULED"
    ]


def _walk(node: object) -> Iterator[object]:
    yield node
    if isinstance(node, dict):
        for value in cast(Json, node).values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in cast(list[object], node):
            yield from _walk(item)


# --- the recorded histories ----------------------------------------------------------------------


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_ac19_a_recorded_history_replays_against_the_workflow_without_a_codec(
    path: Path,
) -> None:
    await _replayer(ScreeningWorkflow).replay_workflow(_history(path))


def test_ac19_the_completed_history_creates_the_run_then_screens() -> None:
    assert _scheduled(COMPLETED) == [CREATE, SCREEN]
    assert _events(COMPLETED)[-1]["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"


def test_ac19_the_skipped_history_only_creates_the_run() -> None:
    assert _scheduled(SKIPPED) == [CREATE]
    assert _events(SKIPPED)[-1]["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"


def test_ac19_the_provider_unavailable_history_ends_in_fail_run_after_screen() -> None:
    assert _scheduled(UNAVAILABLE) == [CREATE, SCREEN, FAIL]
    assert _events(UNAVAILABLE)[-1]["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_ac19_the_histories_are_decoded_not_sealed_and_scrubbed(path: Path) -> None:
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
    assert "ZW5jcnlwdGlvbi1rZXktaWQ" not in text


@pytest.mark.parametrize("path", ALL, ids=IDS)
def test_ac19_the_histories_carry_identifiers_only_no_ledger_values(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    lowered = text.lower()
    for word in ("account", "debit", "credit", "balance_sheet", "rationale"):
        assert f'"{word}' not in lowered
    ledger = generate(1).client_entities[0].trial_balances[-1]
    for line in ledger.lines:
        assert line.account_name not in text
        for amount in (str(line.debit), str(line.credit)):
            if amount != "0.00":
                assert amount not in text
    assert str(ledger.total_debits) not in text


# --- non-determinism is detected -----------------------------------------------------------------


@workflow.defn(name="screening")
class SameCompleted:
    """The recorded sequence, written independently: the control for the failing variants."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            CREATE, input, result_type=str, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        return await workflow.execute_activity(
            SCREEN,
            RunInput(input.tenant_id, run_id),
            result_type=ScreeningOutcome,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )


@workflow.defn(name="screening")
class SameUnavailable:
    """The recorded failure path: a failed screen ends in fail_run."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            CREATE, input, result_type=str, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        run = RunInput(input.tenant_id, run_id)
        try:
            return await workflow.execute_activity(
                SCREEN,
                run,
                result_type=ScreeningOutcome,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            return await workflow.execute_activity(
                FAIL,
                FailInput(run.tenant_id, run.run_id, "provider_unavailable"),
                result_type=ScreeningOutcome,
                start_to_close_timeout=_TIMEOUT,
            )


@workflow.defn(name="screening")
class NeverScreens:
    """Creates the run and stops: drops the screen activity."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        await workflow.execute_activity(
            CREATE, input, result_type=str, start_to_close_timeout=_TIMEOUT
        )
        return ScreeningOutcome("skipped")


@workflow.defn(name="screening")
class ScreensTwice:
    """Adds a second screen the recording never scheduled (an unguarded change, ADR-090)."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            CREATE, input, result_type=str, start_to_close_timeout=_TIMEOUT
        )
        run = RunInput(input.tenant_id, run_id)
        await workflow.execute_activity(
            SCREEN, run, result_type=ScreeningOutcome, start_to_close_timeout=_TIMEOUT
        )
        return await workflow.execute_activity(
            SCREEN, run, result_type=ScreeningOutcome, start_to_close_timeout=_TIMEOUT
        )


@workflow.defn(name="screening")
class ScreensFirst:
    """Screens before creating the run."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        outcome = await workflow.execute_activity(
            SCREEN,
            RunInput(input.tenant_id, input.event_id),
            result_type=ScreeningOutcome,
            start_to_close_timeout=_TIMEOUT,
        )
        await workflow.execute_activity(
            CREATE, input, result_type=str, start_to_close_timeout=_TIMEOUT
        )
        return outcome


@workflow.defn(name="screening")
class FailsFirst:
    """Ends a run before creating one."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        return await workflow.execute_activity(
            FAIL,
            FailInput(input.tenant_id, input.event_id, "internal_error"),
            result_type=ScreeningOutcome,
            start_to_close_timeout=_TIMEOUT,
        )


@workflow.defn(name="screening")
class UnavailableNoFailRun:
    """Gives up on a failed screen without ending the run."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            CREATE, input, result_type=str, start_to_close_timeout=_TIMEOUT
        )
        try:
            return await workflow.execute_activity(
                SCREEN,
                RunInput(input.tenant_id, run_id),
                result_type=ScreeningOutcome,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            return ScreeningOutcome("failed", run_id, "provider_unavailable")


@workflow.defn(name="screening")
class UnavailableFailsTwice:
    """Ends the run twice after a failed screen."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            CREATE, input, result_type=str, start_to_close_timeout=_TIMEOUT
        )
        run = RunInput(input.tenant_id, run_id)
        try:
            return await workflow.execute_activity(
                SCREEN,
                run,
                result_type=ScreeningOutcome,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            fail = FailInput(run.tenant_id, run.run_id, "provider_unavailable")
            await workflow.execute_activity(
                FAIL, fail, result_type=ScreeningOutcome, start_to_close_timeout=_TIMEOUT
            )
            return await workflow.execute_activity(
                FAIL, fail, result_type=ScreeningOutcome, start_to_close_timeout=_TIMEOUT
            )


async def test_ac19_the_same_sequence_replays_the_completed_and_skipped_histories() -> None:
    await _replayer(SameCompleted, sandboxed=False).replay_workflow(_history(COMPLETED))
    await _replayer(SameCompleted, sandboxed=False).replay_workflow(_history(SKIPPED))


async def test_ac19_the_same_failure_path_replays_the_unavailable_history() -> None:
    await _replayer(SameUnavailable, sandboxed=False).replay_workflow(_history(UNAVAILABLE))


@pytest.mark.parametrize("changed", [NeverScreens, ScreensTwice, ScreensFirst, FailsFirst])
async def test_ac19_a_changed_activity_sequence_fails_replay_of_the_completed_history(
    changed: type,
) -> None:
    with pytest.raises(workflow.NondeterminismError):
        await _replayer(changed, sandboxed=False).replay_workflow(_history(COMPLETED))


@pytest.mark.parametrize("changed", [ScreensTwice, FailsFirst])
async def test_ac19_a_workflow_that_always_screens_fails_replay_of_the_skipped_history(
    changed: type,
) -> None:
    with pytest.raises(workflow.NondeterminismError):
        await _replayer(changed, sandboxed=False).replay_workflow(_history(SKIPPED))


@pytest.mark.parametrize(
    "changed", [UnavailableNoFailRun, UnavailableFailsTwice, SameCompleted, ScreensFirst]
)
async def test_ac19_a_changed_failure_path_fails_replay_of_the_unavailable_history(
    changed: type,
) -> None:
    with pytest.raises(workflow.NondeterminismError):
        await _replayer(changed, sandboxed=False).replay_workflow(_history(UNAVAILABLE))
