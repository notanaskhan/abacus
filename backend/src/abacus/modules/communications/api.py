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
from abacus.modules.communications.events import (
    MessageBounced,
    MessageComplained,
    PortalLinkRenewRequested,
)
from abacus.modules.communications.fake_ses import FakeSesEventQueue, FakeSesTransport
from abacus.modules.communications.follow_ups import (
    REMINDER_TEMPLATE,
    RETURN_TEMPLATE,
    ComposedFollowUp,
    FollowUpTemplateMissing,
    compose_follow_up,
    deliver_follow_up,
)
from abacus.modules.communications.invitations import deliver_invitation, deliver_staff_invitation
from abacus.modules.communications.notification_email import (
    NotificationMail,
    send_notification_email,
    template_key,
)
from abacus.modules.communications.routes import router
from abacus.modules.communications.scope import Violation, check_scope, comment_scope_kinds
from abacus.modules.communications.secure_link_routes import router as secure_link_router
from abacus.modules.communications.secure_links import (
    IssuedLink,
    SecureLinkView,
    claim,
    deliver_renewed_link,
    issue_secure_link,
    resolve_secure_link,
    revoke_links_of,
    revoke_links_on_access_revoked,
)
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
from abacus.modules.communications.sign_in_codes import (
    deliver_mfa_reset_notice,
    deliver_sign_in_code,
)
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
    ClientAccessRevoked,
    ClientInvitationIssued,
    PortalMfaResetNoticeRequested,
    PortalSignInCodeRequested,
    StaffInvitationIssued,
    register_contact_links_revoker,
    register_link_claim,
)
from abacus.modules.requests.api import register_comment_scope_check

# SPEC-015: invitation emails are sent when the relay delivers `client_invitation.issued`.
SUBSCRIPTIONS = {
    ClientInvitationIssued.event_type: deliver_invitation,
    StaffInvitationIssued.event_type: deliver_staff_invitation,  # SPEC-024 (TASK-041)
    PortalSignInCodeRequested.event_type: deliver_sign_in_code,  # P-08-T10
    PortalLinkRenewRequested.event_type: deliver_renewed_link,  # P-08-T21
    PortalMfaResetNoticeRequested.event_type: deliver_mfa_reset_notice,  # P-08-T21
    ClientAccessRevoked.event_type: revoke_links_on_access_revoked,  # P-08-T21: links die too
}
# P-08-T21: identity's sign-in start uses a portal email's link through this.
register_link_claim(claim)
# P-08-T21: organisations revokes a contact's links where their access or address changes.
register_contact_links_revoker(revoke_links_of)
# SPEC-032 (TASK-062 D1): a firm comment is checked before it's shared with the client.
register_comment_scope_check(comment_scope_kinds)
# Q-01-T46: the every-minute drain of SES delivery events.
WORKFLOWS: dict[type, str] = {DrainSesEventsWorkflow: "time_sensitive"}
ACTIVITIES: tuple[object, ...] = (drain_ses_events_activity,)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,  # P-01-T05: platform email templates
    secure_link_router,  # P-08-T21: a recipient's link renewal (pre-session)
)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "LOCAL_SINK_DOMAIN",
    "REMINDER_TEMPLATE",
    "RETURN_TEMPLATE",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "ComposedFollowUp",
    "DnsRecord",
    "Draft",
    "DrainSesEventsWorkflow",
    "FakeSesEventQueue",
    "FakeSesTransport",
    "FollowUpTemplateMissing",
    "IdentitySetup",
    "IdentityStatus",
    "InMemorySesIdentities",
    "IssuedLink",
    "LocalMailbox",
    "MessageBounced",
    "MessageComplained",
    "MessageView",
    "NotificationMail",
    "OutOfScope",
    "SecureLinkView",
    "SesEventQueue",
    "SesIdentities",
    "SesIdentityInvalid",
    "SesIdentityNotFound",
    "SesIdentityPort",
    "SesIdentityUnavailable",
    "Transport",
    "Violation",
    "check_scope",
    "compose_follow_up",
    "configure_ses_event_queue",
    "configure_ses_identities",
    "configure_transport",
    "deliver_follow_up",
    "drain_ses_events",
    "is_suppressed",
    "issue_secure_link",
    "on_sink",
    "resolve_secure_link",
    "send",
    "send_email",
    "send_notification_email",
    "ses_identities",
    "sink_address",
    "sink_domain",
    "template_key",
]
