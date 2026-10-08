"""Domain events published by the gateway's budget checks (SPEC-007; notified, SPEC-013).
Identifiers and level only."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class BudgetSoftCrossed(DomainEvent):
    event_type: ClassVar[str] = "budget.soft_crossed"

    level: Annotated[Literal["engagement", "firm", "platform"], classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")] = None


class BudgetAnomaly(DomainEvent):
    event_type: ClassVar[str] = "budget.anomaly"

    engagement_id: Annotated[UUID, classified("internal")]
