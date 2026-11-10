"""Comments v2 and to-dos, contract stub (P-05-T03; TASK-6504; SPEC-650; P-05 §4.3; DEC-3104).
Contract: `docs/contracts/collaboration.md`.

Every route declares exactly one matrix action (P-05-T02's rows, and the live `comment.*` rows in
requests.yaml) and answers 501 until its build row (comments P-05-T05, to-dos P-05-T06). Each first
refuses a client principal (404: P-05 registers no client-visible anchor, INV-4) and then checks
`collaboration.v2` (off: 404). Comment bodies, to-do row text and redaction reasons are classified;
bodies are Restricted (ADR-031, ADR-236 decision 8) and never leave as a log line, an event or a
notification. The agent holds none of these actions (INV-1).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import COLLABORATION_V2
from abacus.kernel._statuses import CommentThreadStatus, TodoStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")
Confidential = classified("confidential")
Restricted = classified("restricted")

# `workpaper` and `todo` register in P-05 (T09, T06); later epics add their own kinds. A kind is a
# lower-case identifier; the provider registry decides whether it exists (409 otherwise).
AnchorKind = Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")]
Visibility = Literal["internal", "shared"]
AuthorSide = Literal["firm", "client"]
TodoScope = Literal["engagement", "firm"]
DueBucket = Literal["overdue", "today", "this_week", "later", "no_date"]
CandidateReason = Literal["not_on_engagement"]
ThreadAction = Literal[
    "comment.create",
    "comment.resolve",
    "comment.share",
    "comment.redact",
    "review_note.raise",
    "todo.create",
]
TodoAction = Literal[
    "todo.update", "todo.complete", "todo.assign", "todo.delete", "comment.create"
]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- shared --------------------------------------------------------------------------------------


class AnchorRef(BaseModel):
    """What a thread or a to-do is on: the kind, the record and, for a row or a cell, where in it.
    The provider validates the locator against its schema (P-05-T05)."""

    model_config = _strict()

    anchor_kind: Annotated[AnchorKind, Internal]
    anchor_id: Annotated[UUID, Internal]
    # e.g. {"sheet": "Exceptions", "cell": "A3"}: identifiers and positions, never row text.
    locator: Annotated[dict[str, str | int] | None, Internal] = None


class PersonRefOut(BaseModel):
    """A person as the UI names them; `initials` for the avatar. Never the agent."""

    model_config = _frozen()

    user_id: Annotated[UUID, Internal]
    name: Annotated[str, Confidential]
    initials: Annotated[str, Field(max_length=3), Confidential]


class AnchorFactsOut(BaseModel):
    """The anchor as its provider reports it at read time (label resolved, never stored)."""

    model_config = _frozen()

    anchor_kind: Annotated[AnchorKind, Internal]
    anchor_id: Annotated[UUID, Internal]
    locator: Annotated[dict[str, str | int] | None, Internal] = None
    label: Annotated[str, Confidential]  # "Northwind · Exceptions row 6"
    engagement_id: Annotated[UUID | None, Internal] = None
    client_visible: Annotated[bool, Internal] = False


# --- comments v2 ---------------------------------------------------------------------------------


class ThreadRedactionOut(BaseModel):
    """The redaction stub every reader sees in the comment's place; the sealed body is kept and
    never returned."""

    model_config = _frozen()

    redacted_by: Annotated[PersonRefOut, Internal]
    redacted_at: Annotated[datetime, Internal]
    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class ThreadCommentOut(BaseModel):
    """One comment. `body` is null when redacted; a correction names what it corrects."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    author: Annotated[PersonRefOut, Internal]
    author_side: Annotated[AuthorSide, Internal]
    body: Annotated[str | None, Restricted] = None
    corrects_comment_id: Annotated[UUID | None, Internal] = None
    corrected_by_comment_id: Annotated[UUID | None, Internal] = None  # "Corrected below"
    mentioned_user_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])
    citation_ids: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])  # C4
    redaction: Annotated[ThreadRedactionOut | None, Internal] = None
    created_at: Annotated[datetime, Internal]


