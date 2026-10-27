"""Outbox events of the engagement export (A-01 §4.6; SPEC-344 §8; engagement-export v1 §7).
Identifiers only: notifications consumes `ready` and `failed` (A-01-T22) and loads what it
shows under its own context."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class _ExportEvent(DomainEvent):
    event_type: ClassVar[str] = "engagement_export.event"

    export_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    requested_by: Annotated[UUID, classified("internal")]


class EngagementExportRequested(_ExportEvent):
    """A person asked for an export; its workflow waits out the Undo window (A-01-T19)."""

    event_type: ClassVar[str] = "engagement_export.requested"


class EngagementExportUndone(_ExportEvent):
    event_type: ClassVar[str] = "engagement_export.undone"


class EngagementExportReady(_ExportEvent):
    event_type: ClassVar[str] = "engagement_export.ready"


class EngagementExportFailed(_ExportEvent):
    event_type: ClassVar[str] = "engagement_export.failed"


class EngagementExportExpired(_ExportEvent):
    """A-01-T22: the 7 days passed (the sweep); its subscriber deletes the segments."""

    event_type: ClassVar[str] = "engagement_export.expired"


class EngagementExportVoided(_ExportEvent):
    """A-01-T22 (P-31): a version the package holds was withdrawn; the bundle is voided
    (`expired`, `withdrawn_content`) and its subscriber deletes the segments."""

    event_type: ClassVar[str] = "engagement_export.voided"
