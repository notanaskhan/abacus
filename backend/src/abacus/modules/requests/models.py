"""Request lists and request items (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class RequestList(Base):
    __tablename__ = "request_lists"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    created_at: Mapped[datetime]
    # SPEC-027 (TASK-051): the date an item without its own is due.
    default_due_on: Mapped[date | None]


class RequestItem(Base):
    __tablename__ = "request_items"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    request_list_id: Mapped[UUID]
    description: Mapped[str]
    audit_area: Mapped[str]
    # From the methodology template that seeded the item (SPEC-008); None for items added by hand.
    retrievability_tier: Mapped[str | None]
    status: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]
    # SPEC-020: whether client users see the item, and the client contributor it's assigned to.
    client_visible: Mapped[bool]
    client_assignee_user_id: Mapped[UUID | None]
    # SPEC-022: what an A item needs, and where the tier came from (override, methodology, rule).
    dataset: Mapped[str | None]
    tier_source: Mapped[str | None]
    tier_rule: Mapped[str | None]
    # SPEC-027 (TASK-051): its own due date; None means the request list's default.
    due_on: Mapped[date | None]
    # SPEC-029 (TASK-055): the document the item expects, set by rule or by the team.
    document_kind: Mapped[str | None]
    document_kind_source: Mapped[str | None]
    # SPEC-031 (TASK-060): what the client reads about the request, and how the firm plans it.
    why: Mapped[str | None]
    good_looks_like: Mapped[str | None]
    still_needed: Mapped[str | None]
    blocks_fieldwork: Mapped[bool] = mapped_column(server_default=FetchedValue())
    effort: Mapped[str | None]
    guidance_source: Mapped[str | None]
    guidance_approved_by: Mapped[UUID | None]  # SPEC-035 (TASK-073): drafted guidance


class Fulfilment(Base):
    __tablename__ = "fulfilments"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    created_by_kind: Mapped[str]
    created_by_id: Mapped[str]
    created_at: Mapped[datetime]


# --- Comments (SPEC-032; TASK-062; ADR-109) ------------------------------------------------------


class Comment(Base):
    """Insert-only. The text is sealed per tenant (Restricted); `body_fingerprint` binds it."""

    __tablename__ = "comments"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID | None]
    author_user_id: Mapped[UUID]
    author_side: Mapped[str]
    visibility: Mapped[str]
    body_sealed: Mapped[bytes]
    body_fingerprint: Mapped[str]
    corrects_comment_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class CommentMention(Base):
    __tablename__ = "comment_mentions"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    comment_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)


class CommentRedaction(Base):
    __tablename__ = "comment_redactions"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    comment_id: Mapped[UUID] = mapped_column(primary_key=True)
    redacted_by: Mapped[UUID]
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class CommentRead(Base):
    __tablename__ = "comment_reads"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_version_id: Mapped[UUID | None]
    last_read_at: Mapped[datetime]


class ClientItemResponse(Base):
    """A client saying a request doesn't apply, or withdrawing that (SPEC-042). Insert-only."""

    __tablename__ = "client_item_responses"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    kind: Mapped[str]
    reason: Mapped[str | None]
    note: Mapped[str | None]
    by_user: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ClientListDone(Base):
    """The client admin marking their list done (SPEC-042). Insert-only."""

    __tablename__ = "client_list_done"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    by_user: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
