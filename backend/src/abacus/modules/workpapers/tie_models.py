"""Tie-out checks (SPEC-310; TASK-321). Insert-only definitions; results computed on read."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import FetchedValue, Numeric
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from abacus.kernel.db import Base


class TieOutCheck(Base):
    __tablename__ = "tie_out_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    target_type: Mapped[str]
    target_id: Mapped[UUID]
    key: Mapped[str]
    kind: Mapped[str]
    current_version_no: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # 0193 (A-02-T11): the issue a check that does not tie is linked to; all three or none.
    issue_id: Mapped[UUID | None]
    issue_linked_by: Mapped[UUID | None]
    issue_linked_at: Mapped[datetime | None]


class TieOutCheckVersion(Base):
    __tablename__ = "tie_out_check_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    check_id: Mapped[UUID]
    version_no: Mapped[int]
    label: Mapped[str]
    actual_selector: Mapped[dict[str, Any]] = mapped_column(JSONB)  # Any: JSON
    expected: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    citation_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid[UUID](as_uuid=True)))
    tolerance: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    reason: Mapped[str | None]
    created_by: Mapped[UUID]
    actor_kind: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
