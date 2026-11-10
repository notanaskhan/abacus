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


class MethodologyVersionApproved(DomainEvent):
    """A quality partner approved a version (K-01-T06): it is Published from `effective_from`, and
    nothing waits on its approval any more (I-01-T23: its Home gate closes; DEC-2613)."""

    event_type: ClassVar[str] = "methodology_version.approved"

    version_id: Annotated[UUID, classified("internal")]
    template_id: Annotated[UUID, classified("internal")]
    approved_by: Annotated[UUID, classified("internal")]


class MethodologyVersionDiscarded(DomainEvent):
    """A version in Needs review was discarded (K-01 AC5.7): nothing waits on its approval any
    more (I-01-T23: its Home gate closes; DEC-2613). A draft's discard emits nothing."""

    event_type: ClassVar[str] = "methodology_version.discarded"

    version_id: Annotated[UUID, classified("internal")]
    template_id: Annotated[UUID, classified("internal")]


class FirmStandardPublished(DomainEvent):
    """A firm standard's version was published (K-02-T08): KNW-01's change log and consumers that
    cache the version in effect re-read it."""

    event_type: ClassVar[str] = "firm_standard.published"

    standard_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class ThresholdPolicyPublished(DomainEvent):
    """A threshold policy's version was published (K-02-T08; consumers C-01, A-04, A-06)."""

    event_type: ClassVar[str] = "threshold_policy.published"

    standard_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]
