"""C6 v2, the sessions half (P-10-T09 stub; P-10 §4.3; ADR-235; SPEC-647). Contract:
`docs/contracts/agent-runs.md` §9. List, create, rename and delete are W-02's.

A session is the thread view of one or more runs. A client a viewer can't open answers
`locked: true` with no figures; a walled client's session is omitted (DEC-87). The snapshot and
the message post are P-10-T43's (`sessions.py`); the session stream answers 501 until T26's.
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
    # P-10-T43 (DEC-4301): the open question's item this answers; without it the body is a
    # message (answered first, the question stays open).
    answers_seq: Annotated[int | None, Field(ge=1), Internal] = None


class SessionMessageAcceptedOut(BaseModel):
    model_config = _frozen()

    item_id: Annotated[UUID, Internal]
    run_id: Annotated[UUID | None, Internal] = None
    status_url: Annotated[str, Internal]


class SessionSubjectRefIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[str, Field(pattern=r"^[a-z_]{1,40}$"), Internal]
    id: Annotated[UUID, Internal]


class SessionCreateIn(BaseModel):
    """T-04-T37 (DEC-4316): a session bound to one record (`tax_return` for TAX-08); the
    record's owner authorises the person and names the capability. W-02 adds unbound sessions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_ref: Annotated[SessionSubjectRefIn, Internal]  # a kind and an id
    title: Annotated[str, Field(min_length=1, max_length=200), Confidential] = "Assistant"


class SessionSummaryOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    state: Annotated[SessionState, Internal]
    last_item_at: Annotated[datetime | None, Internal] = None


class SessionListOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[SessionSummaryOut], Confidential]


sessions_router = AbacusRouter(prefix="/v1/workbench/sessions", tags=["workbench sessions"])


@sessions_router.post(
    "", action="session.create", response_model=SessionSummaryOut, status_code=201, errors=(409,)
)
async def create_session_route(body: SessionCreateIn, ctx: Ctx) -> SessionSummaryOut:
    """409 `capability_unavailable` with `facts.reason` (consent_7216, ai_excluded, paused, …):
    TAX-08's agents-off state; nothing is opened and no model is called (DF-04)."""
    from abacus.modules.workbench.sessions import open_subject_session

    session_id = await open_subject_session(
        ctx, body.subject_ref.kind, body.subject_ref.id, body.title
    )
    return SessionSummaryOut(id=session_id, title=body.title, state="live")


@sessions_router.get("", action="session.read", response_model=SessionListOut)
async def list_sessions_route(
    ctx: Ctx, subject_ref: Annotated[str, Query(pattern=r"^[a-z_]{1,40}:[0-9a-f-]{36}$")]
) -> SessionListOut:
    """The person's own sessions on one record (TAX-08 History), newest first."""
    from abacus.modules.workbench.sessions import subject_sessions

    kind, _, ident = subject_ref.partition(":")
    rows = await subject_sessions(ctx, kind, UUID(ident))
    return SessionListOut(
        items=[
            SessionSummaryOut(
                id=r.id,
                title=r.title,
                state=r.state,  # type: ignore[arg-type]  # the table's CHECK holds the literal
                last_item_at=r.last_item_at,
            )
            for r in rows
        ]
    )


agent_badge_router = AbacusRouter(prefix="/v1/me/agent-events", tags=["workbench sessions"])


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@sessions_router.get(
    "/{session_id}", action="session.read", response_model=SessionSnapshotOut, errors=(501,)
)
async def get_session_route(session_id: UUID, ctx: Ctx) -> SessionSnapshotOut:
    from abacus.modules.workbench.sessions import get_session

    view = await get_session(ctx, session_id)
    return SessionSnapshotOut(
        id=view.row.id,
        title=view.row.title,
        origin=view.row.origin,  # type: ignore[arg-type]  # the table's CHECK holds the literal
        state=view.row.state,  # type: ignore[arg-type]  # the table's CHECK holds the literal
        locked=view.locked,
        last_item_at=view.row.last_item_at,
        items=[
            SessionItemOut(
                id=i.id,
                seq=i.seq,
                kind=i.kind,  # type: ignore[arg-type]  # the table's CHECK holds the literal
                payload=i.payload,
                run_id=i.run_id,
                step_id=i.step_id,
                actor_kind=i.actor_kind,  # type: ignore[arg-type]  # the table's CHECK
                actor_name=i.actor_name,
                created_at=i.created_at,
            )
            for i in view.items
        ],
        allowed_actions=view.allowed_actions,  # type: ignore[arg-type]  # message, manage
    )


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
    from abacus.modules.workbench.sessions import post_message

    posted = await post_message(ctx, session_id, body.body, idempotency_key, body.answers_seq)
    return SessionMessageAcceptedOut(
        item_id=posted.item_id,
        run_id=posted.run_id,
        status_url=f"/v1/workbench/sessions/{session_id}",
    )


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
