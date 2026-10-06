"""Domain events published by the engagements module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class EngagementCreated(DomainEvent):
    event_type: ClassVar[str] = "engagement.created"

    engagement_id: Annotated[UUID, classified("internal")]
