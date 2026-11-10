"""Collaboration's routes (P-05-T05, T06; contract `docs/contracts/collaboration.md`; SPEC-650).

Every route declares exactly one matrix action (P-05-T02's rows and the live `comment.*` rows),
refuses a client principal first (404: no anchor P-05 registers is client-visible, INV-4) and then
checks `collaboration.v2` (off: 404, AC-39). The services authorise on the anchor. A comment body
is Restricted and never stored in the idempotency table: a retry with the same key answers from
the stored identifiers and re-reads the thread.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Query

from abacus.kernel._flags import COLLABORATION_V2
from abacus.kernel._statuses import CommentThreadStatus, TodoStatus
from abacus.kernel.errors import DomainInvalid, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.collaboration import candidates, threads, todos
from abacus.modules.collaboration import views as v
from abacus.modules.collaboration.contract import (
    AnchorCountsIn,
    AnchorKind,
    AnchorRef,
    AssigneeCandidatesOut,
    CommentPostedOut,
    CommentPostIn,
    ConvertedOut,
    MentionCandidatesOut,
    TeamEntryOut,
    ThreadCommentOut,
    ThreadCountOut,
    ThreadCountsOut,
    ThreadMuteIn,
    ThreadOpenIn,
    ThreadOut,
    ThreadPageOut,
    ThreadRedactIn,
    ThreadShareIn,
    TodoAssignIn,
    TodoChecklistItemIn,
    TodoChecklistItemPatchIn,
    TodoCountOut,
    TodoCountsOut,
    TodoCreateIn,
    TodoMoveIn,
    TodoOut,
    TodoPageOut,
    TodoPatchIn,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
Key = Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)]
IfMatch = Annotated[str | None, Header(alias="If-Match", max_length=20)]
Locator = Annotated[str | None, Query(max_length=200)]
Q = Annotated[str | None, Query(max_length=60)]


async def gate(ctx: AuthContext) -> None:
    """A firm person only (no anchor in P-05 is client-visible), then the flag."""
    if ctx.client:
        raise NotFound("comment_thread")
    if not await flag_enabled(ctx.tenant, COLLABORATION_V2):
        raise NotFound(COLLABORATION_V2.name)


def not_yet() -> NoReturn:
    raise NotImplementedYet


class QueryLocatorInvalid(DomainInvalid):
    code = "anchor_locator_invalid"


def query_locator(raw: str | None) -> dict[str, str | int] | None:
    """`?locator=` is the compact JSON object a provider's schema accepts."""
    if not raw:
        return None
    try:
        found: object = json.loads(raw)
    except ValueError:
        raise QueryLocatorInvalid from None
    if not isinstance(found, dict):
        raise QueryLocatorInvalid
    pairs = list(found.items())  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType] -- checked below
    out: dict[str, str | int] = {}
    for k, x in pairs:  # pyright: ignore[reportUnknownVariableType] -- checked here
        if not isinstance(k, str) or not isinstance(x, str | int) or isinstance(x, bool):
            raise QueryLocatorInvalid
        out[k] = x
    return out


async def once(
    ctx: AuthContext,
    route: str,
    key: str | None,
    body: object,
    post: Callable[[], Awaitable[threads.Posted]],
) -> threads.Posted:
    """Post once per key; a retry answers from the stored identifiers (never the body)."""
    if key is None:
        return await post()
    made: list[threads.Posted] = []

    async def run() -> tuple[int, dict[str, object]]:
        posted = await post()
        made.append(posted)
        return 201, {
            "thread_id": str(posted.thread_id),
            "comment_id": str(posted.comment_id),
            "notified": [str(u) for u in posted.notified],
        }

    stored = await idempotent(ctx.tenant, route=route, key=key, body=body, run=run)
    if made:
        return made[0]
    notified = stored.body.get("notified")
    raw = cast(list[object], notified) if isinstance(notified, list) else []
    ids = [UUID(str(u)) for u in raw]
    return threads.Posted(
        UUID(str(stored.body["thread_id"])), UUID(str(stored.body["comment_id"])), ids
    )


threads_router = AbacusRouter(prefix="/v1", tags=["collaboration"])
_T = "/comment-threads/{thread_id}"


