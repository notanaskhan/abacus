"""Domain events published by the fieldwork module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class MaterialityProposed(DomainEvent):
    """SPEC-305 (TASK-306): a materiality version waits for the engagement partner's decision."""

    event_type: ClassVar[str] = "materiality.proposed"

    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]  # not notified of their own (TASK-307)


class RiskApprovalRequested(DomainEvent):
    """SPEC-305: a risk version with a significant risk or rebuttal waits for the partner."""

    event_type: ClassVar[str] = "risk.approval_requested"

    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]  # not notified of their own (TASK-307)
    risk_id: Annotated[UUID, classified("internal")]


class SeverityProposed(DomainEvent):
    """SPEC-305: a deficiency's severity waits for the partner to conclude it."""

    event_type: ClassVar[str] = "finding.severity_proposed"

    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]  # not notified of their own (TASK-307)
    finding_id: Annotated[UUID, classified("internal")]
