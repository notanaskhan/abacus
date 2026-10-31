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


class WorkpaperVersionCreated(DomainEvent):
    """A-04-T04 (DEC-1762): an edit made the paper's next numbered version. Consumers (the
    cockpit rail, A-04's re-draft consumer) read the paper; staleness stays computed."""

    event_type: ClassVar[str] = "workpaper.version_created"

    workpaper_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]


class TieOutCheckChanged(DomainEvent):
    """A tie-out check on a trial balance was defined, edited or linked to an issue (A-02-T17):
    the trial balance's signed content includes its checks, so P-04-T19's stale detector tells
    whoever signed the trial balance before the change (SPEC-333 AC-13)."""

    event_type: ClassVar[str] = "tie_out_check.changed"

    check_id: Annotated[UUID, classified("internal")]
    trial_balance_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
