"""Domain events the review module announces (P-04 §4.5). Identifiers and codes only (ADR-031)."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class SignOffRecorded(DomainEvent):
    """A person signed a target at a level (P-04-T18)."""

    event_type: ClassVar[str] = "sign_off.recorded"

    sign_off_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    level: Annotated[int, classified("internal")]
    signed_by: Annotated[UUID, classified("internal")]


class SignOffWentStale(DomainEvent):
    """A sign-off's target changed after it was signed (P-04-T19): the signer is told. Nothing
    about the sign-off row changes; staleness stays computed (ADR-160 clause 3)."""

    event_type: ClassVar[str] = "sign_off.went_stale"

    sign_off_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    level: Annotated[int, classified("internal")]
    signed_by: Annotated[UUID, classified("internal")]
