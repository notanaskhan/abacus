"""Firm integrations and their sealed secrets (A-02-T12; migration 0194). The catalogue is a
global table read through `integration_catalog_rows()`; it has no ORM model here."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class FirmIntegration(Base):
    __tablename__ = "firm_integrations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    catalog_key: Mapped[str]
    status: Mapped[str]
    mode: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    version: Mapped[int] = mapped_column(server_default=FetchedValue())


class IntegrationSecret(Base):
    """An install's credentials, sealed with the tenant key and the install's id as associated
    data (ADR-035). Restricted: never logged, never returned by a route."""

    __tablename__ = "integration_secrets"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    firm_integration_id: Mapped[UUID]
    sealed: Mapped[bytes] = mapped_column(LargeBinary)
    key_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
