"""Domain events published by the evidence module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class EvidenceVersionCreated(DomainEvent):
    event_type: ClassVar[str] = "evidence_version.created"

    evidence_version_id: Annotated[UUID, classified("internal")]
    evidence_item_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    # The person this version was added for: the uploader, or whoever a system run acts for.
    # Agents acting on the version act on their behalf (ADR-025; TASK-011 Q1).
    requested_by: Annotated[UUID | None, classified("internal")] = None


class ReviewAssigned(DomainEvent):
    """A queued version was given to a reviewer (SPEC-004; notified, SPEC-013)."""

    event_type: ClassVar[str] = "review.assigned"

    engagement_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    assignee_user_id: Annotated[UUID, classified("internal")]


class InboxFileAdded(DomainEvent):
    """A file waits in the engagement's inbox (SPEC-023): the engagement agent's P-3 records how
    many request items the matching rule suggested for it (SPEC-027; TASK-050)."""

    event_type: ClassVar[str] = "inbox_file.added"

    engagement_id: Annotated[UUID, classified("internal")]
    inbox_file_id: Annotated[UUID, classified("internal")]
    suggestions: Annotated[int, classified("internal")]


class EvidenceUploaded(DomainEvent):
    """A client uploaded a file to a request item: the firm's team is notified (SPEC-020)."""

    event_type: ClassVar[str] = "evidence.uploaded"

    engagement_id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    uploaded_by: Annotated[UUID, classified("internal")]
