"""The practice module's records (I-01). First table: Home's client activity (I-01-T12, 0320)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class HomeActivityItem(Base):
    """One allowlisted event about a client, for HOME-01's "Client activity" (I-01-T12; AC4.3).
    A rebuildable projection: identifiers, codes and counts only, inserted once per outbox event
    and deleted after 90 days; never updated."""

    __tablename__ = "home_activity_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    source_event_id: Mapped[UUID]
    event_type: Mapped[str]
    occurred_at: Mapped[datetime]
    client_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID | None]
    office_id: Mapped[UUID | None]
    actor_kind: Mapped[str]
    actor_ref: Mapped[dict[str, str]] = mapped_column(JSONB)
    subject_ref: Mapped[dict[str, str]] = mapped_column(JSONB)
    facts: Mapped[dict[str, str | int | bool]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
