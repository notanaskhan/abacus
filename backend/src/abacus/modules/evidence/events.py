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


class UploadChecksRecorded(DomainEvent):
    """SPEC-029's checks are recorded for an evidence version on a request item (SPEC-030;
    TASK-059): the engagement agent's P-6 may start the upload reviewer."""

    event_type: ClassVar[str] = "upload_checks.recorded"

    engagement_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]


class InboxFileExtracted(DomainEvent):
    """An inbox file's contents were read (SPEC-033; TASK-066): the engagement agent's P-7 may
    start the matcher."""

    event_type: ClassVar[str] = "inbox_file.extracted"

    engagement_id: Annotated[UUID, classified("internal")]
    inbox_file_id: Annotated[UUID, classified("internal")]


class LegalHoldPlaced(DomainEvent):
    """A person placed a legal hold (Q-02-T29): `LegalHoldApply` starts, and the notify list and
    the partners of the engagements in scope are told (`legal_hold_placed`, C16)."""

    event_type: ClassVar[str] = "legal_hold.placed"

    hold_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")] = None
    work_item_id: Annotated[UUID | None, classified("internal")] = None
    engagement_ids: Annotated[tuple[UUID, ...], classified("internal")] = ()
    notify_user_ids: Annotated[tuple[UUID, ...], classified("internal")] = ()
    by_user: Annotated[UUID, classified("internal")]


class LegalHoldLifted(DomainEvent):
    """A person lifted an active legal hold (Q-02-T29): `LegalHoldRelease` starts."""

    event_type: ClassVar[str] = "legal_hold.lifted"

    hold_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class EvidenceVersionWithdrawn(DomainEvent):
    """A client withdrew an unaccepted upload (ADR-162 §4; P-06-T19): its purge starts. No file
    name, ever."""

    event_type: ClassVar[str] = "evidence_version.withdrawn"

    engagement_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID | None, classified("internal")] = None


class EvidenceWithdrawalErased(DomainEvent):
    """A withdrawn version's key was destroyed after its window (ADR-162 §7)."""

    event_type: ClassVar[str] = "evidence_withdrawal.erased"

    engagement_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]


class ReviewDecisionRecorded(DomainEvent):
    """A person accepted, rejected or sent back a version, or undid that (P-04-T16: the gates on
    the version's proposals close or open again)."""

    event_type: ClassVar[str] = "review_decision.recorded"

    engagement_id: Annotated[UUID, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]


class InboxFileSorted(DomainEvent):
    """A person assigned an inbox file to a request item or discarded it (P-04-T16: its match
    proposals no longer wait on anyone)."""

    event_type: ClassVar[str] = "inbox_file.sorted"

    engagement_id: Annotated[UUID, classified("internal")]
    inbox_file_id: Annotated[UUID, classified("internal")]


class CitationMoved(DomainEvent):
    """A citation's source was superseded (P-03-T12; AC6.1): P-04's staleness rules read it."""

    event_type: ClassVar[str] = "citation.moved"

    citation_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    cause_ref: Annotated[str, classified("internal")]  # `evidence_version:<successor>`


class CitationBroken(DomainEvent):
    """A citation's source was voided, withdrawn or erased (P-03-T12; AC6.1)."""

    event_type: ClassVar[str] = "citation.broken"

    citation_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    cause_ref: Annotated[str, classified("internal")]  # `withdrawn:<version>`
