"""G-04-T10/T11 rest (S48; G-04 §4.8, AC-40, AC-47): the support reply notice goes only when the
reply is still unread five minutes on, and a plan request awaiting its partner is a C13 gate
assigned to that partner."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.platform import support

OWNER = uuid.uuid4()
REPLY_AT = datetime(2026, 10, 9, 13, 47, tzinfo=UTC)


class _Result:
    def __init__(self, row: object) -> None:
        self.row = row

    def first(self) -> object:
        return self.row


class _Session:
    def __init__(self, row: object) -> None:
        self.row = row

    async def execute(self, *_: object) -> _Result:
        return _Result(self.row)


class _Tx:
    def __init__(self, sink: list[object]) -> None:
        self.sink = sink

    def record(self, action: str, **_: object) -> None:
        self.sink.append(action)

    def emit(self, event: object, **_: object) -> None:
        self.sink.append(event)


def _wire(monkeypatch: pytest.MonkeyPatch, row: object) -> list[object]:
    sink: list[object] = []

    @asynccontextmanager
    async def session(_t: object) -> AsyncGenerator[_Session]:
        yield _Session(row)

    @asynccontextmanager
    async def uow(_t: object) -> AsyncGenerator[_Tx]:
        yield _Tx(sink)

    monkeypatch.setattr(support, "tenant_session", session)
    monkeypatch.setattr(support, "uow", uow)
    return sink


def _held() -> OutboxEvent:
    return OutboxEvent(
        uuid.uuid4(),
        uuid.uuid4(),
        "support.reply_held",
        {"conversation_id": str(uuid.uuid4()), "message_id": str(uuid.uuid4())},
    )


@pytest.mark.parametrize(
    ("read_at", "sent"),
    [
        (None, True),  # never opened
        (REPLY_AT - timedelta(minutes=1), True),  # opened before the reply
        (REPLY_AT + timedelta(minutes=2), False),  # read within the five minutes
    ],
)
async def test_the_notice_goes_only_while_the_reply_is_unread(
    monkeypatch: pytest.MonkeyPatch, read_at: datetime | None, sent: bool
) -> None:
    row = SimpleNamespace(user_id=OWNER, created_at=REPLY_AT, last_read_at=read_at)
    sink = _wire(monkeypatch, row)
    await support.on_reply_held(_held())
    notices = [e for e in sink if isinstance(e, support.SupportReplied)]
    if sent:
        assert [n.recipient_user_ids for n in notices] == [[OWNER]]
    else:
        assert notices == []


def test_the_reply_is_held_five_minutes() -> None:
    assert timedelta(minutes=5) == support.REPLY_NOTICE_DELAY


async def test_a_waiting_plan_request_is_the_partners_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.modules.platform import api as platform
    from abacus.modules.review import firm_gates

    request, partner = uuid.uuid4(), uuid.uuid4()

    async def awaiting(*_: object) -> list[tuple[uuid.UUID, uuid.UUID | None]]:
        return [(request, partner)]

    monkeypatch.setattr(platform, "awaiting_plan_requests", awaiting)
    gates = await firm_gates.plan_requests_open(object(), None)  # type: ignore[arg-type] -- unused
    assert [(g.subject_id, g.assignee_user_id, g.engagement_id) for g in gates] == [
        (request, partner, None)
    ]
