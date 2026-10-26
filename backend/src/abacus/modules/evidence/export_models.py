"""Engagement export rows (A-01-T18; migration 0191; A-01 §4.2 M2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, FetchedValue
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class EngagementExport(Base):
    """One binder export of an audit work item. The app inserts the request; the status moves
    forward only and the stamps are written once each (the guard trigger)."""

    __tablename__ = "engagement_exports"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    client_id: Mapped[UUID]
    kind: Mapped[str]
    scope: Mapped[dict[str, Any]] = mapped_column(JSONB)  # Any: JSON
    format_version: Mapped[str]
    requested_by: Mapped[UUID]
    requested_by_kind: Mapped[str]
    requested_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    mfa_at: Mapped[datetime]
    grant_id: Mapped[UUID]
    not_before: Mapped[datetime]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    as_of_seq: Mapped[int | None] = mapped_column(BigInteger)
    bundle_sha256: Mapped[str | None]
    manifest_sha256: Mapped[str | None]
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    file_count: Mapped[int | None]
    request_count: Mapped[int | None]
    segment_count: Mapped[int | None]
    object_prefix: Mapped[str | None]
    ready_at: Mapped[datetime | None]
    expires_at: Mapped[datetime | None]
    failure_code: Mapped[str | None]
    void_reason: Mapped[str | None]
    undone_at: Mapped[datetime | None]
    undone_by: Mapped[UUID | None]


class EngagementExportContent(Base):
    """An evidence version a package holds (insert-only), for voiding on withdrawal."""

    __tablename__ = "engagement_export_contents"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    export_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_version_id: Mapped[UUID] = mapped_column(primary_key=True)