class ThreadEventOut(BaseModel):
    """A thread event (append-only): who resolved, reopened, shared or converted it, and when."""

    model_config = _frozen()

    kind: Annotated[
        Literal[
            "opened", "resolved", "reopened", "muted", "unmuted", "converted", "shared", "unshared"
        ],
        Internal,
    ]
    actor: Annotated[PersonRefOut, Internal]
    ref_type: Annotated[Literal["todo", "review_note"] | None, Internal] = None
    ref_id: Annotated[UUID | None, Internal] = None
    created_at: Annotated[datetime, Internal]


class ThreadOut(BaseModel):
    """A thread with its comments, newest last, and what the reader may do on it."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    anchor: Annotated[AnchorFactsOut, Internal]
    engagement_id: Annotated[UUID, Internal]
    status: Annotated[CommentThreadStatus, Internal]
    visibility: Annotated[Visibility, Internal]
    opened_on_version_no: Annotated[int | None, Internal] = None
    pinned_version_no: Annotated[int | None, Internal] = None
    comment_count: Annotated[int, Field(ge=0), Internal]
    unread: Annotated[bool, Internal] = False
    muted: Annotated[bool, Internal] = False
    last_comment_at: Annotated[datetime | None, Internal] = None
    comments: Annotated[list[ThreadCommentOut], Internal] = Field(
        default_factory=list[ThreadCommentOut]
    )
    events: Annotated[list[ThreadEventOut], Internal] = Field(default_factory=list[ThreadEventOut])
    allowed_actions: Annotated[list[ThreadAction], Internal] = Field(
        default_factory=list[ThreadAction]
    )


class ThreadPageOut(ListPage[ThreadOut]):
    """The P-36 envelope; `counts` holds `open` and `resolved` for the anchor (SHL-18d)."""


class AnchorCountsIn(BaseModel):
    """Up to 200 anchors for the C-27 chips on one screen."""

    model_config = _strict()

    anchors: Annotated[list[AnchorRef], Field(min_length=1, max_length=200), Internal]


class ThreadCountOut(BaseModel):
    model_config = _frozen()

    anchor: Annotated[AnchorRef, Internal]
    open: Annotated[int, Field(ge=0), Internal]
    resolved: Annotated[int, Field(ge=0), Internal]
    unread: Annotated[int, Field(ge=0), Internal]


class ThreadCountsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[ThreadCountOut], Internal]


class ThreadCommentBodyIn(BaseModel):
    """A comment's text and who it mentions. Length and emptiness are the service's fixed codes
    (`empty_comment`, `comment_too_long` over 4,000), so the model does not bound them."""

    model_config = _strict()

    body: Annotated[str, Field(max_length=20_000), Restricted]
    mention_user_ids: Annotated[list[UUID], Field(max_length=50), Internal] = Field(
        default_factory=list[UUID]
    )
    mention_team: Annotated[bool, Internal] = False  # "@Northwind PY2025 team"
    citation_ids: Annotated[list[UUID], Field(max_length=20), Internal] = Field(
        default_factory=list[UUID]
    )


class ThreadOpenIn(ThreadCommentBodyIn):
    """Open a thread on an anchor with its first comment."""

    anchor: Annotated[AnchorRef, Internal]


class CommentPostIn(ThreadCommentBodyIn):
    """A reply; `corrects_comment_id` makes it the author's Correct… (DF-18)."""

    corrects_comment_id: Annotated[UUID | None, Internal] = None


class CommentPostedOut(BaseModel):
    """The thread after the post, and who was notified (the delivery line, AC-7)."""

    model_config = _frozen()

    thread: Annotated[ThreadOut, Internal]
    comment_id: Annotated[UUID, Internal]
    notified: Annotated[list[PersonRefOut], Internal] = Field(default_factory=list[PersonRefOut])
    notified_by_email: Annotated[list[UUID], Internal] = Field(default_factory=list[UUID])


class ThreadRedactIn(BaseModel):
    model_config = _strict()

    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class ThreadMuteIn(BaseModel):
    model_config = _strict()

    muted: Annotated[bool, Internal]


