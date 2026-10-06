"""Agent runs and screening results (TASK-011 design §6)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ARRAY, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    agent_id: Mapped[str]
    spec_version: Mapped[int]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID | None]
    initiator_user_id: Mapped[UUID]
    source_event_id: Mapped[UUID | None]
    task_scope: Mapped[list[str]] = mapped_column(ARRAY(String))
    status: Mapped[str]
    context_hash: Mapped[str | None]
    output: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None]
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    agent_run_id: Mapped[UUID]
    action: Mapped[str]
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    rationale: Mapped[str]
    citations: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    unverified: Mapped[list[str]] = mapped_column(JSONB)
    created_by_kind: Mapped[str]
    created_at: Mapped[datetime]
