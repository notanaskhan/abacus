"""Domain events published by the engagements module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class EngagementCreated(DomainEvent):
    event_type: ClassVar[str] = "engagement.created"

    engagement_id: Annotated[UUID, classified("internal")]


class IndependenceRequested(DomainEvent):
    """Someone joined an engagement's team and must confirm their independence (SPEC-025)."""

    event_type: ClassVar[str] = "independence.requested"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]
