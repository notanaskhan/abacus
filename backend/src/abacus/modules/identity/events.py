"""Domain events published by the identity module (ADR-018). Identifiers only."""

from __future__ import annotations

from datetime import date, datetime
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


class ContactInvited(DomainEvent):
    """A client contact was invited with pending grants (P-07-T25; P-07 §4.6; DEC-300):
    identifiers only. The email goes out on `client_invitation.issued`."""

    event_type: ClassVar[str] = "contact.invited"

    contact_id: Annotated[UUID, classified("internal")]
    invitation_id: Annotated[UUID, classified("internal")]
    grant_ids: Annotated[list[UUID], classified("internal")]


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


class MembershipDeactivated(DomainEvent):
    """A staff member was deactivated (G-01-T05; AC4.4): their seat is free and their sessions
    ended; W-01 and caches drop them. Their sign-offs and decisions stay attributed to them."""

    event_type: ClassVar[str] = "membership.deactivated"

    user_id: Annotated[UUID, classified("internal")]


class PortalSignInCodeRequested(DomainEvent):
    """A portal sign-in needs its code emailed: communications issues the code at delivery, so it
    is never stored (P-08-T10; the invitation pattern). Never an email, code or IP."""

    event_type: ClassVar[str] = "portal.sign_in_code_requested"

    challenge_id: Annotated[UUID, classified("internal")]


class WallCreated(DomainEvent):
    """A wall shut a person out of a client (G-01-T09): its consumer ends their assignments
    there (AC8.5), and the named partner is asked to approve it (`wall_approval_requested`)."""

    event_type: ClassVar[str] = "wall.created"

    wall_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    created_by: Annotated[UUID, classified("internal")]
    approver_user_id: Annotated[UUID | None, classified("internal")] = None


class WallApproved(DomainEvent):
    """The named partner approved a wall (AC8.2): its creator is told (`wall_approved`)."""

    event_type: ClassVar[str] = "wall.approved"

    wall_id: Annotated[UUID, classified("internal")]
    created_by: Annotated[UUID, classified("internal")]
    approved_by: Annotated[UUID, classified("internal")]


class ServiceLinePolicyChanged(DomainEvent):
    """A firm changed who reads a service line's content (G-01-T12; DEC-380). Members whose
    reach changed also get `access.changed`."""

    event_type: ClassVar[str] = "service_line_policy.changed"

    service_line: Annotated[str, classified("internal")]
    version: Annotated[int, classified("internal")]


class IndependenceAnnualRecorded(DomainEvent):
    """A person confirmed or declined their annual independence for a year (G-01-T13; DEC-91):
    P-07's team picker and G2 read the new answer."""

    event_type: ClassVar[str] = "independence.annual_recorded"

    user_id: Annotated[UUID, classified("internal")]
    year: Annotated[int, classified("internal")]


class SeasonalAccessEnding(DomainEvent):
    """Seasonal access ends for `members` people of the firm on `access_ends_on`, seven days or
    fewer from now (G-01-T13; AC4.5): firm admins are told once (`seasonal_access_ending`)."""

    event_type: ClassVar[str] = "membership.access_ending"

    access_ends_on: Annotated[date, classified("internal")]
    members: Annotated[int, classified("internal")]


class InvitationExpiring(DomainEvent):
    """A pending client invitation lapses within two days, on day 12 of its 14 (P-07-T47; P-07
    §4.8, DEC-1000): firm admins are told once per invitation and expiry (`invitation_expiring`).
    Identifiers only: never the address or the contact's name."""

    event_type: ClassVar[str] = "invitation.expiring"

    invitation_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    expires_at: Annotated[datetime, classified("internal")]


class WallRemoved(DomainEvent):
    """A partner lifted a wall (AC8.4)."""

    event_type: ClassVar[str] = "wall.removed"

    wall_id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("internal")]


class PortalMfaResetNoticeRequested(DomainEvent):
    """A firm reset a client's second step (P-08-T21, Story 7.2): communications emails the
    person in the firm's name (C16 `portal.mfa_reset_notice`). Identifiers only."""

    event_type: ClassVar[str] = "portal_mfa.reset_notice_requested"

    user_id: Annotated[UUID, classified("internal")]
