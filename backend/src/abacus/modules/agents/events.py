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


class RemindersDrafted(DomainEvent):
    """At Advise, the engagement agent drafted overdue reminders for a person to send or dismiss
    (SPEC-027 P-4; TASK-051): the partner and managers are notified."""

    event_type: ClassVar[str] = "reminders.drafted"

    engagement_id: Annotated[UUID, classified("internal")]
    count: Annotated[int, classified("internal")]


class AgentDigest(DomainEvent):
    """The engagement agent's daily digest for the team (SPEC-027 P-5): items overdue, reminders
    sent and drafted. Delivered in the app only."""

    event_type: ClassVar[str] = "agent.digest"

    engagement_id: Annotated[UUID, classified("internal")]
    overdue: Annotated[int, classified("internal")]
    sent: Annotated[int, classified("internal")]
    drafted: Annotated[int, classified("internal")]
