"""C6 v2, the sessions half (P-10-T09 stub; P-10 §4.3; ADR-235; SPEC-647). Contract:
`docs/contracts/agent-runs.md` §9. List, create, rename and delete are W-02's.

A session is the thread view of one or more runs. A client a viewer can't open answers
`locked: true` with no figures; a walled client's session is omitted (DEC-87). The snapshot and
the message post are P-10-T43's (`sessions.py`); the session stream answers 501 until T26's.

W-02-T02 (SPEC-653; DEC-4604) extends both routes additively: the list answers the filtered,
P-36-enveloped Workbench list when no `subject_ref` is given, and create accepts an empty body
(a blank firm-wide session). Both W-02 paths sit behind `workbench.enabled` (off: 404) and answer
501 until W-02-T09; the TAX-08 subject paths are unchanged. The rest of the family (rename,
delete, context) is `list_contract.py`'s.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

if TYPE_CHECKING:
    from abacus.modules.workbench.session_list import Row

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
Restricted = classified("restricted")

SessionOrigin = Literal["manual", "schedule", "trigger", "test", "saved_prompt", "engagement_run"]
SessionState = Literal[
    "live", "running", "awaiting_answer", "ready_for_review", "complete", "failed"
]
# I-02-T17 (DEC-4938, additive): the kinds in W-02-T06 (context and drill items) read
# back too; without them a session with attached context or a drill could not be read.
SessionItemKind = Literal[
    "user_message",
    "agent_blocks",
    "plan",
    "question",
    "answer",
    "tool_card",
    "artifact",
    "notice",
    "context_added",
    "context_removed",
    "drill",
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
    # W-02-T15 (DEC-4913), additive: edit-and-resend names the person's earlier message it
    # replaces; the new message is a new turn and the earlier items stay.
    edits_seq: Annotated[int | None, Field(ge=1), Internal] = None


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
    record's owner authorises the person and names the capability. W-02-T02: no `subject_ref` is
    a blank session with the context `firm_wide` and the title "New session" until the first
    message names it (AC-C1, AC-L6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    subject_ref: Annotated[SessionSubjectRefIn | None, Internal] = None  # a kind and an id
    title: Annotated[str, Field(min_length=1, max_length=200), Confidential] = "Assistant"


SessionListFilter = Literal["all", "mine", "via_agent", "running", "needs_answer"]


class SessionOwnerOut(BaseModel):
    """Who a row is attributed to. `via_agent` rows read "<person> via Agent" through
    `formatActor` (INV-5); the agent is never an owner."""

    model_config = _frozen()

    user_id: Annotated[UUID | None, Internal] = None
    name: Annotated[str, Confidential]
    via_agent: Annotated[bool, Internal] = False


class SessionSummaryOut(BaseModel):
    """One list row. W-02-T02 adds the WB-01 fields; the TAX-08 subject list leaves them at
    their defaults. A `locked` row carries metadata only (DEC-87): no thread item, figure or
    count."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    state: Annotated[SessionState, Internal]
    last_item_at: Annotated[datetime | None, Internal] = None
    owner: Annotated[SessionOwnerOut | None, Confidential] = None
    origin: Annotated[SessionOrigin | None, Internal] = None
    # The definition's name on a via-Agent row ("Season Progress Reporter"), resolved at read.
    agent_label: Annotated[str | None, Confidential] = None
    needs_answer: Annotated[bool, Internal] = False
    running: Annotated[bool, Internal] = False
    ready_for_review: Annotated[bool, Internal] = False
    locked: Annotated[bool, Internal] = False
    title_source: Annotated[Literal["auto", "manual"] | None, Internal] = None
    # The row's version for `If-Match` on rename (W-02-T09).
    version: Annotated[str | None, Field(max_length=40), Internal] = None
    # W-02-T14 rest (TASK-7927): the Paperclip chip's count of attached context items; None on a
    # locked row (metadata only, DEC-87) and on the TAX-08 subject list.
    context_count: Annotated[int | None, Field(ge=0), Internal] = None


class SessionListCountsOut(BaseModel):
    """The filter menu's counts over the viewer's rows; walled rows are never counted and no
    "n hidden" figure exists anywhere (DEC-43)."""

    model_config = _frozen()

    running: Annotated[int, Field(ge=0), Internal] = 0
    needs_answer: Annotated[int, Field(ge=0), Internal] = 0


