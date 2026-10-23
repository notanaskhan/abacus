"""Domain events published by the identity module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class FirmAgentsResumed(DomainEvent):
    """A firm administrator resumed every engagement agent in the firm (SPEC-027; TASK-050): the
    agents look at their engagements' state once."""

    event_type: ClassVar[str] = "firm.agents_resumed"


class SupportSessionRequested(DomainEvent):
    """A staff member asked for break-glass access to this firm (SPEC-012, SPEC-013)."""

    event_type: ClassVar[str] = "support_session.requested"

    session_id: Annotated[UUID, classified("internal")]


class SupportSessionEmergencyApproved(DomainEvent):
    """A second staff member approved an emergency session: the firm must know now."""

    event_type: ClassVar[str] = "support_session.emergency_approved"

    session_id: Annotated[UUID, classified("internal")]


class EngagementMemberSelfJoined(DomainEvent):
    """A firm admin joined an engagement to see its content (ADR-024: the team is notified)."""

    event_type: ClassVar[str] = "engagement.member_self_joined"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class ClientInvitationIssued(DomainEvent):
    """An invitation needs its email (created or resent): communications issues the token at
    delivery, so it is never stored (SPEC-015; TASK-030 D1)."""

    event_type: ClassVar[str] = "client_invitation.issued"

    invitation_id: Annotated[UUID, classified("internal")]


class EngagementMemberAdded(DomainEvent):
    """Someone was added to an engagement's team: they are notified (SPEC-017 Q4)."""

    event_type: ClassVar[str] = "engagement_member.added"

    engagement_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class StaffInvitationIssued(DomainEvent):
    """A staff invitation needs its email (created or resent); the token is issued at delivery
    and never stored (SPEC-024; TASK-041)."""

    event_type: ClassVar[str] = "staff_invitation.issued"

    invitation_id: Annotated[UUID, classified("internal")]


class ClientAccessGranted(DomainEvent):
    """A client access grant became active (F-03-T26; ADR-146)."""

    event_type: ClassVar[str] = "client_access.granted"

    grant_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class ClientAccessRevoked(DomainEvent):
    """A client access grant was revoked (F-03-T26)."""

    event_type: ClassVar[str] = "client_access.revoked"

    grant_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class AccessChanged(DomainEvent):
    """A person's access changed (a grant here; memberships, walls and roles later): consumers
    that hold sessions or caches for them drop them (P-01, P-10)."""

    event_type: ClassVar[str] = "access.changed"

    user_id: Annotated[UUID, classified("internal")]


class PortalSignInCodeRequested(DomainEvent):
    """A portal sign-in needs its code emailed: communications issues the code at delivery, so it
    is never stored (P-08-T10; the invitation pattern). Never an email, code or IP."""

    event_type: ClassVar[str] = "portal.sign_in_code_requested"

    challenge_id: Annotated[UUID, classified("internal")]
