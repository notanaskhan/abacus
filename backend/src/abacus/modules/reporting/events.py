"""The statements' outbox events (A-06 §4.5). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class StatementDraftRequested(DomainEvent):
    """A person asked for a draft: starts `FsDraftWorkflow`."""

    event_type: ClassVar[str] = "statement.draft_requested"

    run_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]


class StatementTieOutRequested(DomainEvent):
    """A person asked for a tie-out: starts `TieOutWorkflow`."""

    event_type: ClassVar[str] = "statement.tie_out_requested"

    statement_version_id: Annotated[UUID, classified("internal")]


class TieOutCompleted(DomainEvent):
    """Code tied the version (A-06 §4.5's `tie_out.completed`)."""

    event_type: ClassVar[str] = "tie_out.completed"

    statement_version_id: Annotated[UUID, classified("internal")]
    tie_out_run_id: Annotated[UUID, classified("internal")]


# --- C10 (R-02-T09; R-02 §4.6): identifiers only ---------------------------------------------


class DeliverablePublished(DomainEvent):
    """A deliverable version is published to its audiences. Notifications read it: "Deliverable
    ready" for a non-draft version with no approval item (R-02 AC-36)."""

    event_type: ClassVar[str] = "deliverable.published"

    deliverable_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    is_draft: Annotated[bool, classified("internal")]
    has_approval: Annotated[bool, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")] = None
    work_item_id: Annotated[UUID | None, classified("internal")] = None


class DeliverableSuperseded(DomainEvent):
    event_type: ClassVar[str] = "deliverable.superseded"

    deliverable_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]


class DeliverableWithdrawn(DomainEvent):
    event_type: ClassVar[str] = "deliverable.withdrawn"

    deliverable_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
