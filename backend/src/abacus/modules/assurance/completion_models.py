"""Completion, release and archive records (SPEC-314; TASK-332). All insert-only."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class EqrConcurrence(Base):
    __tablename__ = "eqr_concurrences"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    digest_hash: Mapped[str]
    not_involved: Mapped[bool]
    concurred_by: Mapped[UUID]
    actor_kind: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class CompletionRecord(Base):
    __tablename__ = "completion_records"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    kind: Mapped[str]
    choice: Mapped[str | None]
    emphasis: Mapped[bool | None]
    document_date: Mapped[date | None]
    evidence_version_id: Mapped[UUID | None]
    report_record_id: Mapped[UUID | None]
    rationale: Mapped[str | None]
    recorded_by: Mapped[UUID]
    actor_kind: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Release(Base):
    __tablename__ = "releases"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    report_record_id: Mapped[UUID]
    report_date: Mapped[date]
    documentation_due: Mapped[date]
    gates: Mapped[dict[str, Any]] = mapped_column(JSONB)  # Any: JSON
    released_by: Mapped[UUID]
    actor_kind: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Archive(Base):
    __tablename__ = "archives"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    seal: Mapped[str]
    leaf_count: Mapped[int]
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)  # Any: JSON
    locked_by: Mapped[UUID]
    actor_kind: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
