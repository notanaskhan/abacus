"""The collaboration tables of migration 0760 (P-05-T04; ADR-236 proposed), mapped for the
repository. Writes name only the columns the app role may insert or update
(`registry.INSERT_COLUMNS`, `UPDATE_COLUMNS`); everything else is server-set."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ARRAY, FetchedValue
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class CommentThread(Base):
    __tablename__ = "comment_threads"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID | None]
    client_id: Mapped[UUID]
    anchor_kind: Mapped[str]
    anchor_id: Mapped[UUID]
    anchor_locator: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    anchor_locator_key: Mapped[str] = mapped_column(server_default=FetchedValue())
    opened_on_version_no: Mapped[int | None]
    pinned_version_no: Mapped[int | None]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    visibility: Mapped[str] = mapped_column(server_default=FetchedValue())
    shared_scope_kind: Mapped[str | None]
    shared_scope_id: Mapped[UUID | None]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    last_comment_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class CommentThreadEvent(Base):
    __tablename__ = "comment_thread_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    thread_id: Mapped[UUID]
    kind: Mapped[str]
    actor_user_id: Mapped[UUID]
    actor_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    ref_type: Mapped[str | None]
    ref_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ThreadComment(Base):
    __tablename__ = "thread_comments"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    thread_id: Mapped[UUID]
    author_user_id: Mapped[UUID]
    author_side: Mapped[str]
    body_sealed: Mapped[bytes]
    body_fingerprint: Mapped[str]
    corrects_comment_id: Mapped[UUID | None]
    citation_ids: Mapped[list[UUID]] = mapped_column(
        ARRAY(PgUUID(as_uuid=True)), server_default=FetchedValue()
    )
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ThreadCommentMention(Base):
    __tablename__ = "thread_comment_mentions"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    comment_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    via_team: Mapped[bool] = mapped_column(server_default=FetchedValue())


class ThreadCommentRedaction(Base):
    __tablename__ = "thread_comment_redactions"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    comment_id: Mapped[UUID] = mapped_column(primary_key=True)
    redacted_by: Mapped[UUID]
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class CommentThreadRead(Base):
    __tablename__ = "comment_thread_reads"

    # The table's key is UNIQUE (tenant_id, user_id, thread_id); mapped as the primary key.
    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    thread_id: Mapped[UUID] = mapped_column(primary_key=True)
    last_read_at: Mapped[datetime | None]
    muted_at: Mapped[datetime | None]


class Todo(Base):
    __tablename__ = "todos"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    scope_kind: Mapped[str]
    engagement_id: Mapped[UUID | None]
    work_item_id: Mapped[UUID | None]
    client_id: Mapped[UUID | None]
    title: Mapped[str]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    assignee_user_id: Mapped[UUID]
    due_on: Mapped[date | None]
    anchor_kind: Mapped[str | None]
    anchor_id: Mapped[UUID | None]
    anchor_locator: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    row_text_sealed: Mapped[bytes | None]
    row_text_fingerprint: Mapped[str | None]
    source_thread_id: Mapped[UUID | None]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    done_by: Mapped[UUID | None]
    done_at: Mapped[datetime | None]
    assignee_seen_at: Mapped[datetime | None]
    deleted_at: Mapped[datetime | None]
    deleted_by: Mapped[UUID | None]
    version: Mapped[int] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class TodoChecklistItem(Base):
    __tablename__ = "todo_checklist_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    todo_id: Mapped[UUID]
    position: Mapped[int]
    text: Mapped[str]
    done: Mapped[bool] = mapped_column(server_default=FetchedValue())
    done_by: Mapped[UUID | None]
    done_at: Mapped[datetime | None]
