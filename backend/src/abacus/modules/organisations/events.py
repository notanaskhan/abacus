"""Domain events published by the organisations module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class ClientUpdated(DomainEvent):
    """A person changed the client record (P-07-T09): which fields, never their values."""

    event_type: ClassVar[str] = "client.updated"

    client_id: Annotated[UUID, classified("internal")]
    fields: Annotated[list[str], classified("internal")]