async def _thread_out(ctx: AuthContext, thread_id: UUID) -> ThreadOut:
    return (await v.threads_out([await threads.thread(ctx, thread_id)]))[0]


async def _posted_out(ctx: AuthContext, posted: threads.Posted) -> CommentPostedOut:
    named = await v.people(posted.notified)
    return CommentPostedOut(
        thread=await _thread_out(ctx, posted.thread_id),
        comment_id=posted.comment_id,
        notified=[named[u] for u in posted.notified],
    )


@threads_router.get(
    "/comment-threads", action="comment.read", response_model=ThreadPageOut, errors=(409,)
)
async def list_comment_threads_route(
    ctx: Ctx,
    anchor_kind: Annotated[AnchorKind, Query()],
    anchor_id: Annotated[UUID, Query()],
    locator: Locator = None,
    status: Annotated[CommentThreadStatus | None, Query()] = None,
) -> ThreadPageOut:
    """Threads and comments for one anchor; `counts` holds Open and Resolved (SHL-18d)."""
    await gate(ctx)
    found, counts = await threads.threads_on(
        ctx,
        anchor_kind=anchor_kind,
        anchor_id=anchor_id,
        locator=query_locator(locator),
        status=None if status is None else str(status.value),
    )
    items = await v.threads_out(found)
    return ThreadPageOut(items=items, total=len(items), counts=counts)


@threads_router.post(
    "/comment-threads/counts", action="comment.read", response_model=ThreadCountsOut, errors=(409,)
)
async def thread_counts_route(body: AnchorCountsIn, ctx: Ctx) -> ThreadCountsOut:
    """The C-27 chips for up to 200 anchors."""
    await gate(ctx)
    found = await threads.counts(
        ctx, [(a.anchor_kind, a.anchor_id, a.locator) for a in body.anchors]
    )
    return ThreadCountsOut(
        items=[
            ThreadCountOut(
                anchor=AnchorRef(
                    anchor_kind=f.anchor_kind, anchor_id=f.anchor_id, locator=f.locator
                ),
                open=f.open,
                resolved=f.resolved,
                unread=f.unread,
            )
            for f in found
        ]
    )


@threads_router.post(
    "/comment-threads",
    action="comment.create",
    response_model=CommentPostedOut,
    status_code=201,
    errors=(409,),
)
async def open_thread_route(body: ThreadOpenIn, ctx: Ctx, key: Key = None) -> CommentPostedOut:
    """409 `anchor_kind_not_registered`; 422 `empty_comment`, `comment_too_long`,
    `mention_not_allowed`."""
    await gate(ctx)

    async def post() -> threads.Posted:
        return await threads.open_thread(
            ctx,
            anchor_kind=body.anchor.anchor_kind,
            anchor_id=body.anchor.anchor_id,
            locator=body.anchor.locator,
            body=body.body,
            mention_user_ids=body.mention_user_ids,
            mention_team=body.mention_team,
            citation_ids=body.citation_ids,
        )

    posted = await once(ctx, "comment_thread.open", key, body.model_dump(mode="json"), post)
    return await _posted_out(ctx, posted)


@threads_router.post(
    f"{_T}/comments",
    action="comment.create",
    response_model=CommentPostedOut,
    status_code=201,
    errors=(409,),
)
async def post_comment_route(
    thread_id: UUID, body: CommentPostIn, ctx: Ctx, key: Key = None
) -> CommentPostedOut:
    """A reply, or the author's correction (422 `correction_not_allowed` for anyone else)."""
    await gate(ctx)

    async def post() -> threads.Posted:
        return await threads.post_comment(
            ctx,
            thread_id,
            body=body.body,
            mention_user_ids=body.mention_user_ids,
            mention_team=body.mention_team,
            corrects_comment_id=body.corrects_comment_id,
            citation_ids=body.citation_ids,
        )

    payload = {"thread_id": str(thread_id), **body.model_dump(mode="json")}
    posted = await once(ctx, "comment.post", key, payload, post)
    return await _posted_out(ctx, posted)


