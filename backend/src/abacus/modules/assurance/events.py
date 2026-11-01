"""The assurance module's outbox events (A-04 §4.5): identifiers only (ADR-007)."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class MaterialityDecided(DomainEvent):
    """The engagement partner decided materiality: A-03's sampling hold and I-01 read it."""

    event_type: ClassVar[str] = "materiality.decided"

    version_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    decision_id: Annotated[UUID, classified("internal")]


class MaterialityReassessed(DomainEvent):
    """The partner recorded a reassessment at the final basis: No change or Revise (AC3.6)."""

    event_type: ClassVar[str] = "materiality.reassessed"

    version_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    decision_id: Annotated[UUID, classified("internal")]
    revised: Annotated[bool, classified("internal")]


class MaterialityRevised(DomainEvent):
    """A revision's impact list (AC3.7): the preparers of each impacted workpaper are told
    (`materiality_revised`); nothing is recomputed silently."""

    event_type: ClassVar[str] = "materiality.revised"

    version_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]
