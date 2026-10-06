"""AC-19: the retrieval workflow replays its recorded histories, and a change to its activity
sequence is detected as non-determinism (TASK-010b interface contract and revision 1, "Replay";
ADR-017, ADR-090).

Offline: `Replayer` needs no Temporal server and no codec. The recorded histories
(`tests/workflows/histories/retrieval-v1-*.json`) are decoded and scrubbed: plain payloads,
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
from abacus.modules.connections.api import (
    FailInput,
    RetrievalInput,
    RetrievalOutcome,
    RetrievalWorkflow,
)

HISTORIES = Path(__file__).resolve().parent / "histories"
SUCCEEDED = HISTORIES / "retrieval-v1-succeeded.json"
FAILED_VALIDATION = HISTORIES / "retrieval-v1-failed-validation.json"
Json = dict[str, object]
_TIMEOUT = timedelta(minutes=5)
_RETRY = RetryPolicy(maximum_attempts=6)
STAGES = (
    "retrieval.pull_raw",
    "retrieval.normalise_raw",
    "retrieval.validate_run",
    "retrieval.snapshot",
)


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-retrieval-replay", path.read_text(encoding="utf-8"))


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


# --- the recorded histories ----------------------------------------------------------------------


@pytest.mark.parametrize("path", [SUCCEEDED, FAILED_VALIDATION], ids=["succeeded", "failed"])
async def test_ac19_a_recorded_history_replays_without_a_codec(path: Path) -> None:
    await _replayer(RetrievalWorkflow).replay_workflow(_history(path))


def test_ac19_the_succeeded_history_runs_the_five_stages_in_order() -> None:
    assert _scheduled(SUCCEEDED) == [*STAGES, "retrieval.render"]
    assert _events(SUCCEEDED)[-1]["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"


def test_ac19_the_failed_validation_history_ends_in_fail_run_after_validate_run() -> None:
    assert _scheduled(FAILED_VALIDATION) == [*STAGES[:3], "retrieval.fail_run"]
    assert _events(FAILED_VALIDATION)[-1]["eventType"] == "EVENT_TYPE_WORKFLOW_EXECUTION_COMPLETED"


def _walk(node: object) -> Iterator[object]:
    yield node
    if isinstance(node, dict):
        for value in cast(Json, node).values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in cast(list[object], node):
            yield from _walk(item)


@pytest.mark.parametrize("path", [SUCCEEDED, FAILED_VALIDATION], ids=["succeeded", "failed"])
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


@pytest.mark.parametrize("path", [SUCCEEDED, FAILED_VALIDATION], ids=["succeeded", "failed"])
def test_ac19_the_histories_carry_identifiers_only_no_ledger_values(path: Path) -> None:
    text = path.read_text(encoding="utf-8").lower()
    for word in ("account", "debit", "credit", "balance_sheet"):
        assert f'"{word}' not in text


# --- non-determinism is detected -----------------------------------------------------------------


@workflow.defn(name="retrieval")
class SameSequence:
    """The recorded sequence, written independently: the control for the failing variants."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
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
class SwappedStages:
    """Validates before it normalises: a changed activity sequence."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        for name in (
            "retrieval.pull_raw",
            "retrieval.validate_run",
            "retrieval.normalise_raw",
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
class SkippedStage:
    """Drops the snapshot stage."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        for name in ("retrieval.pull_raw", "retrieval.normalise_raw", "retrieval.validate_run"):
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
class ExtraStage:
    """Adds an activity the recording never scheduled (an unguarded change, ADR-090)."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        for name in (
            "retrieval.pull_raw",
            "retrieval.normalise_raw",
            "retrieval.validate_run",
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
class FailFirst:
    """Reports a failure before running anything."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        try:
            return await workflow.execute_activity(
                "retrieval.fail_run",
                FailInput(input.tenant_id, input.run_id, "failed", "internal_error"),
                result_type=RetrievalOutcome,
                start_to_close_timeout=_TIMEOUT,
            )
        except ActivityError:
            return RetrievalOutcome("failed", "internal_error")


@workflow.defn(name="retrieval")
class FailedPathSame:
    """The recorded failure path, written independently: the control for the failure variants."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        try:
            for name in STAGES[:3]:
                await workflow.execute_activity(
                    name, input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
                )
        except ActivityError:
            return await workflow.execute_activity(
                "retrieval.fail_run",
                FailInput(input.tenant_id, input.run_id, "failed_validation", "unbalanced"),
                result_type=RetrievalOutcome,
                start_to_close_timeout=_TIMEOUT,
            )
        return RetrievalOutcome("succeeded")


@workflow.defn(name="retrieval")
class FailedPathNoFailRun:
    """Ends the workflow on a stage failure without ending the run."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        try:
            for name in STAGES[:3]:
                await workflow.execute_activity(
                    name, input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
                )
        except ActivityError:
            return RetrievalOutcome("failed_validation", "unbalanced")
        return RetrievalOutcome("succeeded")


@workflow.defn(name="retrieval")
class FailedPathSnapshotInstead:
    """Takes a snapshot where the recording ended the run."""

    @workflow.run
    async def run(self, input: RetrievalInput) -> RetrievalOutcome:
        try:
            for name in STAGES[:3]:
                await workflow.execute_activity(
                    name, input, start_to_close_timeout=_TIMEOUT, retry_policy=_RETRY
                )
        except ActivityError:
            await workflow.execute_activity(
                "retrieval.snapshot", input, start_to_close_timeout=_TIMEOUT
            )
        return RetrievalOutcome("succeeded")


async def test_ac19_a_workflow_with_the_same_sequence_replays_the_succeeded_history() -> None:
    await _replayer(SameSequence, sandboxed=False).replay_workflow(_history(SUCCEEDED))


async def test_ac19_a_workflow_with_the_same_failure_path_replays_the_failed_history() -> None:
    await _replayer(FailedPathSame, sandboxed=False).replay_workflow(_history(FAILED_VALIDATION))


@pytest.mark.parametrize("changed", [SwappedStages, SkippedStage, ExtraStage, FailFirst])
async def test_ac19_a_changed_activity_sequence_fails_replay_of_the_succeeded_history(
    changed: type,
) -> None:
    with pytest.raises(workflow.NondeterminismError):
        await _replayer(changed, sandboxed=False).replay_workflow(_history(SUCCEEDED))


@pytest.mark.parametrize("changed", [FailedPathNoFailRun, FailedPathSnapshotInstead, SameSequence])
async def test_ac19_a_changed_failure_path_fails_replay_of_the_failed_history(
    changed: type,
) -> None:
    with pytest.raises(workflow.NondeterminismError):
        await _replayer(changed, sandboxed=False).replay_workflow(_history(FAILED_VALIDATION))
