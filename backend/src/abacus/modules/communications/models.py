"""Messages (SPEC-006). Insert-only: a message is recorded once, as sent or blocked."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    channel: Mapped[str]
    recipient_ref: Mapped[str]
    body: Mapped[str]
    status: Mapped[str]
    violations: Mapped[list[dict[str, str]]] = mapped_column(JSONB)
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]
