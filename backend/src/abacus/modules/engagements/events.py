"""Domain events published by the engagements module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class EngagementCreated(DomainEvent):
    event_type: ClassVar[str] = "engagement.created"

    engagement_id: Annotated[UUID, classified("internal")]


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
