"""C6 v2, the sessions half (P-10-T09 stub; P-10 §4.3; ADR-235; SPEC-647). Contract:
`docs/contracts/agent-runs.md` §9. List, create, rename and delete are W-02's.

A session is the thread view of one or more runs. A client a viewer can't open answers
`locked: true` with no figures; a walled client's session is omitted (DEC-87). Every route answers
the matrix action, then 501 until T26 and T43. Flags arrive on the Jan 27, 2028 train.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
Restricted = classified("restricted")

SessionOrigin = Literal["manual", "schedule", "trigger", "test", "saved_prompt", "engagement_run"]
SessionState = Literal[
    "live", "running", "awaiting_answer", "ready_for_review", "complete", "failed"
]
SessionItemKind = Literal[
    "user_message", "agent_blocks", "plan", "question", "answer", "tool_card", "artifact", "notice"
]
SessionActorKind = Literal["human", "agent", "system"]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


class SessionItemOut(BaseModel):
    """One insert-only entry. `payload` has `v` (its schema version) and holds a verified item."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    seq: Annotated[int, Internal]
    kind: Annotated[SessionItemKind, Internal]
    payload: Annotated[dict[str, object], Confidential]  # Any: schema-versioned by `v`
    run_id: Annotated[UUID | None, Internal] = None
    step_id: Annotated[UUID | None, Internal] = None
    actor_kind: Annotated[SessionActorKind, Internal]
    actor_name: Annotated[str | None, Confidential] = None
    created_at: Annotated[datetime, Internal]


class SessionSnapshotOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    origin: Annotated[SessionOrigin, Internal]
    state: Annotated[SessionState, Internal]
    locked: Annotated[bool, Internal] = False
    last_item_at: Annotated[datetime | None, Internal] = None
    items: Annotated[list[SessionItemOut], Confidential]
    allowed_actions: Annotated[list[Literal["message", "manage"]], Internal]


class SessionMessageIn(BaseModel):
    """A question open: this is answered first and the question stays open (AC-S2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Annotated[str, Field(min_length=1, max_length=8000), Restricted]


class SessionMessageAcceptedOut(BaseModel):
    model_config = _frozen()

    item_id: Annotated[UUID, Internal]
    run_id: Annotated[UUID | None, Internal] = None
    status_url: Annotated[str, Internal]


sessions_router = AbacusRouter(prefix="/v1/workbench/sessions", tags=["workbench sessions"])
agent_badge_router = AbacusRouter(prefix="/v1/me/agent-events", tags=["workbench sessions"])


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@sessions_router.get(
    "/{session_id}", action="session.read", response_model=SessionSnapshotOut, errors=(501,)
)
async def get_session_route(session_id: UUID, ctx: Ctx) -> SessionSnapshotOut:
    _not_yet()


@sessions_router.post(
    "/{session_id}/messages",
    action="session.create",
    response_model=SessionMessageAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def post_session_message_route(
    session_id: UUID, body: SessionMessageIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SessionMessageAcceptedOut:
    """A write-proposing turn starts exactly one child run in `awaiting_plan_approval` (AC-S4)."""
    _not_yet()


@sessions_router.get(
    "/{session_id}/events", action="session.read", response_model=bytes, errors=(501,)
)
async def session_events_route(
    session_id: UUID,
    ctx: Ctx,
    last_event_id: Annotated[int | None, Header(alias="Last-Event-ID", ge=0)] = None,
) -> Response:
    """`text/event-stream` of `RunEventOut`, keyed by `session_seq` (T26)."""
    _not_yet()


@agent_badge_router.get("", action="session.read", response_model=bytes, errors=(501,))
async def agent_badge_events_route(ctx: Ctx) -> Response:
    """`text/event-stream` of the caller's badge counts `{running, needs_answer,
    ready_for_review}` (P-10-T26, DEC-3116)."""
    from abacus.kernel._flags import REALTIME_SSE
    from abacus.kernel.errors import NotFound
    from abacus.kernel.flags import flag_enabled
    from abacus.modules.agents.api import agent_badge_stream

    if not await flag_enabled(ctx.tenant, REALTIME_SSE):
        raise NotFound(REALTIME_SSE.name)
    return await agent_badge_stream(ctx)
