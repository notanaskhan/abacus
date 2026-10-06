"""Engagements (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    client_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    name: Mapped[str]
    type: Mapped[str]
    fiscal_period_start: Mapped[date]
    fiscal_period_end: Mapped[date]
    status: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]