class ThreadShareIn(BaseModel):
    """Share with a grant scope (C5); only on a client-visible anchor (409 otherwise)."""

    model_config = _strict()

    scope_kind: Annotated[str, Field(min_length=1, max_length=40), Internal]
    scope_id: Annotated[UUID, Internal]


class ConvertedOut(BaseModel):
    model_config = _frozen()

    thread: Annotated[ThreadOut, Internal]
    review_note_id: Annotated[UUID, Internal]


class PersonCandidateOut(BaseModel):
    """A mention or assignee candidate; a non-member is listed greyed, never a walled person."""

    model_config = _frozen()

    user_id: Annotated[UUID, Internal]
    name: Annotated[str, Confidential]
    initials: Annotated[str, Field(max_length=3), Confidential]
    title: Annotated[str | None, Confidential] = None  # "Audit Senior Manager"
    is_self: Annotated[bool, Internal] = False
    selectable: Annotated[bool, Internal] = True
    reason: Annotated[CandidateReason | None, Internal] = None


class TeamEntryOut(BaseModel):
    model_config = _frozen()

    label: Annotated[str, Confidential]  # "Northwind PY2025 team"
    member_count: Annotated[int, Field(ge=0), Internal]


class MentionCandidatesOut(BaseModel):
    model_config = _frozen()

    team: Annotated[TeamEntryOut | None, Internal] = None
    members: Annotated[list[PersonCandidateOut], Internal]
    not_on_engagement: Annotated[list[PersonCandidateOut], Internal] = Field(
        default_factory=list[PersonCandidateOut]
    )


class AssigneeCandidatesOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[PersonCandidateOut], Internal]


# --- to-dos --------------------------------------------------------------------------------------


class TodoChecklistItemOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    position: Annotated[int, Field(ge=1, le=8), Internal]
    text: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    done: Annotated[bool, Internal]
    done_by: Annotated[PersonRefOut | None, Internal] = None
    done_at: Annotated[datetime | None, Internal] = None


class TodoOut(BaseModel):
    """A to-do. `overdue` is derived at read time in the firm's time zone, never stored (AC-23)."""

    model_config = _frozen()

    id: Annotated[UUID, Internal]
    scope_kind: Annotated[TodoScope, Internal]
    engagement_id: Annotated[UUID | None, Internal] = None
    title: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    status: Annotated[TodoStatus, Internal]
    overdue: Annotated[bool, Internal] = False
    bucket: Annotated[DueBucket | None, Internal] = None
    assignee: Annotated[PersonRefOut, Internal]
    created_by: Annotated[PersonRefOut, Internal]
    created_at: Annotated[datetime, Internal]
    due_on: Annotated[date | None, Internal] = None
    anchor: Annotated[AnchorFactsOut | None, Internal] = None
    row_text: Annotated[str | None, Restricted] = None  # the row's text when the to-do was made
    source_thread_id: Annotated[UUID | None, Internal] = None
    done_by: Annotated[PersonRefOut | None, Internal] = None
    done_at: Annotated[datetime | None, Internal] = None
    unread: Annotated[bool, Internal] = False  # the assignee has not opened it
    checklist: Annotated[list[TodoChecklistItemOut], Field(max_length=8), Internal] = Field(
        default_factory=list[TodoChecklistItemOut]
    )
    comment_count: Annotated[int, Field(ge=0), Internal] = 0
    version: Annotated[int, Field(ge=1), Internal]
    allowed_actions: Annotated[list[TodoAction], Internal] = Field(
        default_factory=list[TodoAction]
    )


class TodoPageOut(ListPage[TodoOut]):
    """The P-36 envelope; for `assignee=me`, `counts` holds `overdue`, `today`, `this_week`,
    `later` and `no_date` in the firm's time zone (AC-29), and `open` and `done`."""


class TodoCreateIn(BaseModel):
    model_config = _strict()

    scope_kind: Annotated[TodoScope, Internal] = "engagement"
    engagement_id: Annotated[UUID | None, Internal] = None
    title: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    assignee_user_id: Annotated[UUID, Internal]
    due_on: Annotated[date | None, Internal] = None
    anchor: Annotated[AnchorRef | None, Internal] = None
    checklist: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=200)]],
        Field(max_length=8),
        Confidential,
    ] = Field(default_factory=list[str])
    source_thread_id: Annotated[UUID | None, Internal] = None


