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
