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
