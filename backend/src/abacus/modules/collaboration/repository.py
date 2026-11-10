"""Collaboration's reads and writes (P-05-T05, T06; migration 0760). Writes name only the columns
the app role may insert or update; every list filters with `visible()` (LIST-001), on the
thread's or the to-do's engagement, after the service authorised the anchor."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, delete, false, func, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from abacus.modules.collaboration.models import (
    CommentThread,
    CommentThreadEvent,
    CommentThreadRead,
    ThreadComment,
    ThreadCommentMention,
    ThreadCommentRedaction,
    Todo,
    TodoChecklistItem,
)
from abacus.modules.identity.api import AuthContext, visible

# --- threads -------------------------------------------------------------------------------------


async def get_thread(session: AsyncSession, thread_id: UUID) -> CommentThread | None:
    return await session.get(CommentThread, thread_id)


async def find_thread(
    session: AsyncSession,
    *,
    anchor_kind: str,
    anchor_id: UUID,
    locator_key: str,
    pinned_version_no: int | None,
) -> CommentThread | None:
    """The one thread on an anchor and locator (and version, under `pin`)."""
    pinned = (
        CommentThread.pinned_version_no.is_(None)
        if pinned_version_no is None
        else CommentThread.pinned_version_no == pinned_version_no
    )
    found = await session.execute(
        select(CommentThread).where(
            CommentThread.anchor_kind == anchor_kind,
            CommentThread.anchor_id == anchor_id,
            CommentThread.anchor_locator_key == locator_key,
            pinned,
        )
    )
    return found.scalar_one_or_none()


async def insert_thread(session: AsyncSession, **values: object) -> UUID:
    return (
        await session.execute(insert(CommentThread).values(**values).returning(CommentThread.id))
    ).scalar_one()


async def set_thread_status(
    session: AsyncSession, thread_id: UUID, *, status: str, expected: str
) -> bool:
    """The status projection beside its event; False when the thread was not `expected`."""
    moved = await session.execute(
        update(CommentThread)
        .where(CommentThread.id == thread_id, CommentThread.status == expected)
        .values(status=status, updated_at=func.clock_timestamp())
        .returning(CommentThread.id)
    )
    return moved.scalar_one_or_none() is not None


async def share_thread(
    session: AsyncSession, thread_id: UUID, *, scope_kind: str, scope_id: UUID
) -> bool:
    moved = await session.execute(
        update(CommentThread)
        .where(CommentThread.id == thread_id, CommentThread.visibility == "internal")
        .values(
            visibility="shared",
            shared_scope_kind=scope_kind,
            shared_scope_id=scope_id,
            updated_at=func.clock_timestamp(),
        )
        .returning(CommentThread.id)
    )
    return moved.scalar_one_or_none() is not None


async def touch_thread(session: AsyncSession, thread_id: UUID) -> None:
    await session.execute(
        update(CommentThread)
        .where(CommentThread.id == thread_id)
        .values(last_comment_at=func.clock_timestamp(), updated_at=func.clock_timestamp())
    )


async def list_threads_on(
    session: AsyncSession,
    ctx: AuthContext,
    *,
    anchor_kind: str,
    anchor_id: UUID,
    locator_key: str | None,
) -> list[CommentThread]:
    """Every thread on an anchor (all locators when `locator_key` is None), newest activity
    last."""
    query = select(CommentThread).where(
        CommentThread.anchor_kind == anchor_kind,
        CommentThread.anchor_id == anchor_id,
        visible(ctx, "comment.read", CommentThread.engagement_id),
    )
    if locator_key is not None:
        query = query.where(CommentThread.anchor_locator_key == locator_key)
    found = await session.execute(query.order_by(CommentThread.created_at, CommentThread.id))
    return list(found.scalars().all())


async def list_threads_on_anchors(
    session: AsyncSession, ctx: AuthContext, anchors: Sequence[tuple[str, UUID]]
) -> list[CommentThread]:
    """The threads on up to 200 anchors, for the C-27 chips (no anchors: none, but the filter is
    still built, which is the route's check)."""
    match = (
        false()
        if not anchors
        else or_(
            *(
                and_(CommentThread.anchor_kind == kind, CommentThread.anchor_id == anchor)
                for kind, anchor in anchors
            )
        )
    )
    found = await session.execute(
        select(CommentThread).where(
            match, visible(ctx, "comment.read", CommentThread.engagement_id)
        )
    )
    return list(found.scalars().all())


async def insert_event(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    thread_id: UUID,
    kind: str,
    actor_user_id: UUID,
    ref_type: str | None = None,
    ref_id: UUID | None = None,
) -> None:
    await session.execute(
        insert(CommentThreadEvent).values(
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            thread_id=thread_id,
            kind=kind,
            actor_user_id=actor_user_id,
            actor_kind="human",
            ref_type=ref_type,
            ref_id=ref_id,
        )
    )


async def list_events(
    session: AsyncSession, ctx: AuthContext, thread_ids: Sequence[UUID]
) -> list[CommentThreadEvent]:
    found = await session.execute(
        select(CommentThreadEvent)
        .where(
            CommentThreadEvent.thread_id.in_(list(thread_ids)),
            visible(ctx, "comment.read", CommentThreadEvent.engagement_id),
        )
        .order_by(CommentThreadEvent.created_at, CommentThreadEvent.id)
    )
    return list(found.scalars().all())


# --- comments ------------------------------------------------------------------------------------


async def insert_comment(session: AsyncSession, **values: object) -> ThreadComment:
    row = (
        await session.execute(insert(ThreadComment).values(**values).returning(ThreadComment))
    ).scalar_one()
    return row


async def get_comment(session: AsyncSession, comment_id: UUID) -> ThreadComment | None:
    return await session.get(ThreadComment, comment_id)


async def get_redaction(session: AsyncSession, comment_id: UUID) -> ThreadCommentRedaction | None:
    """AC-11: a comment's redaction row, by the comment's id."""
    return await session.scalar(
        select(ThreadCommentRedaction).where(ThreadCommentRedaction.comment_id == comment_id)
    )


async def corrected_by_of(session: AsyncSession, comment_id: UUID) -> UUID | None:
    """The comment that corrects this one, if any."""
    return await session.scalar(
        select(ThreadComment.id).where(ThreadComment.corrects_comment_id == comment_id)
    )


async def insert_mentions(
    session: AsyncSession,
    tenant_id: UUID,
    comment_id: UUID,
    user_ids: Sequence[UUID],
    *,
    via_team: bool,
) -> None:
    if not user_ids:
        return
    await session.execute(
        insert(ThreadCommentMention),
        [
            {"tenant_id": tenant_id, "comment_id": comment_id, "user_id": u, "via_team": via_team}
            for u in user_ids
        ],
    )


async def insert_redaction(
    session: AsyncSession, *, tenant_id: UUID, comment_id: UUID, redacted_by: UUID, reason: str
) -> bool:
    """One redaction per comment: False when it was already redacted."""
    made = await session.execute(
        pg_insert(ThreadCommentRedaction)
        .values(tenant_id=tenant_id, comment_id=comment_id, redacted_by=redacted_by, reason=reason)
        .on_conflict_do_nothing()
        .returning(ThreadCommentRedaction.comment_id)
    )
    return made.scalar_one_or_none() is not None


async def list_comments(
    session: AsyncSession, ctx: AuthContext, thread_ids: Sequence[UUID]
) -> list[tuple[ThreadComment, ThreadCommentRedaction | None]]:
    """Comments of the threads, oldest first, each with its redaction."""
    found = await session.execute(
        select(ThreadComment, ThreadCommentRedaction)
        .outerjoin(
            ThreadCommentRedaction,
            and_(
                ThreadCommentRedaction.tenant_id == ThreadComment.tenant_id,
                ThreadCommentRedaction.comment_id == ThreadComment.id,
            ),
        )
        .where(
            ThreadComment.thread_id.in_(list(thread_ids)),
            visible(ctx, "comment.read", ThreadComment.engagement_id),
        )
        .order_by(ThreadComment.created_at, ThreadComment.id)
    )
    return [(c, r) for c, r in found.tuples().all()]


async def list_mentions(
    session: AsyncSession, ctx: AuthContext, comment_ids: Sequence[UUID]
) -> list[ThreadCommentMention]:
    found = await session.execute(
        select(ThreadCommentMention)
        .join(ThreadComment, ThreadComment.id == ThreadCommentMention.comment_id)
        .where(
            ThreadCommentMention.comment_id.in_(list(comment_ids)),
            visible(ctx, "comment.read", ThreadComment.engagement_id),
        )
    )
    return list(found.scalars().all())


# --- per-person reads ----------------------------------------------------------------------------


async def list_reads(
    session: AsyncSession, ctx: AuthContext, thread_ids: Sequence[UUID]
) -> list[CommentThreadRead]:
    found = await session.execute(
        select(CommentThreadRead)
        .join(CommentThread, CommentThread.id == CommentThreadRead.thread_id)
        .where(
            CommentThreadRead.user_id == ctx.user_id,
            CommentThreadRead.thread_id.in_(list(thread_ids)),
            visible(ctx, "comment.read", CommentThread.engagement_id),
        )
    )
    return list(found.scalars().all())


async def mark_read(
    session: AsyncSession, tenant_id: UUID, user_id: UUID, thread_id: UUID
) -> None:
    statement = pg_insert(CommentThreadRead).values(
        tenant_id=tenant_id, user_id=user_id, thread_id=thread_id, last_read_at=func.now()
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["tenant_id", "user_id", "thread_id"],
            set_={"last_read_at": statement.excluded.last_read_at},
        )
    )


