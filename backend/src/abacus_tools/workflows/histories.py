"""Replay-history fixtures: decode, scrub, record (ADR-090, AC-19).

Fixtures are stored decoded (payloads in plain form, only identifiers) and scrubbed (no worker
host names or build IDs), so they replay with any key ring and leak nothing about the machine
that recorded them. A fixture is never overwritten: a changed workflow adds a new version beside
the old ones, and every version must keep replaying.

Record (needs Docker; starts its own Postgres, S3 gateway and Temporal):

    python -m abacus_tools.workflows.record_retrieval tests/workflows/histories
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message
from temporalio.api.common.v1 import Payload
from temporalio.client import WorkflowHistory

from abacus.kernel.crypto.payload_codec import ENCODING, PayloadEncryptionCodec

SCRUBBED_IDENTITY = "worker@recorder"
_IDENTITY_FIELDS = frozenset({"identity"})
_BUILD_FIELDS = frozenset({"binary_checksum", "build_id"})


async def _decode_payload(payload: Payload, codec: PayloadEncryptionCodec) -> None:
    if payload.metadata.get("encoding") == ENCODING:
        (plain,) = await codec.decode([payload])
        payload.CopyFrom(plain)


_TASK_QUEUE = "temporal.api.taskqueue.v1.TaskQueue"
SCRUBBED_STICKY_QUEUE = "sticky@recorder"


async def _walk(message: Message, codec: PayloadEncryptionCodec) -> None:
    if message.DESCRIPTOR.full_name == _TASK_QUEUE and "@" in getattr(message, "name", ""):
        message.name = SCRUBBED_STICKY_QUEUE  # sticky queues name the worker host
    for field, value in message.ListFields():
        if field.type == FieldDescriptor.TYPE_STRING and field.name in _IDENTITY_FIELDS:
            setattr(message, field.name, SCRUBBED_IDENTITY)
            continue
        if field.type == FieldDescriptor.TYPE_STRING and field.name in _BUILD_FIELDS:
            setattr(message, field.name, "recorder")
            continue
        if field.type != FieldDescriptor.TYPE_MESSAGE:
            continue
        if isinstance(value, Message):
            children = [value]
        elif isinstance(value, Mapping):
            children = [
                v for v in cast(Mapping[object, object], value).values() if isinstance(v, Message)
            ]
        else:
            children = [v for v in cast(Iterable[object], value) if isinstance(v, Message)]
        for child in children:
            if isinstance(child, Payload):
                await _decode_payload(child, codec)
            else:
                await _walk(child, codec)


async def decoded_and_scrubbed(
    history: WorkflowHistory, codec: PayloadEncryptionCodec
) -> WorkflowHistory:
    """The history with every sealed payload opened and machine identifiers replaced."""
    for event in history.events:
        await _walk(event, codec)
    return history