class TodoPatchIn(BaseModel):
    """Autosave: title and due date, under `If-Match: <version>` (409 `stale_version`)."""

    model_config = _strict()

    title: Annotated[str | None, Field(min_length=1, max_length=200), Confidential] = None
    due_on: Annotated[date | None, Internal] = None
    clear_due_on: Annotated[bool, Internal] = False


class TodoAssignIn(BaseModel):
    model_config = _strict()

    assignee_user_id: Annotated[UUID, Internal]


class TodoMoveIn(BaseModel):
    """Re-anchor within the same engagement (422 `anchor_scope_mismatch` otherwise)."""

    model_config = _strict()

    anchor: Annotated[AnchorRef, Internal]


class TodoChecklistItemIn(BaseModel):
    model_config = _strict()

    text: Annotated[str, Field(min_length=1, max_length=200), Confidential]


class TodoChecklistItemPatchIn(BaseModel):
    model_config = _strict()

    text: Annotated[str | None, Field(min_length=1, max_length=200), Confidential] = None
    done: Annotated[bool | None, Internal] = None


class TodoCountOut(BaseModel):
    model_config = _frozen()

    anchor: Annotated[AnchorRef, Internal]
    open: Annotated[int, Field(ge=0), Internal]


class TodoCountsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[TodoCountOut], Internal]


# --- routes --------------------------------------------------------------------------------------


async def _gate(ctx: AuthContext) -> None:
    """A firm person only (no anchor in P-05 is client-visible), then the flag."""
    if ctx.client:
        raise NotFound("comment_thread")
    if not await flag_enabled(ctx.tenant, COLLABORATION_V2):
        raise NotFound(COLLABORATION_V2.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


Key = Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)]
IfMatch = Annotated[str | None, Header(alias="If-Match", max_length=20)]
Locator = Annotated[str | None, Query(max_length=200)]

threads_router = AbacusRouter(prefix="/v1", tags=["collaboration"])
_T = "/comment-threads/{thread_id}"


@threads_router.get(
    "/comment-threads", action="comment.read", response_model=ThreadPageOut, errors=(409, 501)
)
async def list_comment_threads_route(
    ctx: Ctx,
    anchor_kind: Annotated[AnchorKind, Query()],
    anchor_id: Annotated[UUID, Query()],
    locator: Locator = None,
    status: Annotated[CommentThreadStatus | None, Query()] = None,
) -> ThreadPageOut:
    """Threads and comments for one anchor (internal threads never to a client principal)."""
    await _gate(ctx)
    _not_yet()


@threads_router.post(
    "/comment-threads/counts", action="comment.read", response_model=ThreadCountsOut, errors=(501,)
)
async def thread_counts_route(body: AnchorCountsIn, ctx: Ctx) -> ThreadCountsOut:
    await _gate(ctx)
    _not_yet()


@threads_router.post(
    "/comment-threads",
    action="comment.create",
    response_model=CommentPostedOut,
    status_code=201,
    errors=(409, 501),
)
async def open_thread_route(body: ThreadOpenIn, ctx: Ctx, key: Key = None) -> CommentPostedOut:
    """409 `anchor_kind_not_registered`; 422 `empty_comment`, `comment_too_long`,
    `mention_not_allowed`."""
    await _gate(ctx)
    _not_yet()


@threads_router.post(
    f"{_T}/comments",
    action="comment.create",
    response_model=CommentPostedOut,
    status_code=201,
    errors=(409, 501),
)
async def post_comment_route(
    thread_id: UUID, body: CommentPostIn, ctx: Ctx, key: Key = None
) -> CommentPostedOut:
    """A reply, or the author's correction (422 `correction_not_allowed` for anyone else)."""
    await _gate(ctx)
    _not_yet()


