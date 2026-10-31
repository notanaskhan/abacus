"""Domain events published by the agents module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar, Literal
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


class FollowUpLimitReached(DomainEvent):
    """The firm's follow-up policy reached its maximum for a binder's recipient (R-01-T24;
    DEC-74, DEC-564): nothing more goes automatically, so the engagement's leads are told in
    the app (`follow_up_limit_reached`, C16)."""

    event_type: ClassVar[str] = "follow_up.limit_reached"

    engagement_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]  # the recipient person's user id


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


class ProposalRecorded(DomainEvent):
    """An agent recorded a proposal a person decides on (P-04-T16; C13): a screening result, an
    upload review, an inbox match or a guidance draft. The human-gate projector reads the owner's
    records, never this payload, for what waits on whom."""

    event_type: ClassVar[str] = "proposal.recorded"

    engagement_id: Annotated[UUID, classified("internal")]
    source: Annotated[
        Literal["screening_result", "upload_review", "inbox_match", "guidance_draft"],
        classified("internal"),
    ]


class GuidanceDraftDecided(DomainEvent):
    """A person approved or discarded guidance drafts (SPEC-035; P-04-T16 closes their gates)."""

    event_type: ClassVar[str] = "guidance_draft.decided"

    engagement_id: Annotated[UUID, classified("internal")]


# --- Proposals and suggestions (P-04-T24; ADR-161; P-04 §4.5) ----------------------------------


class ProposalCreated(DomainEvent):
    """The agent proposed a change set (through its task scope)."""

    event_type: ClassVar[str] = "proposal.created"

    proposal_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    kind: Annotated[str, classified("internal")]
    agent_run_id: Annotated[UUID, classified("internal")]


class ProposalDecided(DomainEvent):
    """A person approved (with or without edits) or rejected a proposal."""

    event_type: ClassVar[str] = "proposal.decided"

    proposal_id: Annotated[UUID, classified("internal")]
    decision_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    decision: Annotated[str, classified("internal")]
    reason_code: Annotated[str | None, classified("internal")] = None
    by_user: Annotated[UUID, classified("internal")]


class ProposalRouted(DomainEvent):
    """A proposal waits on a named approver (`proposal_routed`): a person sent it (SHL-10 d), or
    the agent's threshold evaluation named them when it proposed (`by_user` is then None)."""

    event_type: ClassVar[str] = "proposal.routed"

    proposal_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    approver_user_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID | None, classified("internal")] = None
    # Who acted, as the transaction's actor kind: the notification reads as a person only when
    # a person did (security review, DEC-609).
    actor_kind: Annotated[Literal["human", "agent"], classified("internal")] = "agent"


class SuggestionCreated(DomainEvent):
    event_type: ClassVar[str] = "suggestion.created"

    suggestion_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]


class SuggestionResolved(DomainEvent):
    """A person adopted (as proposed or edited) or dismissed a suggestion."""

    event_type: ClassVar[str] = "suggestion.resolved"

    suggestion_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    decision: Annotated[str, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class IntakeProposalsRecorded(DomainEvent):
    """N-01-T22 follow-up (DEC-1287): the matcher's intake mode recorded proposals for an
    attachment. Intake proposals wait on INB-02's card, not a human gate (they have no
    engagement), so this, not `proposal.recorded`, is their signal; communications reads the
    proposals, never this payload, to flag a card it cannot call."""

    event_type: ClassVar[str] = "inbox_match.intake_recorded"

    attachment_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    match_id: Annotated[UUID, classified("internal")]
