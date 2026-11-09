"""`GET /v1/events`, the invalidation stream (P-10-T27; ADR-232 proposed; SPEC-647 AC-T9;
DEC-3117).

- **The subscriber** turns each registered outbox event (`kernel.realtime.register_invalidation`)
  into `realtime_events` rows, one per topic the payload names (`engagement:<id>`,
  `work_item:<id>`, `run:<id>`, …): identifiers and enums only, never a value; then it wakes the
  topic (`kernel.realtime.notify`, inside its own transaction).
- **The stream** opens with a `stream` event naming its id, then replays and tails its topics'
  rows after `Last-Event-ID`. Each topic is authorised on add by its owner's authorizer
  (`kernel.realtime.register_topic`); an engagement topic a firm admin holds only as metadata
  carries the `notice` and `locked` events alone (AC-T9). A portal principal may hold only its own
  grant scope's `portal:` topic.
- **Backpressure.** Identical `(type, ref)` within one read coalesce (the 250 ms window: a read
  takes what arrived since the last); more than 500 waiting events answer `resync`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Final, cast
from uuid import UUID, uuid4

from fastapi.responses import StreamingResponse
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY, TEXT

from abacus.kernel import realtime
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainForbidden, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.identity.api import AuthContext

QUEUE_LIMIT: Final = 500
_INSERT = text(
    "INSERT INTO realtime_events (tenant_id, topic, type, ref_type, ref_id) "
    "VALUES (:tenant, :topic, 'invalidate', :ref_type, :ref_id)"
)
_AFTER = text(
    "SELECT seq, topic, type, ref_type, ref_id, version, at FROM realtime_events "
    "WHERE topic = ANY(:topics) AND seq > :after ORDER BY seq LIMIT :limit"
).bindparams(bindparam("topics", type_=ARRAY(TEXT)))
_METADATA_TYPES: Final = frozenset({"notice", "locked", "resync"})


class TopicRefused(DomainForbidden):
    """A topic the caller may not subscribe to (`facts.topic` is the kind only)."""

    code = "topic_not_allowed"


async def on_outbox_event(event: OutboxEvent) -> None:
    """One `realtime_events` row per topic the event names, then a wake per topic."""
    found = realtime.invalidation_of(event.event_type)
    if found is None:
        return
    raw_ref = event.payload.get(found.ref_field)
    ref_id = UUID(str(raw_ref)) if raw_ref else None
    topics = [
        f"{kind}:{event.payload[field]}"
        for kind, field in found.topic_fields
        if event.payload.get(field)
    ]
    if not topics:
        return
    system = TenantContext(event.tenant_id, "system", f"realtime:{event.event_type}")
    async with uow(system) as tx:
        for topic in topics:
            await tx.session.execute(
                _INSERT,
                {
                    "tenant": event.tenant_id,
                    "topic": topic,
                    "ref_type": found.ref_type,
                    "ref_id": ref_id,
                },
            )
            await realtime.notify(tx.session, event.tenant_id, topic)
        tx.record(
            "realtime.invalidated",
            target=Target(found.ref_type, ref_id)
            if ref_id
            else Target("realtime", event.event_id),
            after=Ref(topics=len(topics)),
            scope=Scope(engagement_id=_uuid_or_none(event.payload.get("engagement_id"))),
        )


# --- the stream ----------------------------------------------------------------------------------

_STREAMS: dict[UUID, tuple[UUID, dict[str, realtime.TopicAccess]]] = {}


async def _authorised(ctx: AuthContext, topics: Sequence[str]) -> dict[str, realtime.TopicAccess]:
    held: dict[str, realtime.TopicAccess] = {}
    for topic in topics:
        if ctx.client and not topic.startswith("portal:"):
            raise TopicRefused(facts={"topic": topic.partition(":")[0]})
        access = await realtime.authorise_topic(ctx, topic)
        if access is None:
            raise TopicRefused(facts={"topic": topic.partition(":")[0]})
        held[topic] = access
    return held


def _uuid_or_none(value: object) -> UUID | None:
    return UUID(str(value)) if value else None


def parse_topics(raw: str | None) -> list[str]:
    return sorted({t.strip() for t in (raw or "").split(",") if t.strip()})[:100]


async def events_stream(
    ctx: AuthContext, topics: Sequence[str], last_event_id: int | None
) -> StreamingResponse:
    held = await _authorised(ctx, topics)
    stream_id = uuid4()
    _STREAMS[stream_id] = (ctx.user_id, held)
    opened = False

    async def source(after: int | None) -> Sequence[realtime.StreamEvent]:
        nonlocal opened
        out: list[realtime.StreamEvent] = []
        if not opened:
            opened = True
            out.append(realtime.StreamEvent(after or 0, "stream", {"stream_id": str(stream_id)}))
        current = _STREAMS.get(stream_id, (ctx.user_id, {}))[1]
        if not current:
            return out
        async with tenant_session(ctx.tenant) as session:
            rows = (
                await session.execute(
                    _AFTER,
                    {"topics": list(current), "after": after or 0, "limit": QUEUE_LIMIT + 1},
                )
            ).all()
        if len(rows) > QUEUE_LIMIT:
            raise realtime.GapTooOld  # the client resyncs through REST
        seen: set[tuple[str, str, object]] = set()
        for r in rows:
            if current.get(str(r.topic)) == "metadata" and str(r.type) not in _METADATA_TYPES:
                continue
            key = (str(r.topic), str(r.type), r.ref_id)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                realtime.StreamEvent(
                    int(r.seq),
                    str(r.type),
                    {
                        "seq": int(r.seq),
                        "topic": str(r.topic),
                        "ref_type": r.ref_type,
                        "ref_id": None if r.ref_id is None else str(r.ref_id),
                        "version": r.version,
                        "at": r.at.isoformat(),
                    },
                )
            )
        return out

    async def still_allowed() -> bool:
        current = _STREAMS.get(stream_id, (ctx.user_id, {}))[1]
        for topic in list(current):
            if await realtime.authorise_topic(ctx, topic) is None:
                return False
        return True

    realtime.claim_slot(ctx.tenant_id, ctx.user_id)

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in realtime.stream(
                source,
                still_allowed,
                topics=(*held, f"access:{ctx.user_id}"),
                last_seq=last_event_id,
                expires_at=None,
            ):
                yield chunk
        finally:
            _STREAMS.pop(stream_id, None)
            realtime.release_slot(ctx.tenant_id, ctx.user_id)

    return StreamingResponse(body(), media_type="text/event-stream", headers=realtime.SSE_HEADERS)


async def change_topics(
    ctx: AuthContext, stream_id: UUID, add: Sequence[str], remove: Sequence[str]
) -> list[str]:
    """`POST /v1/events/{id}/topics`: the caller's own open stream only; each added topic is
    authorised now."""
    found = _STREAMS.get(stream_id)
    if found is None or found[0] != ctx.user_id:
        raise NotFound("stream")
    added = await _authorised(ctx, add)
    current = dict(found[1])
    current.update(added)
    for topic in remove:
        current.pop(topic, None)
    _STREAMS[stream_id] = (ctx.user_id, current)
    for topic in added:
        realtime.wake(topic)
    return sorted(current)


# --- the topics notifications answers for itself -------------------------------------------------


async def _user(ctx: object, ident: str) -> realtime.TopicAccess | None:
    return "content" if str(cast(AuthContext, ctx).user_id) == ident else None


async def _firm(ctx: object, ident: str) -> realtime.TopicAccess | None:
    """`firm:home`: any firm member's own Home invalidations (client principals never)."""
    auth = cast(AuthContext, ctx)
    return "content" if ident == "home" and not auth.client else None


def register() -> None:
    realtime.register_topic("user", _user)
    realtime.register_topic("firm", _firm)
    # P-10-T27 AC: a request item's status reaches its engagement and work item topics.
    realtime.register_invalidation(
        "request_item.status_changed",
        realtime.Invalidation(
            "request_item",
            "request_item_id",
            (("engagement", "engagement_id"), ("work_item", "work_item_id")),
        ),
    )
    realtime.register_invalidation(
        "report.released",
        realtime.Invalidation(
            "report_release",
            "release_id",
            (("engagement", "engagement_id"), ("work_item", "work_item_id")),
        ),
    )
    realtime.register_invalidation(
        "notification.created",
        realtime.Invalidation("notification", "notification_id", (("user", "user_id"),)),
    )


__all__ = ["change_topics", "events_stream", "on_outbox_event", "parse_topics", "register"]
