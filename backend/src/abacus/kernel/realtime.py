"""Server-Sent Events, the kernel half (P-10-T26; ADR-232 proposed; SPEC-647 §3.8; DEC-3116).

Modules own their streams' sources and authorisers; this module owns the wire and the rules every
stream keeps:

- **Framing.** `id:` (the stream's own sequence, so `Last-Event-ID` resumes it), `event:` and one
  `data:` line of JSON. A payload over 64 KB never goes on the wire: the caller sends
  `{id, ref_only: true}` and the client fetches it through REST.
- **Order and resume.** A source answers the events after a cursor in sequence order; the stream
  replays from `Last-Event-ID` first, then tails. A gap older than the source's horizon answers
  one `resync` event and closes.
- **Authorisation lives.** The stream re-checks its authoriser every 60 seconds and whenever it is
  woken for the subscriber (`access.changed`); a refusal sends `locked` and closes.
- **Limits.** A `:hb` comment every 15 seconds; the stream closes 30 seconds before the session's
  token expires; a seventh concurrent stream per user answers 409 `too_many_streams`.
- **Wake-ups.** `notify()` runs `pg_notify` inside the writing transaction (delivered on commit)
  and wakes this process's streams at once; every stream also polls its source each second, so
  a stream in another process is at most a second behind and correct on polling alone. The hub
  never opens a raw connection (ADR-014): it rides the sessions every request already uses.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.errors import DomainConflict

MAX_STREAMS_PER_USER: Final = 6
HEARTBEAT_SECONDS: Final = 15.0
REAUTH_SECONDS: Final = 60.0
POLL_SECONDS: Final = 1.0
CLOSE_BEFORE_EXPIRY_SECONDS: Final = 30.0
MAX_EVENT_BYTES: Final = 64 * 1024
SSE_HEADERS: Final = {
    "Cache-Control": "no-store",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


class TooManyStreams(DomainConflict):
    """A seventh concurrent stream for one person (`facts.limit`)."""

    code = "too_many_streams"


class GapTooOld(Exception):
    """The cursor is older than what the source keeps: the client resyncs through REST."""


@dataclass(frozen=True)
class StreamEvent:
    seq: int
    type: str
    data: dict[str, object]


def frame(event: StreamEvent) -> bytes:
    """One SSE event. A payload over 64 KB is sent by reference (`ref_only`)."""
    body = json.dumps(event.data, separators=(",", ":"), sort_keys=True, default=str)
    if len(body.encode()) > MAX_EVENT_BYTES:
        ref = {"seq": event.seq, "type": event.type, "ref_only": True}
        if "id" in event.data:
            ref["id"] = event.data["id"]
        body = json.dumps(ref, separators=(",", ":"), sort_keys=True, default=str)
    return f"id: {event.seq}\nevent: {event.type}\ndata: {body}\n\n".encode()


def comment(word: str) -> bytes:
    return f":{word}\n\n".encode()


# --- slots and wake-ups (per process) -----------------------------------------------------------

_SLOTS: dict[tuple[UUID, UUID], int] = defaultdict(int)
_WAKE: dict[str, set[asyncio.Event]] = defaultdict(set)


def claim_slot(tenant_id: UUID, user_id: UUID) -> None:
    key = (tenant_id, user_id)
    if _SLOTS[key] >= MAX_STREAMS_PER_USER:
        raise TooManyStreams(facts={"limit": MAX_STREAMS_PER_USER})
    _SLOTS[key] += 1


def release_slot(tenant_id: UUID, user_id: UUID) -> None:
    key = (tenant_id, user_id)
    _SLOTS[key] = max(0, _SLOTS[key] - 1)
    if not _SLOTS[key]:
        del _SLOTS[key]


def wake(topic: str) -> None:
    """Wake this process's streams on `topic` (a write, or `access.changed`)."""
    for event in tuple(_WAKE.get(topic, ())):
        event.set()


async def notify(session: AsyncSession, tenant_id: UUID, topic: str) -> None:
    """Inside the writing transaction: Postgres delivers the NOTIFY on commit, on the tenant's
    channel (0683's `realtime_channel`); this process's streams wake now and re-read."""
    await session.execute(
        text("SELECT pg_notify(realtime_channel(:t), :topic)"),
        {"t": tenant_id, "topic": topic[:120]},
    )
    wake(topic)


Source = Callable[[int | None], Awaitable[Sequence[StreamEvent]]]
Authoriser = Callable[[], Awaitable[bool]]
Clock = Callable[[], float]


