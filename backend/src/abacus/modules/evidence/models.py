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
    created_at: Mapped[datetime]
