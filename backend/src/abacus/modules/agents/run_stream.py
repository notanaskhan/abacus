"""The run stream and the badge stream (P-10-T26; ADR-232 proposed; SPEC-647 AC-T1, AC-T2;
DEC-3116). PROTECTED (agents).

`GET /v1/agent-runs/{id}/events` replays `run_events` after `Last-Event-ID` (the run's own
`run_seq`), then tails, through `kernel.realtime.stream`: identifiers, enums and verified items
only, and over 64 KB by reference. The run is authorised `agent_run.read` when the stream opens
and again every 60 seconds and on `access.changed`: a wall or a revoked grant sends `locked`. A
cursor older than the oldest kept event (30 days) answers `resync`.

`GET /v1/me/agent-badge` streams the caller's own counts (`running`, `needs_answer`,
`ready_for_review`) whenever they change.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Final, cast
from uuid import UUID

from fastapi.responses import StreamingResponse
from sqlalchemy import text

from abacus.kernel import realtime, request_context
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.agents.runs import authorised_run
from abacus.modules.identity.api import AuthContext, Forbidden

PAGE: Final = 200
_AFTER = text(
    "SELECT run_seq, type, payload FROM run_events WHERE run_id = :run AND run_seq > :after "
    "ORDER BY run_seq LIMIT :page"
)
_OLDEST = text("SELECT min(run_seq) FROM run_events WHERE run_id = :run")
_BADGE = text(
    "SELECT count(*) FILTER (WHERE state IN ('running', 'dispatched', 'queued')) AS running, "
    "count(*) FILTER (WHERE state = 'needs_input') AS needs_answer, "
    "count(*) FILTER (WHERE state = 'awaiting_sign_off') AS ready_for_review "
    "FROM agent_runs WHERE initiator_user_id = :me"
)


def _response(body: AsyncIterator[bytes]) -> StreamingResponse:
    return StreamingResponse(body, media_type="text/event-stream", headers=realtime.SSE_HEADERS)


async def run_events_stream(
    ctx: AuthContext, run_id: UUID, last_event_id: int | None
) -> StreamingResponse:
    await authorised_run(ctx, run_id)  # 404 for a walled, unknown or shadow run

    async def source(after: int | None) -> Sequence[realtime.StreamEvent]:
        async with tenant_session(ctx.tenant) as session:
            if after:
                oldest = await session.scalar(_OLDEST, {"run": run_id})
                if oldest is not None and int(oldest) > after + 1:
                    raise realtime.GapTooOld
            rows = (
                await session.execute(_AFTER, {"run": run_id, "after": after or 0, "page": PAGE})
            ).all()
        return [
            realtime.StreamEvent(
                int(r.run_seq),
                str(r.type),
                {
                    "seq": int(r.run_seq),
                    "run_id": str(run_id),
                    **cast(dict[str, object], r.payload),
                },
            )
            for r in rows
        ]

    async def still_allowed() -> bool:
        try:
            await authorised_run(ctx, run_id)
        except (NotFound, Forbidden):
            return False
        return True

    # P-10-T26: read before the body runs, while the request's context is bound.
    expires = request_context.token_expires_at()
    realtime.claim_slot(ctx.tenant_id, ctx.user_id)

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in realtime.stream(
                source,
                still_allowed,
                topics=(f"run:{run_id}", f"access:{ctx.user_id}"),
                last_seq=last_event_id,
                expires_at=expires,
            ):
                yield chunk
        finally:
            realtime.release_slot(ctx.tenant_id, ctx.user_id)

    return _response(body())


async def badge_stream(ctx: AuthContext) -> StreamingResponse:
    """The caller's own counts; an event only when they change."""
    if ctx.client:
        raise NotFound("agent_badge")
    seen: dict[str, int] = {}
    tick = 0

    async def source(after: int | None) -> Sequence[realtime.StreamEvent]:
        nonlocal tick
        del after
        async with tenant_session(ctx.tenant) as session:
            row = (await session.execute(_BADGE, {"me": ctx.user_id})).one()
        counts = {
            "running": int(row.running),
            "needs_answer": int(row.needs_answer),
            "ready_for_review": int(row.ready_for_review),
        }
        if counts == seen:
            return []
        seen.clear()
        seen.update(counts)
        tick += 1
        return [realtime.StreamEvent(tick, "badge", dict(counts))]

    async def always() -> bool:
        return True

    # P-10-T26: read before the body runs, while the request's context is bound.
    expires = request_context.token_expires_at()
    realtime.claim_slot(ctx.tenant_id, ctx.user_id)

    async def body() -> AsyncIterator[bytes]:
        try:
            async for chunk in realtime.stream(
                source, always, topics=(f"badge:{ctx.user_id}",), last_seq=None, expires_at=expires
            ):
                yield chunk
        finally:
            realtime.release_slot(ctx.tenant_id, ctx.user_id)

    return _response(body())