@threads_router.post(
    "/thread-comments/{comment_id}/redact",
    action="comment.redact",
    response_model=ThreadCommentOut,
    errors=(409,),
)
async def redact_thread_comment_route(
    comment_id: UUID, body: ThreadRedactIn, ctx: Ctx, key: Key = None
) -> ThreadCommentOut:
    """Firm admin with a fresh MFA (matrix); 409 `already_redacted`. A retry with the key after a
    redaction answers 409 too: the comment is redacted either way."""
    del key  # a redaction is one row per comment: the database is its own idempotency
    await gate(ctx)
    thread_id = await threads.redact(ctx, comment_id, body.reason)
    out = await _thread_out(ctx, thread_id)
    return next(c for c in out.comments if c.id == comment_id)


@threads_router.post(
    f"{_T}/resolve", action="comment.resolve", response_model=ThreadOut, errors=(409,)
)
async def resolve_thread_route(thread_id: UUID, ctx: Ctx, key: Key = None) -> ThreadOut:
    """A `resolved` thread event (409 `thread_already_resolved`)."""
    del key  # the status projection only moves from `open`: a retry answers 409
    await gate(ctx)
    await threads.resolve(ctx, thread_id)
    return await _thread_out(ctx, thread_id)


@threads_router.post(
    f"{_T}/reopen", action="comment.resolve", response_model=ThreadOut, errors=(409,)
)
async def reopen_thread_route(thread_id: UUID, ctx: Ctx, key: Key = None) -> ThreadOut:
    del key  # the status projection only moves from `resolved`: a retry answers 409
    await gate(ctx)
    await threads.reopen(ctx, thread_id)
    return await _thread_out(ctx, thread_id)


@threads_router.post(f"{_T}/mute", action="comment.read", response_model=ThreadOut)
async def mute_thread_route(thread_id: UUID, body: ThreadMuteIn, ctx: Ctx) -> ThreadOut:
    await gate(ctx)
    await threads.mute(ctx, thread_id, muted=body.muted)
    return await _thread_out(ctx, thread_id)


@threads_router.post(f"{_T}/read", action="comment.read", response_model=ThreadOut)
async def read_thread_route(thread_id: UUID, ctx: Ctx) -> ThreadOut:
    await gate(ctx)
    await threads.mark_read(ctx, thread_id)
    return await _thread_out(ctx, thread_id)


@threads_router.post(
    f"{_T}/share", action="comment.share", response_model=ThreadOut, errors=(409,)
)
async def share_thread_route(
    thread_id: UUID, body: ThreadShareIn, ctx: Ctx, key: Key = None
) -> ThreadOut:
    """409 `anchor_not_shareable` for every anchor P-05 registers."""
    del key  # sharing moves `internal` to `shared` once; a retry writes nothing
    await gate(ctx)
    await threads.share(ctx, thread_id, scope_kind=body.scope_kind, scope_id=body.scope_id)
    return await _thread_out(ctx, thread_id)


@threads_router.post(
    f"{_T}/convert-to-review-note",
    action="review_note.raise",
    response_model=ConvertedOut,
    status_code=201,
    errors=(409, 501),
)
async def convert_to_review_note_route(thread_id: UUID, ctx: Ctx, key: Key = None) -> ConvertedOut:
    """Raises an open AUD-17 note through C3 in the same unit of work (P-05-T09)."""
    await gate(ctx)
    not_yet()


@threads_router.get(
    "/engagements/{engagement_id}/mention-candidates",
    action="comment.create",
    response_model=MentionCandidatesOut,
)
async def thread_mention_candidates_route(
    engagement_id: UUID, ctx: Ctx, q: Q = None
) -> MentionCandidatesOut:
    """SHL-18b/b2: the team entry and its members; non-members greyed for a search (AC-6)."""
    await gate(ctx)
    found = await candidates.mention_candidates(ctx, engagement_id, q)
    team = None
    if not q or not q.strip():
        team = TeamEntryOut(label=found.team_label, member_count=len(found.members))
    return MentionCandidatesOut(
        team=team,
        members=[v.candidate_out(m) for m in found.members],
        not_on_engagement=[v.candidate_out(m) for m in found.not_on_engagement],
    )


@threads_router.get(
    "/engagements/{engagement_id}/assignee-candidates",
    action="todo.assign",
    response_model=AssigneeCandidatesOut,
)
async def assignee_candidates_route(
    engagement_id: UUID, ctx: Ctx, q: Q = None
) -> AssigneeCandidatesOut:
    """SHL-17b: the people on the engagement (AC-17); never the agent."""
    await gate(ctx)
    found = await candidates.assignee_candidates(ctx, engagement_id, q)
    return AssigneeCandidatesOut(items=[v.candidate_out(m) for m in found])


