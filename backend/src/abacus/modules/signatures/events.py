"""The signatures module's outbox events (N-02 §4.5): identifiers and codes only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class EnvelopeCompleted(DomainEvent):
    """Every signer has signed, or a person imported the signed package (record mode)."""

    event_type: ClassVar[str] = "envelope.completed"

    envelope_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    purpose: Annotated[str, classified("internal")]
    provider: Annotated[str, classified("internal")]
    source_kind: Annotated[str, classified("internal")]
    source_id: Annotated[UUID, classified("internal")]
    imported_by: Annotated[UUID | None, classified("internal")]
    # N-02-T24: who sent it, for SIG-01's `envelope_completed` notification (None: imported).
    sent_by: Annotated[UUID | None, classified("internal")] = None


class EnvelopeSendApproved(DomainEvent):
    """A person pressed Send (N-02-T20): held by the outbox until the Undo window ends and
    delivered only if the send's grant is consumed then (ADR-161); its subscriber starts
    EnvelopeWorkflow. An undone send voids the grant, so this is never delivered."""

    event_type: ClassVar[str] = "envelope.send_approved"

    envelope_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    sent_by: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]


class EnvelopeSuperseded(DomainEvent):
    """C7 v1.1 (N-02-T25): the system marked the envelope superseded (an amount changed after
    signing); every gate consumer treats it as unmet."""

    event_type: ClassVar[str] = "envelope.superseded"

    envelope_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    reason: Annotated[str, classified("internal")]


class EnvelopeSignerSigned(DomainEvent):
    """C7 v1.1 (N-02-T25): one signer signed, as the provider's poll recorded it."""

    event_type: ClassVar[str] = "envelope.signer_signed"

    envelope_id: Annotated[UUID, classified("internal")]
    signer_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    source_kind: Annotated[str, classified("internal")]
    source_id: Annotated[UUID, classified("internal")]


class EnvelopeSignerVerificationFailed(DomainEvent):
    """C7 v1.1 (N-02-T25): one signer's identity check closed their remote path (DF-11)."""

    event_type: ClassVar[str] = "envelope.signer_verification_failed"

    envelope_id: Annotated[UUID, classified("internal")]
    signer_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    source_kind: Annotated[str, classified("internal")]
    source_id: Annotated[UUID, classified("internal")]
    # N-02-T27 (additive): the person who sent it, whom C16 tells (DF-11).
    sent_by: Annotated[UUID | None, classified("internal")] = None


class EnvelopeDeclined(DomainEvent):
    """N-02-T24: a signer declined (at the provider or in the portal); the sender is told."""

    event_type: ClassVar[str] = "envelope.declined"

    envelope_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    sent_by: Annotated[UUID | None, classified("internal")]


class EnvelopeExpired(DomainEvent):
    """N-02-T24: an open envelope passed its expiry; the sender is told."""

    event_type: ClassVar[str] = "envelope.expired"

    envelope_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    sent_by: Annotated[UUID | None, classified("internal")]
