"""Connections and sync runs (glossary). TASK-010 design §4."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ARRAY, FetchedValue, LargeBinary, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
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
    # 0195 (A-02-T13): entity-scoped connections. `display_label` is client content (masked,
    # rendered as text); `status_reason_code` is C20's reason for `needs_attention`.
    category: Mapped[str] = mapped_column(server_default=FetchedValue())
    external_account_ref: Mapped[str | None]
    display_label: Mapped[str | None]
    connected_by_user_id: Mapped[UUID | None]
    connected_at: Mapped[datetime | None]
    reauth_due_at: Mapped[datetime | None]
    last_sync_at: Mapped[datetime | None]
    status_reason_code: Mapped[str | None]
    # 0215 (A-02-T16): bumped on every status change (the portal's disconnect `seen_version`).
    version: Mapped[int] = mapped_column(server_default=FetchedValue())


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
    # 0215 (A-02-T16): POR-16's consent (same entity), and the connection a reconnect
    # re-authorises; both null for the legacy engagement flow (SPEC-020).
    consent_id: Mapped[UUID | None]
    connection_id: Mapped[UUID | None]
    category: Mapped[str | None]
    # The PKCE verifier, sealed (bound to `state_hash`); opened once at completion (review L6).
    verifier_sealed: Mapped[bytes | None] = mapped_column(LargeBinary)


class ConnectionGrantRevocation(Base):
    """A retired grant waiting for the provider's revoke (0215; review M1). Restricted: the
    sealed blob is never logged; the row is deleted once the revoke is answered."""

    __tablename__ = "connection_grant_revocations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    provider: Mapped[str]
    connection_id: Mapped[UUID | None]
    state_id: Mapped[UUID | None]  # an abandoned grant's state (review round 2, L3)
    sealed: Mapped[bytes] = mapped_column(LargeBinary)
    reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


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
    # 0195 (A-02-T13): null for a run no request item asked for (`trigger` says why it ran).
    request_item_id: Mapped[UUID | None]
    trigger: Mapped[str] = mapped_column(server_default=FetchedValue())
    label: Mapped[str | None]
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


class LedgerImport(Base):
    """SPEC-028 (TASK-052): one uploaded ledger export, its scan result and what became of it."""

    __tablename__ = "ledger_imports"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    format: Mapped[str]
    period_start: Mapped[date]
    period_end: Mapped[date]
    storage_key: Mapped[str]
    storage_version_id: Mapped[str]
    fingerprint: Mapped[str]
    size_bytes: Mapped[int]
    scan_status: Mapped[str] = mapped_column(server_default=FetchedValue())
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    failure_code: Mapped[str | None]
    # TASK-053 D1: what a failed check found, for the fixed message templates.
    difference: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    found_period_end: Mapped[date | None]
    totals_from_lines: Mapped[bool] = mapped_column(server_default=FetchedValue())
    uploaded_by: Mapped[UUID]
    on_behalf: Mapped[bool] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class GlImport(Base):
    """SPEC-034 (TASK-069): one uploaded general ledger export and where it stands."""

    __tablename__ = "gl_imports"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    kind: Mapped[str] = mapped_column(server_default=FetchedValue())  # year | subsequent
    engagement_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    format: Mapped[str]
    period_start: Mapped[date]
    period_end: Mapped[date]
    storage_key: Mapped[str]
    storage_version_id: Mapped[str]
    fingerprint: Mapped[str]
    size_bytes: Mapped[int]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    failure_code: Mapped[str | None]
    failure_details: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    gl_snapshot_id: Mapped[UUID | None]
    line_count: Mapped[int | None]
    uploaded_by: Mapped[UUID]
    on_behalf: Mapped[bool] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ConnectionConsent(Base):
    """What a client agreed to before the provider's sheet, as shown (0195; insert-only)."""

    __tablename__ = "connection_consents"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    connection_id: Mapped[UUID | None]
    client_entity_id: Mapped[UUID]
    catalog_key: Mapped[str]
    consent_version: Mapped[int]
    will: Mapped[list[str]] = mapped_column(ARRAY(String))
    wont: Mapped[list[str]] = mapped_column(ARRAY(String))
    authorization_text: Mapped[str]
    authorised_by_user_id: Mapped[UUID]
    ip_sha256: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ConnectionConsentLink(Base):
    """The connection a consent produced, recorded once (0195; insert-only)."""

    __tablename__ = "connection_consent_links"

    consent_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]  # the consent's and the connection's entity (review M2)
    connection_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ReconnectRequest(Base):
    """The firm asking the client to reconnect; one open per connection (0195)."""

    __tablename__ = "reconnect_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    connection_id: Mapped[UUID]
    requested_by_user_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    fulfilled_at: Mapped[datetime | None]
