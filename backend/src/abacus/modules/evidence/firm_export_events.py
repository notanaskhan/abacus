"""Outbox events of the firm export (Q-02-T43; compliance-kernel §7). Identifiers only:
notifications tells the named approver of a request and both people of a ready archive; the
evidence module's own subscribers start the build and delete an expired archive's segments."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class _FirmExportEvent(DomainEvent):
    event_type: ClassVar[str] = "firm_export.event"

    export_id: Annotated[UUID, classified("internal")]
    requested_by: Annotated[UUID, classified("internal")]
    approver_user_id: Annotated[UUID, classified("internal")]


class FirmExportRequested(_FirmExportEvent):
    """A security admin asked; the named approver is told (`firm_export_approval_requested`)."""

    event_type: ClassVar[str] = "firm_export.requested"


class FirmExportApproved(_FirmExportEvent):
    """The named approver approved: its subscriber starts `FirmExportWorkflow`."""

    event_type: ClassVar[str] = "firm_export.approved"


class FirmExportReady(_FirmExportEvent):
    """The archive is built: both people are told (`firm_export_ready`)."""

    event_type: ClassVar[str] = "firm_export.ready"


class FirmExportExpired(_FirmExportEvent):
    """The 7 days passed (the sweep); its subscriber deletes the segments."""

    event_type: ClassVar[str] = "firm_export.expired"
