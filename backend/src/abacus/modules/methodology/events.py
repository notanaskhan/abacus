"""Domain events the methodology module announces (K-01-T06; ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class MethodologyReviewRequested(DomainEvent):
    """A version was submitted for review: the firm's quality partners are told."""

    event_type: ClassVar[str] = "methodology.review_requested"

    version_id: Annotated[UUID, classified("internal")]
    template_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class MethodologyVersionSuperseded(DomainEvent):
    """A published version gave way to a newer approved one (its `effective_to` is set)."""

    event_type: ClassVar[str] = "methodology_version.superseded"

    version_id: Annotated[UUID, classified("internal")]
    template_id: Annotated[UUID, classified("internal")]
    by_version_id: Annotated[UUID, classified("internal")]
