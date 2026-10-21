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
