"""Domain events published by collaboration (P-05 §4.6; ADR-018). Identifiers and enums only:
never a comment body, a row's text, a title or a name (chapter 03 rule 8). `mention.created` is
distinct from the live SPEC-032 `comment.mentioned` until CL-1 (ADR-236)."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from pydantic import Field

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent

Id = Annotated[UUID, classified("internal")]
OptId = Annotated[UUID | None, classified("internal")]
Code = Annotated[str, classified("internal")]


class CommentCreated(DomainEvent):
    event_type: ClassVar[str] = "comment.created"

    comment_id: Id
    thread_id: Id
    anchor_kind: Code
    anchor_id: Id
    engagement_id: Id


class MentionCreated(DomainEvent):
    """One per mentioned person (AC-7); notifications fan it out as the kind `mention`."""

    event_type: ClassVar[str] = "mention.created"

    comment_id: Id
    thread_id: Id
    anchor_kind: Code
    anchor_id: Id
    engagement_id: Id
    user_id: Id
    # The notifications catalogue's `mention` recipients read this key (SPEC-032's shape).
    mentioned_user_ids: Annotated[list[UUID], classified("internal")] = Field(
        default_factory=list[UUID]
    )


class ThreadResolved(DomainEvent):
    event_type: ClassVar[str] = "comment_thread.resolved"

    thread_id: Id
    anchor_kind: Code
    anchor_id: Id
    engagement_id: Id


class ThreadReopened(DomainEvent):
    event_type: ClassVar[str] = "comment_thread.reopened"

    thread_id: Id
    anchor_kind: Code
    anchor_id: Id
    engagement_id: Id


# Each to-do event carries the same identifiers (a DomainEvent subclass names its own type).


class TodoCreated(DomainEvent):
    event_type: ClassVar[str] = "todo.created"

    todo_id: Id
    scope_kind: Code
    engagement_id: OptId = None
    anchor_kind: Annotated[str | None, classified("internal")] = None
    anchor_id: OptId = None
    assignee_user_id: Id


class TodoUpdated(DomainEvent):
    event_type: ClassVar[str] = "todo.updated"

    todo_id: Id
    scope_kind: Code
    engagement_id: OptId = None
    anchor_kind: Annotated[str | None, classified("internal")] = None
    anchor_id: OptId = None
    assignee_user_id: Id


class TodoCompleted(DomainEvent):
    event_type: ClassVar[str] = "todo.completed"

    todo_id: Id
    scope_kind: Code
    engagement_id: OptId = None
    anchor_kind: Annotated[str | None, classified("internal")] = None
    anchor_id: OptId = None
    assignee_user_id: Id


class TodoReopened(DomainEvent):
    event_type: ClassVar[str] = "todo.reopened"

    todo_id: Id
    scope_kind: Code
    engagement_id: OptId = None
    anchor_kind: Annotated[str | None, classified("internal")] = None
    anchor_id: OptId = None
    assignee_user_id: Id


class TodoMoved(DomainEvent):
    event_type: ClassVar[str] = "todo.moved"

    todo_id: Id
    scope_kind: Code
    engagement_id: OptId = None
    anchor_kind: Annotated[str | None, classified("internal")] = None
    anchor_id: OptId = None
    assignee_user_id: Id


class TodoDeleted(DomainEvent):
    event_type: ClassVar[str] = "todo.deleted"

    todo_id: Id
    scope_kind: Code
    engagement_id: OptId = None
    anchor_kind: Annotated[str | None, classified("internal")] = None
    anchor_id: OptId = None
    assignee_user_id: Id


class TodoAssigned(DomainEvent):
    """Notifications fan it out as `todo_assigned` to the assignee (P-05 §4.8)."""

    event_type: ClassVar[str] = "todo.assigned"

    todo_id: Id
    assignee_user_id: Id
    assigned_by: Id
    engagement_id: OptId = None
