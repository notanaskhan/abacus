"""Domain events published by the communications module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class MessageReady(DomainEvent):
    """A checked message for delivery (a transport consumes it, increments 2 and 8)."""

    event_type: ClassVar[str] = "message.ready"
    message_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]


class MessageBounced(DomainEvent):
    """SES reported a bounce for this send (Q-01-T46). A permanent one suppressed the address."""

    event_type: ClassVar[str] = "message.bounced"
    message_id: Annotated[UUID, classified("internal")]


class MessageComplained(DomainEvent):
    """The recipient marked this send as spam (Q-01-T46); the address is suppressed."""

    event_type: ClassVar[str] = "message.complained"
    message_id: Annotated[UUID, classified("internal")]
