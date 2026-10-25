"""Domain events published by the agents module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class KnowledgeDocumentAdded(DomainEvent):
    """A knowledge document's chunks await embedding (SPEC-009)."""

    event_type: ClassVar[str] = "knowledge_document.added"

    document_id: Annotated[UUID, classified("internal")]


class FollowUpsDrafted(DomainEvent):
    """The engagement agent drafted follow-ups on overdue requests for a person to send or
    dismiss (SPEC-027 P-4; DEC-74): the partner and managers are notified in the app
    (`follow_up_drafted`, C16; P-06-T14 renamed the event from the dotted `reminders.drafted`)."""

    event_type: ClassVar[str] = "follow_up.drafted"

    engagement_id: Annotated[UUID, classified("internal")]
    count: Annotated[int, classified("internal")]


class FollowUpSent(DomainEvent):
    """A person sent a follow-up (P-06-T14). Held by an approval grant until the 10-s Undo
    window ends (ADR-161); its delivery sends the email (communications)."""

    event_type: ClassVar[str] = "follow_up.sent"

    follow_up_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    sent_by: Annotated[UUID, classified("internal")]


class AgentDigest(DomainEvent):
    """The engagement agent's daily digest for the team (SPEC-027 P-5): items overdue, reminders
    sent and drafted. Delivered in the app only."""

    event_type: ClassVar[str] = "agent.digest"

    engagement_id: Annotated[UUID, classified("internal")]
    overdue: Annotated[int, classified("internal")]
    sent: Annotated[int, classified("internal")]
    drafted: Annotated[int, classified("internal")]


class UploadReviewRecorded(DomainEvent):
    """The upload reviewer recorded its review of a version (SPEC-030; P-06-T20): the request
    batches it fulfils recompose their screening (code only, nothing else follows)."""

    event_type: ClassVar[str] = "upload_review.recorded"

    engagement_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