async def set_muted(
    session: AsyncSession, tenant_id: UUID, user_id: UUID, thread_id: UUID, *, muted: bool
) -> None:
    statement = pg_insert(CommentThreadRead).values(
        tenant_id=tenant_id,
        user_id=user_id,
        thread_id=thread_id,
        muted_at=func.now() if muted else None,
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=["tenant_id", "user_id", "thread_id"],
            set_={"muted_at": statement.excluded.muted_at},
        )
    )


# --- to-dos (P-05-T06) ---------------------------------------------------------------------------


async def insert_todo(session: AsyncSession, **values: object) -> UUID:
    return (await session.execute(insert(Todo).values(**values).returning(Todo.id))).scalar_one()


async def get_todo(session: AsyncSession, todo_id: UUID) -> Todo | None:
    """A live to-do (soft-deleted ones are gone for every route but the audit trail)."""
    found = await session.execute(
        select(Todo).where(Todo.id == todo_id, Todo.deleted_at.is_(None))
    )
    return found.scalar_one_or_none()


async def update_todo(
    session: AsyncSession,
    todo_id: UUID,
    *,
    expected_version: int | None,
    bump: bool = True,
    **values: object,
) -> Todo | None:
    """Set `values` (and bump the version, unless `bump` is off for a read marker); None when
    `expected_version` is stale or the to-do is gone."""
    return await update_todo_values(
        session, todo_id, values, expected_version=expected_version, bump=bump
    )


