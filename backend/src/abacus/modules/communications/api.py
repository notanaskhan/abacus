"""Public interface of the communications module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.communications.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.communications.deliveries import (
    SesEventQueue,
    configure_ses_event_queue,
    drain_ses_events,
    drain_ses_events_activity,
    is_suppressed,
    send_email,
)
from abacus.modules.communications.events import MessageBounced, MessageComplained
from abacus.modules.communications.fake_ses import FakeSesEventQueue, FakeSesTransport
from abacus.modules.communications.follow_ups import render_follow_up, send_follow_up
from abacus.modules.communications.invitations import deliver_invitation, deliver_staff_invitation
from abacus.modules.communications.notification_email import (
    NotificationMail,
    send_notification_email,
    template_key,
)
from abacus.modules.communications.routes import router
from abacus.modules.communications.scope import Violation, check_scope, comment_scope_kinds
from abacus.modules.communications.service import Draft, MessageView, OutOfScope, send
from abacus.modules.communications.ses_identities import (
    DnsRecord,
    IdentitySetup,
    IdentityStatus,
    InMemorySesIdentities,
    SesIdentities,
    SesIdentityInvalid,
    SesIdentityNotFound,
    SesIdentityPort,
    SesIdentityUnavailable,
    configure_ses_identities,
    ses_identities,
)
from abacus.modules.communications.sign_in_codes import deliver_sign_in_code
from abacus.modules.communications.sink import (
    LOCAL_SINK_DOMAIN,
    on_sink,
    sink_address,
    sink_domain,
)
from abacus.modules.communications.transport import LocalMailbox, Transport, configure_transport
from abacus.modules.communications.workflows import DrainSesEventsWorkflow
from abacus.modules.identity.api import (
    AbacusRouter,
    ClientInvitationIssued,
    PortalSignInCodeRequested,
    StaffInvitationIssued,
)
from abacus.modules.requests.api import register_comment_scope_check

# SPEC-015: invitation emails are sent when the relay delivers `client_invitation.issued`.
SUBSCRIPTIONS = {
    ClientInvitationIssued.event_type: deliver_invitation,
    StaffInvitationIssued.event_type: deliver_staff_invitation,  # SPEC-024 (TASK-041)
    PortalSignInCodeRequested.event_type: deliver_sign_in_code,  # P-08-T10
}
# SPEC-032 (TASK-062 D1): a firm comment is checked before it's shared with the client.
register_comment_scope_check(comment_scope_kinds)
# Q-01-T46: the every-minute drain of SES delivery events.
WORKFLOWS: dict[type, str] = {DrainSesEventsWorkflow: "time_sensitive"}
ACTIVITIES: tuple[object, ...] = (drain_ses_events_activity,)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)  # P-01-T05: platform email templates

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "LOCAL_SINK_DOMAIN",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "DnsRecord",
    "Draft",
    "DrainSesEventsWorkflow",
    "FakeSesEventQueue",
    "FakeSesTransport",
    "IdentitySetup",
    "IdentityStatus",
    "InMemorySesIdentities",
    "LocalMailbox",
    "MessageBounced",
    "MessageComplained",
    "MessageView",
    "NotificationMail",
    "OutOfScope",
    "SesEventQueue",
    "SesIdentities",
    "SesIdentityInvalid",
    "SesIdentityNotFound",
    "SesIdentityPort",
    "SesIdentityUnavailable",
    "Transport",
    "Violation",
    "check_scope",
    "configure_ses_event_queue",
    "configure_ses_identities",
    "configure_transport",
    "drain_ses_events",
    "is_suppressed",
    "on_sink",
    "render_follow_up",
    "send",
    "send_email",
    "send_follow_up",
    "send_notification_email",
    "ses_identities",
    "sink_address",
    "sink_domain",
    "template_key",
]
