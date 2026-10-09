"""Connections and sync runs (glossary). TASK-010 design §4."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import ARRAY, FetchedValue, LargeBinary, String
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
    # SPEC-020 (TASK-036): health checks and revocation.
    last_checked_at: Mapped[datetime | None]
    last_check_ok: Mapped[bool | None]
    revoked_at: Mapped[datetime | None]
    revoked_by: Mapped[str | None]


class ConnectionState(Base):
    """One started connection flow: single-use, short-lived, the state kept only as a hash."""

    __tablename__ = "connection_states"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    user_id: Mapped[UUID]
    provider: Mapped[str]
    state_hash: Mapped[str]
    created_at: Mapped[datetime]
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]


class ConnectionSecret(Base):
    """A connection's provider credentials, sealed with the tenant's key (ADR-035)."""

    __tablename__ = "connection_secrets"

    connection_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    sealed: Mapped[bytes] = mapped_column(LargeBinary)
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
    # Waiting for a work slot (SPEC-003 AC-13): the run is still `running`, reported as queued.
    queued_reason: Mapped[str | None]
    estimated_start_at: Mapped[datetime | None]
    started_by: Mapped[str]
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]