todos_router = AbacusRouter(prefix="/v1/todos", tags=["collaboration"])
_D = "/{todo_id}"


def _anchor_of(ref: AnchorRef | None) -> tuple[str, UUID, dict[str, str | int] | None] | None:
    return None if ref is None else (ref.anchor_kind, ref.anchor_id, ref.locator)


async def _todo_out(ctx: AuthContext, todo_id: UUID) -> TodoOut:
    return (await v.todos_out([await todos.read(ctx, todo_id)]))[0]


@todos_router.post(
    "", action="todo.create", response_model=TodoOut, status_code=201, errors=(409,)
)
async def create_todo_route(body: TodoCreateIn, ctx: Ctx, key: Key = None) -> TodoOut:
    """422 `assignee_not_allowed` (not a human member, walled, or the agent)."""
    await gate(ctx)

    async def run() -> tuple[int, dict[str, object]]:
        todo_id = await todos.create(
            ctx,
            scope_kind=body.scope_kind,
            engagement_id=body.engagement_id,
            title=body.title,
            assignee_user_id=body.assignee_user_id,
            due_on=body.due_on,
            anchor=_anchor_of(body.anchor),
            checklist=body.checklist,
            source_thread_id=body.source_thread_id,
        )
        return 201, {"todo_id": str(todo_id)}

    if key is None:
        _, made = await run()
    else:
        made = (
            await idempotent(
                ctx.tenant,
                route="todo.create",
                key=key,
                body=body.model_dump(mode="json"),
                run=run,
            )
        ).body
    return await _todo_out(ctx, UUID(str(made["todo_id"])))