class SessionListOut(BaseModel):
    """The P-36 envelope's fields W-02 uses; additive to the TAX-08 shape (items only)."""

    model_config = _frozen()

    items: Annotated[list[SessionSummaryOut], Confidential]
    next_cursor: Annotated[str | None, Internal] = None
    total: Annotated[int, Field(ge=0), Internal] = 0
    counts: Annotated[SessionListCountsOut | None, Internal] = None


sessions_router = AbacusRouter(prefix="/v1/workbench/sessions", tags=["workbench sessions"])


def summary_of(r: Row) -> SessionSummaryOut:
    """W-02-T09: one list row; a locked row keeps metadata only (no thread, figure or count)."""
    return SessionSummaryOut(
        id=r.id,
        title=r.title,
        state=r.state,  # type: ignore[arg-type]  # the table's CHECK holds the literal
        last_item_at=r.last_item_at,
        owner=SessionOwnerOut(user_id=r.owner_user_id, name=r.owner_name, via_agent=r.via_agent),
        origin=r.origin,  # type: ignore[arg-type] -- the run's context reads as its initiator
        needs_answer=r.needs_answer and not r.locked,
        running=r.running,
        ready_for_review=r.ready_for_review and not r.locked,
        locked=r.locked,
        title_source=r.title_source,  # type: ignore[arg-type] -- the run's context reads as its initiator
        version=r.version,
        context_count=None if r.locked else r.context_count,
    )


async def workbench_gate(ctx: AuthContext) -> None:
    """`workbench.enabled` off: 404 named after the flag (the repository's answer)."""
    from abacus.kernel._flags import WORKBENCH_ENABLED
    from abacus.kernel.errors import NotFound
    from abacus.kernel.flags import flag_enabled

    if not await flag_enabled(ctx.tenant, WORKBENCH_ENABLED):
        raise NotFound(WORKBENCH_ENABLED.name)


@sessions_router.post(
    "",
    action="session.create",
    response_model=SessionSummaryOut,
    status_code=201,
    errors=(409, 501),
)
async def create_session_route(body: SessionCreateIn, ctx: Ctx) -> SessionSummaryOut:
    """409 `capability_unavailable` with `facts.reason` (consent_7216, ai_excluded, paused, …):
    TAX-08's agents-off state; nothing is opened and no model is called (DF-04). No
    `subject_ref`: a blank Workbench session (W-02-T09; 404 behind `workbench.enabled`)."""
    from abacus.modules.workbench.sessions import open_subject_session

    if body.subject_ref is None:
        from abacus.modules.workbench.session_list import NEW_TITLE, create_blank

        await workbench_gate(ctx)
        created = await create_blank(ctx)
        return SessionSummaryOut(
            id=created, title=NEW_TITLE, state="live", title_source="auto", origin="manual"
        )

    session_id = await open_subject_session(
        ctx, body.subject_ref.kind, body.subject_ref.id, body.title
    )
    return SessionSummaryOut(id=session_id, title=body.title, state="live")


@sessions_router.get("", action="session.read", response_model=SessionListOut)
async def list_sessions_route(
    ctx: Ctx,
    subject_ref: Annotated[str | None, Query(pattern=r"^[a-z_]{1,40}:[0-9a-f-]{36}$")] = None,
    filter: Annotated[SessionListFilter, Query()] = "all",
    q: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> SessionListOut:
    """With `subject_ref`: the person's own sessions on one record (TAX-08 History), newest
    first. Without: WB-01's list under DEC-87 membership (DEC-4601), filtered, searched by title
    only (never thread content), with the filter counts (W-02-T09; 404 behind
    `workbench.enabled`)."""
    from abacus.modules.workbench.sessions import subject_sessions

    if subject_ref is None:
        from abacus.modules.workbench.session_list import list_sessions

        await workbench_gate(ctx)
        listed = await list_sessions(ctx, filter, q, cursor)
        return SessionListOut(
            items=[summary_of(r) for r in listed.rows],
            next_cursor=listed.next_cursor,
            total=listed.total,
            counts=SessionListCountsOut(running=listed.running, needs_answer=listed.needs_answer),
        )

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

    posted = await post_message(
        ctx, session_id, body.body, idempotency_key, body.answers_seq, edits_seq=body.edits_seq
    )
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
