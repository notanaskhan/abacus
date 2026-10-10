"""Agent runs and screening results (TASK-011 design §6)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, FetchedValue, Numeric, String
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
    # Waiting for a work slot (SPEC-003 AC-13): the run is still `running`, reported as queued.
    queued_reason: Mapped[str | None]
    estimated_start_at: Mapped[datetime | None]
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


class KnowledgeDocument(Base):
    """A firm's methodology document (SPEC-009). Text lives in its chunks."""

    __tablename__ = "knowledge_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    title: Mapped[str]
    source_kind: Mapped[str]
    media_type: Mapped[str]
    fingerprint: Mapped[str]
    char_count: Mapped[int]
    status: Mapped[str]
    failure_code: Mapped[str | None]
    added_by: Mapped[UUID]
    created_at: Mapped[datetime]
    withdrawn_at: Mapped[datetime | None]


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    heading_path: Mapped[str]
    text: Mapped[str]
    char_count: Mapped[int]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    embedding_model: Mapped[str | None]
    embedded_at: Mapped[datetime | None]


class EngagementAgentState(Base):
    """SPEC-027 (TASK-050): an engagement's agent paused or resumed (partner or manager)."""

    __tablename__ = "engagement_agents"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(primary_key=True)
    paused_at: Mapped[datetime | None]
    paused_by: Mapped[UUID | None]
    reason: Mapped[str | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class AgentActivity(Base):
    """SPEC-027 AC-7: one automatic action, by which policy and why. Insert-only; references
    only, never client content."""

    __tablename__ = "agent_activity"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    policy: Mapped[str]
    policy_version: Mapped[int]
    action: Mapped[str]
    outcome: Mapped[str]
    reason: Mapped[str | None]
    record_type: Mapped[str | None]
    record_id: Mapped[UUID | None]
    item_count: Mapped[int | None]
    for_user: Mapped[UUID | None]
    source_event_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
