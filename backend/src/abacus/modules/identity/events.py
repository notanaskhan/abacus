"""Domain events published by the identity module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


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