async def stream(
    source: Source,
    authorised: Authoriser,
    *,
    topics: Sequence[str],
    last_seq: int | None,
    expires_at: datetime | None,
    clock: Clock = time.monotonic,
    poll_seconds: float = POLL_SECONDS,
    sleep: Callable[[float], Awaitable[object]] | None = None,
) -> AsyncIterator[bytes]:
    """The stream's bytes (module docstring). The caller claimed the slot and releases it."""
    woken = asyncio.Event()
    for topic in topics:
        _WAKE[topic].add(woken)
    cursor = last_seq
    started = clock()
    last_beat = last_auth = started
    deadline = None
    if expires_at is not None:
        left = (expires_at - datetime.now(UTC)).total_seconds() - CLOSE_BEFORE_EXPIRY_SECONDS
        deadline = started + max(0.0, left)
    try:
        while True:
            now = clock()
            if deadline is not None and now >= deadline:
                return
            if now - last_auth >= REAUTH_SECONDS or woken.is_set():
                last_auth = now
                if not await authorised():
                    yield frame(StreamEvent(cursor or 0, "locked", {}))
                    return
            woken.clear()
            try:
                events = await source(cursor)
            except GapTooOld:
                yield frame(StreamEvent(cursor or 0, "resync", {}))
                return
            for event in events:
                yield frame(event)
                cursor = event.seq
            if now - last_beat >= HEARTBEAT_SECONDS:
                last_beat = now
                yield comment("hb")
            if sleep is not None:
                await sleep(poll_seconds)
            else:
                with suppress(TimeoutError):
                    await asyncio.wait_for(woken.wait(), timeout=poll_seconds)
    finally:
        for topic in topics:
            _WAKE[topic].discard(woken)
            if not _WAKE[topic]:
                del _WAKE[topic]


# --- topics: each owner registers who may subscribe (P-10-T27; ADR-232 decision 5) -------------
#
# The slot lives here, not in `notifications`, because nothing may import `notifications` (the
# module graph); `notifications.realtime` reads it. An authorizer answers "content", "metadata"
# (a firm admin's engagement topics: metadata invalidations only, AC-T9) or None (refused).

TopicAccess = Literal["content", "metadata"]
TopicAuthorizer = Callable[[object, str], Awaitable[TopicAccess | None]]
_TOPICS: dict[str, TopicAuthorizer] = {}
TOPIC_KINDS: Final = ("user", "engagement", "work_item", "run", "session", "firm", "portal")


def register_topic(kind: str, authorizer: TopicAuthorizer) -> None:
    if kind not in TOPIC_KINDS:
        raise ValueError(f"unknown topic kind {kind!r}")
    if kind in _TOPICS and _TOPICS[kind] is not authorizer:
        raise ValueError(f"topic kind {kind!r} is already registered")
    _TOPICS[kind] = authorizer


async def authorise_topic(ctx: object, topic: str) -> TopicAccess | None:
    """`<kind>:<id>` through its owner's authorizer; an unknown kind is refused (fail closed)."""
    kind, _, ident = topic.partition(":")
    authorizer = _TOPICS.get(kind)
    if authorizer is None or not ident:
        return None
    try:
        return await authorizer(ctx, ident)
    except Exception:  # an owner that cannot answer refuses
        return None


@dataclass(frozen=True)
class Invalidation:
    """Which topics an outbox event invalidates: the payload's id fields by topic kind."""

    ref_type: str
    ref_field: str
    topic_fields: tuple[tuple[str, str], ...]  # (topic kind, payload field)


_INVALIDATIONS: dict[str, Invalidation] = {}


def register_invalidation(event_type: str, invalidation: Invalidation) -> None:
    _INVALIDATIONS[event_type] = invalidation


def invalidation_of(event_type: str) -> Invalidation | None:
    return _INVALIDATIONS.get(event_type)


def invalidating_events() -> frozenset[str]:
    return frozenset(_INVALIDATIONS)


__all__ = [
    "MAX_STREAMS_PER_USER",
    "SSE_HEADERS",
    "TOPIC_KINDS",
    "GapTooOld",
    "Invalidation",
    "StreamEvent",
    "TooManyStreams",
    "TopicAccess",
    "authorise_topic",
    "claim_slot",
    "comment",
    "frame",
    "invalidating_events",
    "invalidation_of",
    "notify",
    "register_invalidation",
    "register_topic",
    "release_slot",
    "stream",
    "wake",
]
