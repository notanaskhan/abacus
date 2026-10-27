"""Firm export rows (Q-02-T43; migration 0216; compliance-kernel §3)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, FetchedValue
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class FirmExport(Base):
    """One export of everything the firm holds. The app inserts the request; the status moves
    forward only, the decision is the named approver's and the stamps are written once (the
    guard trigger)."""

    __tablename__ = "firm_exports"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    scope: Mapped[str] = mapped_column(server_default=FetchedValue())
    origin: Mapped[str] = mapped_column(server_default=FetchedValue())
    requested_by: Mapped[UUID]
    requested_by_kind: Mapped[str]
    requested_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    request_mfa_at: Mapped[datetime]
    approver_id: Mapped[UUID]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    decided_by: Mapped[UUID | None]
    decided_at: Mapped[datetime | None]
    decided_mfa_at: Mapped[datetime | None]
    decline_reason: Mapped[str | None]
    bundle_sha256: Mapped[str | None]
    manifest_sha256: Mapped[str | None]
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    segment_count: Mapped[int | None]
    object_prefix: Mapped[str | None]
    ready_at: Mapped[datetime | None]
    available_until: Mapped[datetime | None]
    downloaded_at: Mapped[datetime | None]
    failure_code: Mapped[str | None]


class FirmExportLink(Base):
    """One 15-minute link, bound to the person it was issued to (insert-only)."""

    __tablename__ = "firm_export_links"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    export_id: Mapped[UUID]
    user_id: Mapped[UUID]
    issued_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    expires_at: Mapped[datetime]
    mfa_at: Mapped[datetime]
