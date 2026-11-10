"""P-10-T26 (TASK-6516; SPEC-647 AC-T1, AC-T2; ADR-232 proposed; DEC-3116): the SSE core.

Row acceptance: "A reconnect with Last-Event-ID receives every missed event in order, a new wall
closes the stream with locked within 60 s, and a seventh stream gets 409 too_many_streams."
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence

import pytest

from abacus.kernel import realtime as rt

pytestmark = pytest.mark.asyncio


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _events(after: int | None, upto: int) -> list[rt.StreamEvent]:
    return [
        rt.StreamEvent(n, "item.appended", {"seq": n}) for n in range((after or 0) + 1, upto + 1)
    ]


async def _take(gen: AsyncIterator[bytes], n: int) -> list[bytes]:
    out: list[bytes] = []
    async for chunk in gen:
        out.append(chunk)
        if len(out) >= n:
            break
    return out


async def test_a_reconnect_replays_every_missed_event_in_order() -> None:
    clock = Clock()

    async def source(after: int | None) -> Sequence[rt.StreamEvent]:
        return _events(after, 7)

    async def ok() -> bool:
        return True

    async def tick(_s: float) -> None:
        clock.now += 1

    chunks = await _take(
        rt.stream(
            source, ok, topics=("run:x",), last_seq=3, expires_at=None, clock=clock, sleep=tick
        ),
        4,
    )
    assert [c.split(b"\n")[0] for c in chunks] == [b"id: 4", b"id: 5", b"id: 6", b"id: 7"]


async def test_a_new_wall_sends_locked_within_60_seconds() -> None:
    clock = Clock()
    walled = False

    async def source(after: int | None) -> Sequence[rt.StreamEvent]:
        return []

    async def allowed() -> bool:
        return not walled

    async def tick(_s: float) -> None:
        nonlocal walled
        clock.now += 1
        walled = clock.now > 5  # a wall lands 5 s in

    chunks = [
        c
        async for c in rt.stream(
            source,
            allowed,
            topics=("run:x",),
            last_seq=None,
            expires_at=None,
            clock=clock,
            sleep=tick,
        )
    ]
    assert b"event: locked" in chunks[-1]
    assert clock.now <= 61


async def test_a_gap_older_than_the_horizon_answers_resync() -> None:
    async def source(after: int | None) -> Sequence[rt.StreamEvent]:
        raise rt.GapTooOld

    async def ok() -> bool:
        return True

    chunks = [
        c async for c in rt.stream(source, ok, topics=("run:x",), last_seq=1, expires_at=None)
    ]
    assert len(chunks) == 1 and b"event: resync" in chunks[0]


def test_a_seventh_stream_is_refused() -> None:
    tenant, user = uuid.uuid4(), uuid.uuid4()
    for _ in range(rt.MAX_STREAMS_PER_USER):
        rt.claim_slot(tenant, user)
    with pytest.raises(rt.TooManyStreams):
        rt.claim_slot(tenant, user)
    rt.release_slot(tenant, user)
    rt.claim_slot(tenant, user)  # a freed slot is usable again
    for _ in range(rt.MAX_STREAMS_PER_USER):
        rt.release_slot(tenant, user)


def test_over_64_kb_goes_by_reference() -> None:
    big = rt.frame(rt.StreamEvent(9, "item.appended", {"id": "abc", "blob": "x" * 70_000}))
    assert b'"ref_only":true' in big and len(big) < 500
    small = rt.frame(rt.StreamEvent(1, "invalidate", {"ref_id": "r"}))
    assert small.startswith(b"id: 1\nevent: invalidate\ndata: ")


async def test_a_heartbeat_comes_every_15_seconds() -> None:
    clock = Clock()

    async def source(after: int | None) -> Sequence[rt.StreamEvent]:
        return []

    async def ok() -> bool:
        return True

    async def tick(_s: float) -> None:
        clock.now += 1

    (first,) = await _take(
        rt.stream(
            source, ok, topics=("t",), last_seq=None, expires_at=None, clock=clock, sleep=tick
        ),
        1,
    )
    assert first == b":hb\n\n" and clock.now >= 15
