"""Firm integrations and their sealed secrets (A-02-T12; migration 0194), and C20 v2's personal
installs, OAuth states, events and Notify me (W-01-T04, 0890). The catalogue is a global table
read through `integration_catalog_rows()` and `integration_catalog_workbench()` (0901); it has no
ORM model here."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import FetchedValue, LargeBinary, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class FirmIntegration(Base):
    __tablename__ = "firm_integrations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    catalog_key: Mapped[str]
    status: Mapped[str]
    mode: Mapped[str]
    created_by: Mapped[UUID | None]  # NULL only for a firm app (0890)
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    version: Mapped[int] = mapped_column(server_default=FetchedValue())
    # W-01-T04 (0890): the drawer's facts.
    status_reason_code: Mapped[str | None]
    status_changed_at: Mapped[datetime | None]
    token_renews_at: Mapped[datetime | None]
    last_sync_at: Mapped[datetime | None]
    granted_scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=FetchedValue())
    consent_version: Mapped[int | None]
    connected_by: Mapped[UUID | None]
    connected_at: Mapped[datetime | None]


class IntegrationSecret(Base):
    """An install's credentials, sealed with the tenant key and the install's id as associated
    data (ADR-035). Restricted: never logged, never returned by a route."""

    __tablename__ = "integration_secrets"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    firm_integration_id: Mapped[UUID | None]
    user_integration_id: Mapped[UUID | None]  # W-01-T04: exactly one owner (0890)
    sealed: Mapped[bytes] = mapped_column(LargeBinary)
    key_id: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class IntegrationMapping(Base):
    """ADM-08's settings and mappings for an install (T-01-T20, migration 0466)."""

    __tablename__ = "integration_mappings"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    firm_integration_id: Mapped[UUID]
    kind: Mapped[str]
    source_key: Mapped[str]
    target_value: Mapped[str]
    direction: Mapped[str | None]
    version: Mapped[int] = mapped_column(server_default=FetchedValue())
    updated_by: Mapped[UUID]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class UserIntegration(Base):
    """A person's own install, "acting as you" (W-01-T04; one live per person and key)."""

    __tablename__ = "user_integrations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    user_id: Mapped[UUID]
    catalog_key: Mapped[str]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    status_reason_code: Mapped[str | None]
    status_changed_at: Mapped[datetime | None]
    connected_at: Mapped[datetime | None]
    token_renews_at: Mapped[datetime | None]
    last_sync_at: Mapped[datetime | None]
    granted_scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=FetchedValue())
    consent_version: Mapped[int | None]
    version: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class IntegrationOAuthState(Base):
    """A hashed single-use OAuth state with its sealed PKCE verifier (10 minutes; 0890)."""

    __tablename__ = "integration_oauth_states"

    state_sha256: Mapped[str] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    user_id: Mapped[UUID]
    catalog_key: Mapped[str]
    scope_kind: Mapped[str]
    purpose: Mapped[str]
    pkce_verifier_sealed: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    expires_at: Mapped[datetime]
    spent_at: Mapped[datetime | None]


class IntegrationEvent(Base):
    """One health or lifecycle event of an install (insert-only; 0890)."""

    __tablename__ = "integration_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    install_kind: Mapped[str]
    install_id: Mapped[UUID]
    catalog_key: Mapped[str]
    kind: Mapped[str]
    at: Mapped[datetime]
    actor_user_id: Mapped[UUID | None]
    subject_type: Mapped[str | None]
    subject_id: Mapped[UUID | None]
    run_id: Mapped[UUID | None]
    code: Mapped[str | None]
    http_status: Mapped[int | None]
    latency_ms: Mapped[int | None]


class IntegrationInterest(Base):
    """Notify me: a person asked to be told when a key becomes available (0890)."""

    __tablename__ = "integration_interest"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    catalog_key: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    notified_at: Mapped[datetime | None]
