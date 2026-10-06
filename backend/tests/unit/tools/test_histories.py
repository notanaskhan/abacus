"""AC-19: the replay-history scrubber keeps identifiers, opens sealed payloads and replaces every
machine identifier (`abacus_tools.workflows.histories`; ADR-090)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from temporalio.api.common.v1 import Payload, Payloads
from temporalio.api.enums.v1 import EventType, TaskQueueKind
from temporalio.api.history.v1 import HistoryEvent
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.client import WorkflowHistory

from abacus.kernel.crypto.payload_codec import ENCODING, PayloadEncryptionCodec
from abacus_tools.workflows.histories import (
    SCRUBBED_IDENTITY,
    SCRUBBED_STICKY_QUEUE,
    decoded_and_scrubbed,
)

SECRET = b"test-history-secret-0123456789abcdef-xyz"
PLAIN = b'{"run_id": "test-run-4417"}'
HISTORIES = Path(__file__).resolve().parents[2] / "workflows" / "histories"


def _codec() -> PayloadEncryptionCodec:
    return PayloadEncryptionCodec({"platform-v1": SECRET}, current="platform-v1")


def _plain(data: bytes = PLAIN) -> Payload:
    return Payload(metadata={"encoding": b"json/plain"}, data=data)


async def _sealed(data: bytes = PLAIN) -> Payload:
    [sealed] = await _codec().encode([_plain(data)])
    return sealed


def _history(*events: HistoryEvent) -> WorkflowHistory:
    return WorkflowHistory("test-history", list(events))


def _started() -> HistoryEvent:
    return HistoryEvent(event_type=EventType.EVENT_TYPE_WORKFLOW_EXECUTION_STARTED)


async def test_ac19_a_sealed_workflow_input_is_opened() -> None:
    event = _started()
    event.workflow_execution_started_event_attributes.input.CopyFrom(
        Payloads(payloads=[await _sealed()])
    )
    result = await decoded_and_scrubbed(_history(event), _codec())
    [payload] = result.events[0].workflow_execution_started_event_attributes.input.payloads
    assert payload.metadata["encoding"] == b"json/plain"
    assert payload.data == PLAIN
    assert "encryption-key-id" not in payload.metadata


async def test_ac19_a_payload_that_is_not_sealed_is_left_alone() -> None:
    event = _started()
    event.workflow_execution_started_event_attributes.input.CopyFrom(
        Payloads(payloads=[_plain(b"null")])
    )
    result = await decoded_and_scrubbed(_history(event), _codec())
    [payload] = result.events[0].workflow_execution_started_event_attributes.input.payloads
    assert payload.data == b"null"
    assert payload.metadata["encoding"] == b"json/plain"


async def test_ac19_payloads_nested_in_maps_are_opened() -> None:
    event = _started()
    memo = event.workflow_execution_started_event_attributes.memo
    memo.fields["note"].CopyFrom(await _sealed(b'"memo-value"'))
    result = await decoded_and_scrubbed(_history(event), _codec())
    opened = result.events[0].workflow_execution_started_event_attributes.memo.fields["note"]
    assert opened.metadata["encoding"] == b"json/plain"
    assert opened.data == b'"memo-value"'


async def test_ac19_the_worker_identity_is_replaced_and_the_identifiers_are_kept() -> None:
    event = _started()
    attributes = event.workflow_execution_started_event_attributes
    attributes.identity = "12345@alice-laptop.local"
    attributes.workflow_id = "retrieval:test-run-4417"
    attributes.original_execution_run_id = "run-id-kept"
    attributes.workflow_type.name = "retrieval"
    result = await decoded_and_scrubbed(_history(event), _codec())
    scrubbed = result.events[0].workflow_execution_started_event_attributes
    assert scrubbed.identity == SCRUBBED_IDENTITY == "worker@recorder"
    assert scrubbed.workflow_id == "retrieval:test-run-4417"
    assert scrubbed.original_execution_run_id == "run-id-kept"
    assert scrubbed.workflow_type.name == "retrieval"
    assert "alice-laptop" not in result.to_json()


async def test_ac19_identity_on_task_events_is_replaced() -> None:
    event = HistoryEvent(event_type=EventType.EVENT_TYPE_WORKFLOW_TASK_STARTED)
    event.workflow_task_started_event_attributes.identity = "999@build-host-7"
    result = await decoded_and_scrubbed(_history(event), _codec())
    assert result.events[0].workflow_task_started_event_attributes.identity == SCRUBBED_IDENTITY


async def test_ac19_binary_checksums_are_replaced() -> None:
    event = HistoryEvent(event_type=EventType.EVENT_TYPE_WORKFLOW_TASK_COMPLETED)
    event.workflow_task_completed_event_attributes.binary_checksum = "sum-of-the-recording-build"
    result = await decoded_and_scrubbed(_history(event), _codec())
    assert "sum-of-the-recording-build" not in result.to_json()
    assert result.events[0].workflow_task_completed_event_attributes.binary_checksum == "recorder"


async def test_ac19_a_sticky_task_queue_named_after_the_host_is_replaced() -> None:
    event = HistoryEvent(event_type=EventType.EVENT_TYPE_WORKFLOW_TASK_SCHEDULED)
    event.workflow_task_scheduled_event_attributes.task_queue.CopyFrom(
        TaskQueue(
            name="alice-laptop.local:6f1c-sticky@12345", kind=TaskQueueKind.TASK_QUEUE_KIND_STICKY
        )
    )
    result = await decoded_and_scrubbed(_history(event), _codec())
    queue = result.events[0].workflow_task_scheduled_event_attributes.task_queue
    assert queue.name == SCRUBBED_STICKY_QUEUE == "sticky@recorder"
    assert queue.kind == TaskQueueKind.TASK_QUEUE_KIND_STICKY
    assert "alice-laptop" not in result.to_json()


async def test_ac19_a_normal_task_queue_name_is_kept() -> None:
    event = HistoryEvent(event_type=EventType.EVENT_TYPE_WORKFLOW_TASK_SCHEDULED)
    event.workflow_task_scheduled_event_attributes.task_queue.CopyFrom(
        TaskQueue(name="abacus-recorder")
    )
    result = await decoded_and_scrubbed(_history(event), _codec())
    queue = result.events[0].workflow_task_scheduled_event_attributes.task_queue
    assert queue.name == "abacus-recorder"


async def test_ac19_every_event_of_a_history_is_scrubbed() -> None:
    events: list[HistoryEvent] = []
    for number in range(1, 4):
        event = HistoryEvent(
            event_id=number, event_type=EventType.EVENT_TYPE_WORKFLOW_TASK_STARTED
        )
        event.workflow_task_started_event_attributes.identity = f"host-{number}"
        events.append(event)
    result = await decoded_and_scrubbed(_history(*events), _codec())
    assert [e.event_id for e in result.events] == [1, 2, 3]
    assert {e.workflow_task_started_event_attributes.identity for e in result.events} == {
        SCRUBBED_IDENTITY
    }


async def test_ac19_an_empty_history_comes_back_empty() -> None:
    assert (await decoded_and_scrubbed(_history(), _codec())).events == []


async def test_ac19_a_payload_sealed_under_an_unknown_key_is_not_silently_kept() -> None:
    other = PayloadEncryptionCodec({"platform-v2": b"x" * 32 + b"abc"}, current="platform-v2")
    event = _started()
    event.workflow_execution_started_event_attributes.input.CopyFrom(
        Payloads(payloads=[(await other.encode([_plain()]))[0]])
    )
    with pytest.raises(Exception, match=r"."):
        await decoded_and_scrubbed(_history(event), _codec())


@pytest.mark.parametrize("name", ["retrieval-v1-succeeded", "retrieval-v1-failed-validation"])
async def test_ac19_scrubbing_a_recorded_fixture_changes_nothing(name: str) -> None:
    text = (HISTORIES / f"{name}.json").read_text(encoding="utf-8")
    history = WorkflowHistory.from_json("test-history", text)
    before = json.loads(history.to_json())
    result = await decoded_and_scrubbed(history, _codec())
    assert json.loads(result.to_json()) == before
    assert ENCODING.decode() not in result.to_json()
