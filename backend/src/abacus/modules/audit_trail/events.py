"""Domain events the audit trail emits (ADR-018; G-02-T17). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class AuditExportRequested(DomainEvent):
    """A person asked for an audit-log export: its subscriber starts `AuditExportWorkflow`."""

    event_type: ClassVar[str] = "audit_export.requested"

    export_id: Annotated[UUID, classified("internal")]
    requested_by: Annotated[UUID, classified("internal")]


class AuditExportReady(DomainEvent):
    """The bundle is built and signed (`audit_export_ready`, C16: the requester only)."""

    event_type: ClassVar[str] = "audit_export.ready"

    export_id: Annotated[UUID, classified("internal")]
    requested_by: Annotated[UUID, classified("internal")]
