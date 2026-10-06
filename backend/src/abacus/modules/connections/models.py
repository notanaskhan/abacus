"""Connections and sync runs (glossary). TASK-010 design §4."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import ARRAY, String
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    provider: Mapped[str]
    status: Mapped[str]
    scopes: Mapped[list[str]] = mapped_column(ARRAY(String))
    expires_at: Mapped[datetime | None]
    created_by: Mapped[str]
    created_at: Mapped[datetime]


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    connection_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    dataset: Mapped[str]
    period_start: Mapped[date]
    period_end: Mapped[date]
    status: Mapped[str]
    raw_storage_key: Mapped[str | None]
    raw_version_id: Mapped[str | None]
    raw_fingerprint: Mapped[str | None]
    raw_size_bytes: Mapped[int | None]
    raw_pulled_at: Mapped[datetime | None]
    source: Mapped[str | None]
    snapshot_id: Mapped[UUID | None]
    evidence_version_id: Mapped[UUID | None]
    failure_code: Mapped[str | None]
    started_by: Mapped[str]
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
