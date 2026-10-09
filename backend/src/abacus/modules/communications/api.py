"""Public interface of the communications module; other modules import only this (ADR-008)."""

from abacus.modules.communications.invitations import deliver_invitation, deliver_staff_invitation
from abacus.modules.communications.scope import Violation, check_scope
from abacus.modules.communications.service import Draft, MessageView, OutOfScope, send
from abacus.modules.communications.transport import LocalMailbox, Transport, configure_transport
from abacus.modules.identity.api import ClientInvitationIssued, StaffInvitationIssued

# SPEC-015: invitation emails are sent when the relay delivers `client_invitation.issued`.
SUBSCRIPTIONS = {
    ClientInvitationIssued.event_type: deliver_invitation,
    StaffInvitationIssued.event_type: deliver_staff_invitation,  # SPEC-024 (TASK-041)
}
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

__all__ = [
    "ACTIVITIES",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "Draft",
    "LocalMailbox",
    "MessageView",
    "OutOfScope",
    "Transport",
    "Violation",
    "check_scope",
    "configure_transport",
    "send",
]
