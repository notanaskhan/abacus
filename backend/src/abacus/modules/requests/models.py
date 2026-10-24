"""Request lists and request items (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.dialects.postgresql import JSONB
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
    # F-03-T14 (0070): a binder on a work item; one per (work item, kind, part).
    work_item_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    name: Mapped[str] = mapped_column(server_default=FetchedValue())
    kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    part: Mapped[int] = mapped_column(server_default=FetchedValue())
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    published_at: Mapped[datetime | None]
    published_by: Mapped[UUID | None]
    marked_done_at: Mapped[datetime | None]
    marked_done_by: Mapped[UUID | None]
    prior_year_source_ref: Mapped[UUID | None]
    # P-06-T05 (0100): the binder engine's stamps.
    unpublished_at: Mapped[datetime | None]
    unpublished_by: Mapped[UUID | None]
    unpublish_reason_sealed: Mapped[bytes | None]
    created_from: Mapped[str] = mapped_column(server_default=FetchedValue())
    template_ref: Mapped[str | None]
    follow_up_override: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON values
    closed_at: Mapped[datetime | None]
    closed_reason: Mapped[str | None]


class BinderActivity(Base):
    """The binder-list projection (P-06-T05, 0100): status, open count and the last client
    activity, read by the binders index (P-06-T11). The app inserts and updates the projection
    columns only, never deletes."""

    __tablename__ = "binder_activity"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    binder_id: Mapped[UUID] = mapped_column(primary_key=True)
    work_item_id: Mapped[UUID | None]
    status: Mapped[str]
    open_count: Mapped[int] = mapped_column(server_default=FetchedValue())
    last_client_activity_at: Mapped[datetime | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class RequestCategory(Base):
    """A binder's section (F-03-T14). Insert-only."""

    __tablename__ = "request_categories"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    request_list_id: Mapped[UUID]
    name: Mapped[str]
    position: Mapped[int]


class BinderRecipient(Base):
    """Who a binder is for (P-06-T05). Insert-only: a removal is a new row with `removed_at`."""

    __tablename__ = "binder_recipients"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    binder_id: Mapped[UUID]
    contact_id: Mapped[UUID]
    added_by: Mapped[UUID]
    added_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    removed_at: Mapped[datetime | None]


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
    # F-03-T15 (0071): the v2 lifecycle stamps.
    requested_at: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]
    client_ignored_at: Mapped[datetime | None]
    # P-06-T05 (0100): the binder engine's request fields.
    title: Mapped[str | None]
    category_id: Mapped[UUID | None]
    kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    source_tag: Mapped[str | None]
    sent_by: Mapped[UUID | None]
    deleted_at: Mapped[datetime | None]
    incorporation_state: Mapped[str] = mapped_column(server_default=FetchedValue())
    # P-06-T10: the rest of the v2 record (0071, 0100).
    na_reason: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    na_note: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    na_by: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    na_at: Mapped[datetime | None] = mapped_column(server_default=FetchedValue())
    incorporated_by: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    incorporated_at: Mapped[datetime | None] = mapped_column(server_default=FetchedValue())
    firm_owner_user_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    period_start: Mapped[date | None] = mapped_column(server_default=FetchedValue())
    period_end: Mapped[date | None] = mapped_column(server_default=FetchedValue())
    wave: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    supports_ref: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    # {kind, id}: an opaque reference to what the request supports.
    linked_ref: Mapped[dict[str, Any] | None] = mapped_column(  # Any: JSON scalars
        JSONB, server_default=FetchedValue()
    )
    drafted_by_run_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    drafted_wording_source: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    drafted_wording_fingerprint: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    deleted_by: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())


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


class FulfilmentWithdrawal(Base):
    """A fulfilment voided because its version was withdrawn by the client (P-06-T19; ADR-162).
    Insert-only; requests reads leave such fulfilments out."""

    __tablename__ = "fulfilment_withdrawals"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    fulfilment_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    withdrawn_by_user_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


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
