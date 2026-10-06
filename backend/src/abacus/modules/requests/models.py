"""Request lists and request items (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class RequestList(Base):
    __tablename__ = "request_lists"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    created_at: Mapped[datetime]


class RequestItem(Base):
    __tablename__ = "request_items"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    request_list_id: Mapped[UUID]
    description: Mapped[str]
    audit_area: Mapped[str]
    status: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]


class Fulfilment(Base):
    __tablename__ = "fulfilments"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    created_by_kind: Mapped[str]
    created_by_id: Mapped[str]
    created_at: Mapped[datetime]
