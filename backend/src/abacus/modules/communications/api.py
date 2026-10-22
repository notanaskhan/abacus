"""Public interface of the communications module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.communications.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.communications.follow_ups import render_follow_up, send_follow_up
from abacus.modules.communications.invitations import deliver_invitation, deliver_staff_invitation
from abacus.modules.communications.routes import router
from abacus.modules.communications.scope import Violation, check_scope, comment_scope_kinds
from abacus.modules.communications.service import Draft, MessageView, OutOfScope, send
from abacus.modules.communications.transport import LocalMailbox, Transport, configure_transport
from abacus.modules.identity.api import AbacusRouter, ClientInvitationIssued, StaffInvitationIssued
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

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)  # P-01-T05: platform email templates

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
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
    "render_follow_up",
    "send",
    "send_follow_up",
]
