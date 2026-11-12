"""TASK-7325: the session's live thread. An item written emits `session.items_changed` with
identifiers only; the realtime stream turns it into an invalidate on `session:<id>`; the topic is
open only to whoever may read the session in full."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import pytest

from abacus.kernel import realtime
from abacus.modules.workbench import api as _workbench  # registers the topic and invalidation
from abacus.modules.workbench import sessions
from abacus.modules.workbench.session_events import SessionItemsChanged, session_topic

del _workbench


@dataclass
class _Ctx:
    client: bool = False
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID = field(default_factory=uuid.uuid4)


def test_the_event_carries_identifiers_only() -> None:
    event = SessionItemsChanged(session_id=uuid.uuid4(), seq=3)
    assert event.event_type == "session.items_changed"
    assert set(event.model_dump()) - {"event_id"} == {"session_id", "seq"}


def test_an_item_invalidates_the_sessions_own_topic() -> None:
    found = realtime.invalidation_of("session.items_changed")
    assert found is not None
    assert (found.ref_type, found.ref_field) == ("session", "session_id")
    assert found.topic_fields == (("session", "session_id"),)


async def test_the_topic_is_open_only_to_a_full_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    open_to: set[uuid.UUID] = set()

    async def readable(_ctx: object, session_id: uuid.UUID) -> bool:
        return session_id in open_to

    monkeypatch.setattr(sessions, "readable_in_full", readable)
    sid = uuid.uuid4()
    assert await session_topic(_Ctx(), str(sid)) is None
    open_to.add(sid)
    assert await session_topic(_Ctx(), str(sid)) == "content"
    # A client principal never subscribes, and a malformed id reads nothing.
    assert await session_topic(_Ctx(client=True), str(sid)) is None
    assert await session_topic(_Ctx(), "not-a-uuid") is None