async def update_todo_values(
    session: AsyncSession,
    todo_id: UUID,
    values: Mapping[str, object],
    *,
    expected_version: int | None,
    bump: bool = True,
) -> Todo | None:
    query = update(Todo).where(Todo.id == todo_id, Todo.deleted_at.is_(None))
    if expected_version is not None:
        query = query.where(Todo.version == expected_version)
    changes: dict[str, object] = {**values, "updated_at": func.clock_timestamp()}
    if bump:
        changes["version"] = Todo.version + 1
    found = await session.execute(
        query.values(changes).returning(Todo).execution_options(synchronize_session=False)
    )
    return found.scalar_one_or_none()


# A firm-scope to-do has no engagement; `visible()` admits no NULL engagement.
_TODO_ENGAGEMENT = cast("ColumnElement[UUID]", Todo.engagement_id)


def _own_firm_todo(ctx: AuthContext) -> ColumnElement[bool]:
    """A firm-scope to-do is read by its creator and its assignee only (AC-28); engagement
    to-dos go by `visible()` beside it in each query."""
    return and_(
        Todo.scope_kind == "firm",
        or_(Todo.created_by == ctx.user_id, Todo.assignee_user_id == ctx.user_id),
    )


async def list_my_todos(
    session: AsyncSession, ctx: AuthContext, *, status: str | None
) -> list[Todo]:
    query = select(Todo).where(
        Todo.assignee_user_id == ctx.user_id,
        Todo.deleted_at.is_(None),
        or_(visible(ctx, "todo.read", _TODO_ENGAGEMENT), _own_firm_todo(ctx)),
    )
    if status is not None:
        query = query.where(Todo.status == status)
    found = await session.execute(
        query.order_by(Todo.due_on.asc().nulls_last(), Todo.created_at, Todo.id)
    )
    return list(found.scalars().all())


