"""The signatures module's outbox events (N-02 §4.5): identifiers and codes only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class EnvelopeCompleted(DomainEvent):
    """Every signer has signed, or a person imported the signed package (record mode)."""

    event_type: ClassVar[str] = "envelope.completed"

    envelope_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    purpose: Annotated[str, classified("internal")]
    provider: Annotated[str, classified("internal")]
    source_kind: Annotated[str, classified("internal")]
    source_id: Annotated[UUID, classified("internal")]
    imported_by: Annotated[UUID | None, classified("internal")]
