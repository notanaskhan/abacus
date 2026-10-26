"""Domain events the workpapers module announces. Identifiers only (ADR-031)."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class WorkpaperContentChanged(DomainEvent):
    """A paper's signed content changed (cells or citations): P-04-T19's stale detector tells
    whoever signed an earlier content. Staleness itself stays computed (ADR-160 clause 3)."""

    event_type: ClassVar[str] = "workpaper.content_changed"

    workpaper_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