async def list_todos_on(
    session: AsyncSession, ctx: AuthContext, *, anchor_kind: str, anchor_id: UUID
) -> list[Todo]:
    found = await session.execute(
        select(Todo)
        .where(
            Todo.anchor_kind == anchor_kind,
            Todo.anchor_id == anchor_id,
            Todo.deleted_at.is_(None),
            or_(visible(ctx, "todo.read", _TODO_ENGAGEMENT), _own_firm_todo(ctx)),
        )
        .order_by(Todo.created_at, Todo.id)
    )
    return list(found.scalars().all())


async def list_todos_on_anchors(
    session: AsyncSession, ctx: AuthContext, anchors: Sequence[tuple[str, UUID]]
) -> list[Todo]:
    match = (
        false()
        if not anchors
        else or_(
            *(and_(Todo.anchor_kind == kind, Todo.anchor_id == anchor) for kind, anchor in anchors)
        )
    )
    found = await session.execute(
        select(Todo).where(
            match,
            Todo.status == "open",
            Todo.deleted_at.is_(None),
            or_(visible(ctx, "todo.read", _TODO_ENGAGEMENT), _own_firm_todo(ctx)),
        )
    )
    return list(found.scalars().all())


async def comment_counts_on(
    session: AsyncSession, ctx: AuthContext, anchor_kind: str, anchor_ids: Sequence[UUID]
) -> list[tuple[UUID, int]]:
    """Comments on the threads of each anchor (SHL-17's comment count)."""
    found = await session.execute(
        select(CommentThread.anchor_id, func.count(ThreadComment.id))
        .join(ThreadComment, ThreadComment.thread_id == CommentThread.id)
        .where(
            CommentThread.anchor_kind == anchor_kind,
            CommentThread.anchor_id.in_(list(anchor_ids)),
            visible(ctx, "comment.read", CommentThread.engagement_id),
        )
        .group_by(CommentThread.anchor_id)
    )
    return [(a, int(n)) for a, n in found.tuples().all()]


async def list_checklist(
    session: AsyncSession, ctx: AuthContext, todo_ids: Sequence[UUID]
) -> list[TodoChecklistItem]:
    found = await session.execute(
        select(TodoChecklistItem)
        .join(Todo, Todo.id == TodoChecklistItem.todo_id)
        .where(
            TodoChecklistItem.todo_id.in_(list(todo_ids)),
            or_(visible(ctx, "todo.read", _TODO_ENGAGEMENT), _own_firm_todo(ctx)),
        )
        .order_by(TodoChecklistItem.todo_id, TodoChecklistItem.position)
    )
    return list(found.scalars().all())


async def insert_checklist_items(
    session: AsyncSession, tenant_id: UUID, todo_id: UUID, texts: Sequence[tuple[int, str]]
) -> None:
    if not texts:
        return
    await session.execute(
        insert(TodoChecklistItem),
        [{"tenant_id": tenant_id, "todo_id": todo_id, "position": p, "text": t} for p, t in texts],
    )


