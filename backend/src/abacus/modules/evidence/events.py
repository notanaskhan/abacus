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
