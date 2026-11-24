"""Domain events published by the engagements module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class EngagementCreated(DomainEvent):
    event_type: ClassVar[str] = "engagement.created"

    engagement_id: Annotated[UUID, classified("internal")]
    # T-08-T19 (additive): the record the engagement was opened from, when ENG-03 was prefilled
    # by one (`planning_opportunity:<uuid>`: TAX-15 c's opportunity becomes Accepted).
    source_ref: Annotated[str | None, classified("internal")] = None


class IndependenceRequested(DomainEvent):
    """Someone joined an engagement's team and must confirm their independence (SPEC-025)."""

    event_type: ClassVar[str] = "independence.requested"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


# --- P-07-T47 (P-07 §4.8; C16): what a person is told. Identifiers only. -----------------------


class IndependenceReminded(DomainEvent):
    """A person sent a member the firm's reminder to confirm their independence (by a click)."""

    event_type: ClassVar[str] = "independence.reminded"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class IndependenceConclusionDue(DomainEvent):
    """Every member confirmed and nobody has concluded: the engagement partner concludes."""

    event_type: ClassVar[str] = "independence.conclusion_due"

    engagement_id: Annotated[UUID, classified("internal")]


class AcceptanceReviewRequested(DomainEvent):
    """The engagement partner asked another partner for a risk review of the acceptance."""

    event_type: ClassVar[str] = "acceptance.review_requested"

    engagement_id: Annotated[UUID, classified("internal")]
    record_id: Annotated[UUID, classified("internal")]
    partner_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class TeamChangeProposed(DomainEvent):
    """The team changed (a member added or their role changed): it waits for the engagement
    partner's approval (ENG-05)."""

    event_type: ClassVar[str] = "team.change_proposed"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]
    by_user: Annotated[UUID, classified("internal")]


class EqrEligibilityApproved(DomainEvent):
    """The quality owner recorded an EQR candidate's eligibility (eligible or not)."""

    event_type: ClassVar[str] = "eqr.eligibility_approved"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


# --- P-07-T52: CLI-06's bulk import. Identifiers and counts only. ------------------------------


class ClientImportCompleted(DomainEvent):
    """A bulk client import's run finished: every row applied, skipped or failed."""

    event_type: ClassVar[str] = "client_import.completed"

    import_id: Annotated[UUID, classified("internal")]


class TemplateUpdateAvailable(DomainEvent):
    """K-03-T12 (DEC-5904; K-03 §4.8): a rollout set an engagement to Update now, so its link reads
    update_available; the manager the rollout row names is told (`template_update_available`,
    C16; deep link to SHL-22). Emitted by K-03-T32's rollout start, one per engagement."""

    event_type: ClassVar[str] = "template_update.available"

    engagement_id: Annotated[UUID, classified("internal")]
    rollout_id: Annotated[UUID, classified("internal")]
    to_version_id: Annotated[UUID, classified("internal")]
    recipient_user_ids: Annotated[list[UUID], classified("internal")]
    by_user: Annotated[UUID, classified("internal")]