@todos_router.get("", action="todo.read", response_model=TodoPageOut)
async def list_todos_route(
    ctx: Ctx,
    assignee: Annotated[Literal["me"] | None, Query()] = None,
    status: Annotated[TodoStatus | None, Query()] = None,
    anchor_kind: Annotated[AnchorKind | None, Query()] = None,
    anchor_id: Annotated[UUID | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> TodoPageOut:
    """My to-dos (`assignee=me`, with the bands in `counts`) or the to-dos on one anchor. A
    person's to-dos are few (no cursor yet; `limit` caps the page)."""
    del cursor
    await gate(ctx)
    if anchor_kind is not None and anchor_id is not None:
        found = await todos.on_anchor(ctx, anchor_kind, anchor_id)
        items = await v.todos_out(found[:limit])
        return TodoPageOut(items=items, total=len(found), counts={"open": len(found)})
    page = await todos.mine(ctx, status=None if status is None else str(status.value))
    items = await v.todos_out(page.items[:limit])
    return TodoPageOut(items=items, total=len(page.items), counts=page.counts)


@todos_router.post("/counts", action="todo.read", response_model=TodoCountsOut)
async def todo_counts_route(body: AnchorCountsIn, ctx: Ctx) -> TodoCountsOut:
    """The "n To-do" chips for up to 200 anchors."""
    await gate(ctx)
    found = await todos.anchor_counts(
        ctx, [(a.anchor_kind, a.anchor_id, a.locator) for a in body.anchors]
    )
    return TodoCountsOut(
        items=[
            TodoCountOut(
                anchor=AnchorRef(anchor_kind=k, anchor_id=a, locator=dict(loc) if loc else None),
                open=n,
            )
            for k, a, loc, n in found
        ]
    )


@todos_router.get(_D, action="todo.read", response_model=TodoOut)
async def get_todo_route(todo_id: UUID, ctx: Ctx) -> TodoOut:
    await gate(ctx)
    return await _todo_out(ctx, todo_id)


@todos_router.patch(_D, action="todo.update", response_model=TodoOut, errors=(409,))
async def patch_todo_route(
    todo_id: UUID, body: TodoPatchIn, ctx: Ctx, if_match: IfMatch = None
) -> TodoOut:
    """409 `stale_version` when `If-Match` is not the current version (AC-20)."""
    await gate(ctx)
    await todos.patch(
        ctx,
        todo_id,
        title=body.title,
        due_on=body.due_on,
        clear_due_on=body.clear_due_on,
        if_match=if_match,
    )
    return await _todo_out(ctx, todo_id)


@todos_router.post(f"{_D}/assign", action="todo.assign", response_model=TodoOut, errors=(409,))
async def assign_todo_route(
    todo_id: UUID, body: TodoAssignIn, ctx: Ctx, key: Key = None
) -> TodoOut:
    del key  # reassigning to the same person again changes nothing a person sees
    await gate(ctx)
    await todos.assign(ctx, todo_id, body.assignee_user_id)
    return await _todo_out(ctx, todo_id)


@todos_router.post(f"{_D}/complete", action="todo.complete", response_model=TodoOut, errors=(409,))
async def complete_todo_route(todo_id: UUID, ctx: Ctx, key: Key = None) -> TodoOut:
    del key  # `open` to `done` once: a retry answers 409 `todo_already_done`
    await gate(ctx)
    await todos.complete(ctx, todo_id)
    return await _todo_out(ctx, todo_id)


@todos_router.post(f"{_D}/reopen", action="todo.complete", response_model=TodoOut, errors=(409,))
async def reopen_todo_route(todo_id: UUID, ctx: Ctx, key: Key = None) -> TodoOut:
    """Reopen, and the Undo of a completion (a compensating command, DEC-24)."""
    del key  # `done` to `open` once: a retry answers 409 `todo_not_done`
    await gate(ctx)
    await todos.reopen(ctx, todo_id)
    return await _todo_out(ctx, todo_id)


@todos_router.post(f"{_D}/move", action="todo.update", response_model=TodoOut, errors=(409,))
async def move_todo_route(todo_id: UUID, body: TodoMoveIn, ctx: Ctx, key: Key = None) -> TodoOut:
    del key  # moving to the same anchor again changes nothing
    await gate(ctx)
    await todos.move(
        ctx, todo_id, (body.anchor.anchor_kind, body.anchor.anchor_id, body.anchor.locator)
    )
    return await _todo_out(ctx, todo_id)


@todos_router.delete(_D, action="todo.delete", response_model=TodoOut, errors=(409,))
async def delete_todo_route(todo_id: UUID, ctx: Ctx) -> TodoOut:
    """A soft delete (creator, assignee or manager-or-above; 403 otherwise)."""
    await gate(ctx)
    return (await v.todos_out([await todos.delete(ctx, todo_id)]))[0]


@todos_router.post(
    f"{_D}/checklist-items",
    action="todo.update",
    response_model=TodoOut,
    status_code=201,
    errors=(409,),
)
async def add_checklist_item_route(todo_id: UUID, body: TodoChecklistItemIn, ctx: Ctx) -> TodoOut:
    """422 `checklist_full` on a ninth item."""
    await gate(ctx)
    await todos.add_item(ctx, todo_id, body.text)
    return await _todo_out(ctx, todo_id)


@todos_router.patch(
    f"{_D}/checklist-items/{{item_id}}",
    action="todo.update",
    response_model=TodoOut,
    errors=(409,),
)
async def patch_checklist_item_route(
    todo_id: UUID, item_id: UUID, body: TodoChecklistItemPatchIn, ctx: Ctx
) -> TodoOut:
    await gate(ctx)
    await todos.change_item(ctx, todo_id, item_id, text=body.text, done=body.done)
    return await _todo_out(ctx, todo_id)


@todos_router.delete(
    f"{_D}/checklist-items/{{item_id}}",
    action="todo.update",
    response_model=TodoOut,
    errors=(409,),
)
async def delete_checklist_item_route(todo_id: UUID, item_id: UUID, ctx: Ctx) -> TodoOut:
    await gate(ctx)
    await todos.remove_item(ctx, todo_id, item_id)
    return await _todo_out(ctx, todo_id)


@todos_router.post(f"{_D}/seen", action="todo.read", response_model=TodoOut)
async def seen_todo_route(todo_id: UUID, ctx: Ctx) -> TodoOut:
    """The assignee opened it: clears the unread dot."""
    await gate(ctx)
    await todos.seen(ctx, todo_id)
    return await _todo_out(ctx, todo_id)