@threads_router.post(
    "/thread-comments/{comment_id}/redact",
    action="comment.redact",
    response_model=ThreadCommentOut,
    errors=(409, 501),
)
async def redact_thread_comment_route(
    comment_id: UUID, body: ThreadRedactIn, ctx: Ctx, key: Key = None
) -> ThreadCommentOut:
    """Firm admin with a fresh MFA (matrix); 409 `already_redacted`."""
    await _gate(ctx)
    _not_yet()


@threads_router.post(
    f"{_T}/resolve", action="comment.resolve", response_model=ThreadOut, errors=(409, 501)
)
async def resolve_thread_route(thread_id: UUID, ctx: Ctx, key: Key = None) -> ThreadOut:
    """A `resolved` thread event (409 `thread_already_resolved`)."""
    await _gate(ctx)
    _not_yet()


@threads_router.post(
    f"{_T}/reopen", action="comment.resolve", response_model=ThreadOut, errors=(409, 501)
)
async def reopen_thread_route(thread_id: UUID, ctx: Ctx, key: Key = None) -> ThreadOut:
    await _gate(ctx)
    _not_yet()


@threads_router.post(f"{_T}/mute", action="comment.read", response_model=ThreadOut, errors=(501,))
async def mute_thread_route(thread_id: UUID, body: ThreadMuteIn, ctx: Ctx) -> ThreadOut:
    await _gate(ctx)
    _not_yet()


@threads_router.post(f"{_T}/read", action="comment.read", response_model=ThreadOut, errors=(501,))
async def read_thread_route(thread_id: UUID, ctx: Ctx) -> ThreadOut:
    await _gate(ctx)
    _not_yet()


@threads_router.post(
    f"{_T}/share", action="comment.share", response_model=ThreadOut, errors=(409, 501)
)
async def share_thread_route(
    thread_id: UUID, body: ThreadShareIn, ctx: Ctx, key: Key = None
) -> ThreadOut:
    """409 `anchor_not_shareable` for every anchor P-05 registers."""
    await _gate(ctx)
    _not_yet()


@threads_router.post(
    f"{_T}/convert-to-review-note",
    action="review_note.raise",
    response_model=ConvertedOut,
    status_code=201,
    errors=(409, 501),
)
async def convert_to_review_note_route(thread_id: UUID, ctx: Ctx, key: Key = None) -> ConvertedOut:
    """Raises an open AUD-17 note through C3 in the same unit of work (P-05-T09)."""
    await _gate(ctx)
    _not_yet()


@threads_router.get(
    "/engagements/{engagement_id}/mention-candidates",
    action="comment.create",
    response_model=MentionCandidatesOut,
    errors=(501,),
)
async def thread_mention_candidates_route(
    engagement_id: UUID, ctx: Ctx, q: Annotated[str | None, Query(max_length=60)] = None
) -> MentionCandidatesOut:
    await _gate(ctx)
    _not_yet()


@threads_router.get(
    "/engagements/{engagement_id}/assignee-candidates",
    action="todo.assign",
    response_model=AssigneeCandidatesOut,
    errors=(501,),
)
async def assignee_candidates_route(
    engagement_id: UUID, ctx: Ctx, q: Annotated[str | None, Query(max_length=60)] = None
) -> AssigneeCandidatesOut:
    await _gate(ctx)
    _not_yet()


todos_router = AbacusRouter(prefix="/v1/todos", tags=["collaboration"])
_D = "/{todo_id}"


@todos_router.post(
    "", action="todo.create", response_model=TodoOut, status_code=201, errors=(409, 501)
)
async def create_todo_route(body: TodoCreateIn, ctx: Ctx, key: Key = None) -> TodoOut:
    """422 `assignee_not_allowed` (not a human member, walled, or the agent)."""
    await _gate(ctx)
    _not_yet()


