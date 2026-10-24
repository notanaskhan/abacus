"""Assurance phase events (A-01-T05; migration 0134). Insert-only."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class AssurancePhaseEvent(Base):
    __tablename__ = "assurance_phase_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    from_phase: Mapped[str]
    to_phase: Mapped[str]
    mode: Mapped[str]
    reason_sealed: Mapped[bytes | None]
    gate_ref: Mapped[str | None]
    actor_kind: Mapped[str]
    actor_user_id: Mapped[UUID | None]
    mfa_at: Mapped[datetime | None]
    recorded_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
