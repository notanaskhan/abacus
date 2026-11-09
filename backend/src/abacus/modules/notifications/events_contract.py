"""C6 v2, the invalidation stream (P-10-T09 stub; P-10 §3.8, §4.3; ADR-232; SPEC-647). Contract:
`docs/contracts/agent-runs.md` §9.

`GET /v1/events` multiplexes identifier-only invalidations: `stream` (its id), `invalidate`,
`notice`, `locked`, `resync` and a `:hb` heartbeat every 15 seconds. Clients refetch through the
typed client. Topics are authorised through `notifications.register_topic`. A seventh stream
answers 409 `too_many_streams`. Off (`realtime.sse`, Jan 27, 2028 train): 404, and clients poll.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")

InvalidationType = Literal["stream", "invalidate", "notice", "locked", "resync"]
Topic = Annotated[str, Field(min_length=1, max_length=120), Internal]


class InvalidationEventOut(BaseModel):
    """Identifiers and enums only (AC-T2). A firm admin's engagement topics carry metadata
    invalidations only (AC-T9)."""

    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, Internal]
    type: Annotated[InvalidationType, Internal]
    topic: Annotated[str | None, Internal] = None
    ref_type: Annotated[str | None, Internal] = None
    ref_id: Annotated[UUID | None, Internal] = None
    version: Annotated[int | None, Internal] = None
    at: Annotated[datetime, Internal]


class StreamTopicsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    add: Annotated[list[Topic], Field(max_length=100), Internal] = Field(default_factory=list[str])
    remove: Annotated[list[Topic], Field(max_length=100), Internal] = Field(
        default_factory=list[str]
    )


class StreamTopicsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    topics: Annotated[list[str], Internal]


events_router = AbacusRouter(prefix="/v1/events", tags=["real time"])


def _not_yet() -> NoReturn:
    raise NotImplementedYet


async def _sse_on(ctx: AuthContext) -> None:
    from abacus.kernel._flags import REALTIME_SSE
    from abacus.kernel.errors import NotFound
    from abacus.kernel.flags import flag_enabled

    if not await flag_enabled(ctx.tenant, REALTIME_SSE):
        raise NotFound(REALTIME_SSE.name)


@events_router.get("", action="events.subscribe", response_model=bytes, errors=(409, 501))
async def events_stream_route(
    ctx: Ctx,
    topics: Annotated[str | None, Query(max_length=2000)] = None,
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID", ge=0)] = None,
) -> Response:
    """`text/event-stream` of `InvalidationEventOut` (P-10-T27, DEC-3117)."""
    from abacus.modules.notifications import realtime as live

    await _sse_on(ctx)
    return await live.events_stream(ctx, live.parse_topics(topics), last_event_id)


@events_router.post(
    "/{stream_id}/topics", action="events.subscribe", response_model=StreamTopicsOut, errors=(501,)
)
async def stream_topics_route(
    stream_id: UUID, body: StreamTopicsIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> StreamTopicsOut:
    """Add or remove topics without reconnecting; each is authorised on add (P-10-T27)."""
    from abacus.modules.notifications import realtime as live

    await _sse_on(ctx)
    del idempotency_key  # the change is a set operation: a repeat changes nothing
    return StreamTopicsOut(topics=await live.change_topics(ctx, stream_id, body.add, body.remove))
