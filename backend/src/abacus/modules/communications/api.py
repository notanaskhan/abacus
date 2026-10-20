"""Public interface of the communications module; other modules import only this (ADR-008)."""

from abacus.modules.communications.invitations import deliver_invitation, deliver_staff_invitation
from abacus.modules.communications.reminders import render_reminder, send_reminder
from abacus.modules.communications.scope import Violation, check_scope, comment_scope_kinds
from abacus.modules.communications.service import Draft, MessageView, OutOfScope, send
from abacus.modules.communications.transport import LocalMailbox, Transport, configure_transport
from abacus.modules.identity.api import ClientInvitationIssued, StaffInvitationIssued
from abacus.modules.requests.api import register_comment_scope_check

# SPEC-015: invitation emails are sent when the relay delivers `client_invitation.issued`.
SUBSCRIPTIONS = {
    ClientInvitationIssued.event_type: deliver_invitation,
    StaffInvitationIssued.event_type: deliver_staff_invitation,  # SPEC-024 (TASK-041)
}
# SPEC-032 (TASK-062 D1): a firm comment is checked before it's shared with the client.
register_comment_scope_check(comment_scope_kinds)
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
    "render_reminder",
    "send",
    "send_reminder",
]
