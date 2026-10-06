"""Domain events published by the evidence module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class EvidenceVersionCreated(DomainEvent):
    event_type: ClassVar[str] = "evidence_version.created"

    evidence_version_id: Annotated[UUID, classified("internal")]
    evidence_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    # The person this version was added for: the uploader, or whoever a system run acts for.
    # Agents acting on the version act on their behalf (ADR-025; TASK-011 Q1).
    requested_by: Annotated[UUID | None, classified("internal")] = None
