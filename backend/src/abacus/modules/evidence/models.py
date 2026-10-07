"""Evidence items and versions (glossary). TASK-009 design §4."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    title: Mapped[str]
    created_by_kind: Mapped[str]
    created_by_id: Mapped[str]
    created_at: Mapped[datetime]


class EvidenceVersion(Base):
    __tablename__ = "evidence_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_item_id: Mapped[UUID]
    version_no: Mapped[int]
    fingerprint: Mapped[str]
    storage_key: Mapped[str]
    storage_version_id: Mapped[str]
    size_bytes: Mapped[int]
    media_type: Mapped[str]
    source: Mapped[str]
    method: Mapped[str]
    pulled_at: Mapped[datetime | None]
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    client_entity_id: Mapped[UUID | None]
    snapshot_id: Mapped[UUID | None]
    idempotency_key: Mapped[str | None]
    created_at: Mapped[datetime]


class ReviewDecision(Base):
    """A person's accept, reject or send back of one evidence version (SPEC-004; ADR-005).
    Insert-only and immutable; the database refuses a non-human actor."""

    __tablename__ = "review_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    decision: Mapped[str]
    reason_code: Mapped[str | None]
    note: Mapped[str | None]
    screening_result_id: Mapped[UUID | None]
    corrects_proposal: Mapped[bool]
    actor_kind: Mapped[str]
    actor_id: Mapped[str]
    created_at: Mapped[datetime]


class ReviewAssignment(Base):
    """Who has taken a queued version (advisory, SPEC-004 Q3); None once released."""

    __tablename__ = "review_assignments"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID]
    assignee_user_id: Mapped[UUID | None]
    assigned_by: Mapped[UUID]
    assigned_at: Mapped[datetime]