@todos_router.get("", action="todo.read", response_model=TodoPageOut, errors=(501,))
async def list_todos_route(
    ctx: Ctx,
    assignee: Annotated[Literal["me"] | None, Query()] = None,
    status: Annotated[TodoStatus | None, Query()] = None,
    anchor_kind: Annotated[AnchorKind | None, Query()] = None,
    anchor_id: Annotated[UUID | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TodoPageOut:
    """My to-dos (`assignee=me`) or the to-dos on one anchor."""
    await _gate(ctx)
    _not_yet()


@todos_router.post("/counts", action="todo.read", response_model=TodoCountsOut, errors=(501,))
async def todo_counts_route(body: AnchorCountsIn, ctx: Ctx) -> TodoCountsOut:
    await _gate(ctx)
    _not_yet()


@todos_router.get(_D, action="todo.read", response_model=TodoOut, errors=(501,))
async def get_todo_route(todo_id: UUID, ctx: Ctx) -> TodoOut:
    await _gate(ctx)
    _not_yet()


@todos_router.patch(_D, action="todo.update", response_model=TodoOut, errors=(409, 501))
async def patch_todo_route(
    todo_id: UUID, body: TodoPatchIn, ctx: Ctx, if_match: IfMatch = None
) -> TodoOut:
    """409 `stale_version` when `If-Match` is not the current version (AC-20)."""
    await _gate(ctx)
    _not_yet()


@todos_router.post(f"{_D}/assign", action="todo.assign", response_model=TodoOut, errors=(409, 501))
async def assign_todo_route(
    todo_id: UUID, body: TodoAssignIn, ctx: Ctx, key: Key = None
) -> TodoOut:
    await _gate(ctx)
    _not_yet()


@todos_router.post(
    f"{_D}/complete", action="todo.complete", response_model=TodoOut, errors=(409, 501)
)
async def complete_todo_route(todo_id: UUID, ctx: Ctx, key: Key = None) -> TodoOut:
    await _gate(ctx)
    _not_yet()


@todos_router.post(
    f"{_D}/reopen", action="todo.complete", response_model=TodoOut, errors=(409, 501)
)
async def reopen_todo_route(todo_id: UUID, ctx: Ctx, key: Key = None) -> TodoOut:
    """Reopen, and the Undo of a completion (a compensating command, DEC-24)."""
    await _gate(ctx)
    _not_yet()


@todos_router.post(f"{_D}/move", action="todo.update", response_model=TodoOut, errors=(409, 501))
async def move_todo_route(todo_id: UUID, body: TodoMoveIn, ctx: Ctx, key: Key = None) -> TodoOut:
    await _gate(ctx)
    _not_yet()


@todos_router.delete(_D, action="todo.delete", response_model=TodoOut, errors=(409, 501))
async def delete_todo_route(todo_id: UUID, ctx: Ctx) -> TodoOut:
    """A soft delete (creator, assignee or manager-or-above; 403 otherwise)."""
    await _gate(ctx)
    _not_yet()


@todos_router.post(
    f"{_D}/checklist-items",
    action="todo.update",
    response_model=TodoOut,
    status_code=201,
    errors=(409, 501),
)
async def add_checklist_item_route(todo_id: UUID, body: TodoChecklistItemIn, ctx: Ctx) -> TodoOut:
    """422 `checklist_full` on a ninth item."""
    await _gate(ctx)
    _not_yet()


@todos_router.patch(
    f"{_D}/checklist-items/{{item_id}}",
    action="todo.update",
    response_model=TodoOut,
    errors=(409, 501),
)
async def patch_checklist_item_route(
    todo_id: UUID, item_id: UUID, body: TodoChecklistItemPatchIn, ctx: Ctx
) -> TodoOut:
    await _gate(ctx)
    _not_yet()


@todos_router.delete(
    f"{_D}/checklist-items/{{item_id}}",
    action="todo.update",
    response_model=TodoOut,
    errors=(409, 501),
)
async def delete_checklist_item_route(todo_id: UUID, item_id: UUID, ctx: Ctx) -> TodoOut:
    await _gate(ctx)
    _not_yet()


@todos_router.post(f"{_D}/seen", action="todo.read", response_model=TodoOut, errors=(501,))
async def seen_todo_route(todo_id: UUID, ctx: Ctx) -> TodoOut:
    """The assignee opened it: clears the unread dot."""
    await _gate(ctx)
    _not_yet()
