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
