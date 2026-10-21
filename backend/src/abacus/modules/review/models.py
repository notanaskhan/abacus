"""Review grammar records (P-04; ADR-136). First table: sign-offs (SPEC-308; TASK-319)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class SignOff(Base):
    """L1 preparer to L5 EQR on a registered reviewable, with the content hash signed.
    Insert-only; staleness is computed against the target's current hash."""

    __tablename__ = "sign_offs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    target_type: Mapped[str]
    target_id: Mapped[UUID]
    level: Mapped[int]
    content_hash: Mapped[str]
    signed_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ReviewableNote(Base):
    """A review note on a registered reviewable (SPEC-313; TASK-331). Insert-only."""

    __tablename__ = "reviewable_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    target_type: Mapped[str]
    target_id: Mapped[UUID]
    anchor: Mapped[str | None]
    body: Mapped[str]
    raised_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ReviewableNoteEvent(Base):
    __tablename__ = "reviewable_note_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    note_id: Mapped[UUID]
    kind: Mapped[str]
    body: Mapped[str | None]
    by_user: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
