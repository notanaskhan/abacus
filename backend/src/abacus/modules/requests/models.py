"""Request lists and request items (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

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
