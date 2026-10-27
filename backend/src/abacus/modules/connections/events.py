"""Domain events published by the connections module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class ConnectionCreated(DomainEvent):
    """A client connected their ledger: the engagement's leads are notified (SPEC-020)."""

    event_type: ClassVar[str] = "connection.created"

    connection_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by: Annotated[UUID, classified("internal")]


class ConnectionRevoked(DomainEvent):
    """A connection ended: the engagement's leads are notified (SPEC-020, TASK-036 D5)."""

    event_type: ClassVar[str] = "connection.revoked"

    connection_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by: Annotated[UUID, classified("internal")]


class ConnectionReauthorized(DomainEvent):
    """A client signed in again on a connection that needed it (A-02-T16; POR-16 d): the same
    connection is active again; consumers resume what waited on it."""

    event_type: ClassVar[str] = "connection.reauthorized"

    connection_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by: Annotated[UUID, classified("internal")]


class LedgerSnapshotRecorded(DomainEvent):
    """A trial balance snapshot was recorded (SPEC-034; TASK-069): general ledgers waiting for
    it are checked."""

    event_type: ClassVar[str] = "ledger_snapshot.recorded"

    client_entity_id: Annotated[UUID, classified("internal")]
    snapshot_id: Annotated[UUID, classified("internal")]


class ConnectionNeedsReauth(DomainEvent):
    """A-02-T25: the daily health pass found a connection whose grant expired or was refused
    (`token_expired`, `invalid_grant`): it now needs its client to sign in again. Published once
    per transition, so its leads are told once (C16 `connection_needs_reauth`)."""

    event_type: ClassVar[str] = "connection.needs_reauth"

    connection_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    reason: Annotated[str, classified("internal")]


class ConnectionReauthDue(DomainEvent):
    """A-02-T25: a connection's grant ends within `REAUTH_NOTICE_DAYS` (`reauth_due_at`); told
    once per due date (`reauth_noticed_for`)."""

    event_type: ClassVar[str] = "connection.reauth_due"

    connection_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