async def checklist_count(session: AsyncSession, todo_id: UUID) -> int:
    found = await session.scalar(
        select(func.count())
        .select_from(TodoChecklistItem)
        .where(TodoChecklistItem.todo_id == todo_id)
    )
    return int(found or 0)


async def get_checklist_item(
    session: AsyncSession, todo_id: UUID, item_id: UUID
) -> TodoChecklistItem | None:
    found = await session.execute(
        select(TodoChecklistItem).where(
            TodoChecklistItem.id == item_id, TodoChecklistItem.todo_id == todo_id
        )
    )
    return found.scalar_one_or_none()


async def set_checklist_item(
    session: AsyncSession,
    item_id: UUID,
    *,
    text: str | None,
    done: bool | None,
    by: UUID,
) -> None:
    values: dict[str, Any] = {}  # Any: column values of mixed types
    if text is not None:
        values["text"] = text
    if done is not None:
        values.update(
            done=done, done_by=by if done else None, done_at=func.now() if done else None
        )
    if values:
        await session.execute(
            update(TodoChecklistItem).where(TodoChecklistItem.id == item_id).values(**values)
        )


async def remove_checklist_item(session: AsyncSession, todo_id: UUID, item_id: UUID) -> int:
    """Delete one item and close the gap in the positions (the constraint is deferrable)."""
    removed = await session.execute(
        delete(TodoChecklistItem)
        .where(TodoChecklistItem.id == item_id, TodoChecklistItem.todo_id == todo_id)
        .returning(TodoChecklistItem.position)
    )
    position = removed.scalar_one_or_none()
    if position is None:
        return 0
    await session.execute(text("SET CONSTRAINTS todo_checklist_items_position DEFERRED"))
    await session.execute(
        update(TodoChecklistItem)
        .where(TodoChecklistItem.todo_id == todo_id, TodoChecklistItem.position > position)
        .values(position=TodoChecklistItem.position - 1)
    )
    return 1


def bucket_of(due_on: date | None, today: date) -> str:
    """AC-23, AC-29: the My to-dos band, derived in the firm's zone; never stored. This week
    runs to the coming Sunday."""
    if due_on is None:
        return "no_date"
    if due_on < today:
        return "overdue"
    if due_on == today:
        return "today"
    end_of_week = today.toordinal() + (6 - today.weekday())
    return "this_week" if due_on.toordinal() <= end_of_week else "later"


async def shared_threads_on_anchor(
    session: AsyncSession, anchor_kind: str, anchor_id: UUID
) -> list[CommentThread]:
    """R-02-T22: the shared threads on one anchor, for the client path once the anchor's provider
    has authorised the client (LIST_EXEMPT)."""
    found = await session.execute(
        select(CommentThread)
        .where(
            CommentThread.anchor_kind == anchor_kind,
            CommentThread.anchor_id == anchor_id,
            CommentThread.visibility == "shared",
        )
        .order_by(CommentThread.created_at, CommentThread.id)
    )
    return list(found.scalars().all())


async def comments_of_threads(
    session: AsyncSession, thread_ids: Sequence[UUID]
) -> list[tuple[ThreadComment, ThreadCommentRedaction | None]]:
    """R-02-T22: the comments of threads the client path already narrowed, oldest first."""
    if not thread_ids:
        return []
    found = await session.execute(
        select(ThreadComment, ThreadCommentRedaction)
        .outerjoin(
            ThreadCommentRedaction,
            and_(
                ThreadCommentRedaction.tenant_id == ThreadComment.tenant_id,
                ThreadCommentRedaction.comment_id == ThreadComment.id,
            ),
        )
        .where(ThreadComment.thread_id.in_(list(thread_ids)))
        .order_by(ThreadComment.created_at, ThreadComment.id)
    )
    return [(c, r) for c, r in found.tuples().all()]
