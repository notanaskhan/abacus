"""Public interface of the communications module; other modules import only this (ADR-008)."""

from datetime import timedelta

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.kernel.dispatch import PlatformSchedule, WorkClass, register_work_classes
from abacus.modules.communications import portal_intake
from abacus.modules.communications.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.communications.deliveries import (
    SesEventQueue,
    configure_ses_event_queue,
    delivery_status,
    drain_ses_events,
    drain_ses_events_activity,
    is_suppressed,
    send_email,
)
from abacus.modules.communications.events import (
    InboxAttachmentReceived,
    MessageBounced,
    MessageComplained,
    MessageDeliveryStatusChanged,
    PortalIntakeWithdrawn,
    PortalLinkRenewRequested,
    SendingDomainFailed,
    SendingDomainStatusChanged,
    SendingDomainVerified,
)
from abacus.modules.communications.fake_ses import FakeSesEventQueue, FakeSesTransport
from abacus.modules.communications.follow_up_policy import (
    FollowUpPolicy,
    NextSend,
    ReminderHistory,
    Sent,
    first_tick_on_or_after,
    follow_up_policy,
    limit_reached_today,
    next_send_at,
    next_send_on,
    next_sequence_by_policy,
    register_reminder_history,
    save_follow_up_policy,
    write_follow_up_policy,
)
from abacus.modules.communications.follow_ups import (
    REMINDER_TEMPLATE,
    RETURN_TEMPLATE,
    ComposedFollowUp,
    FollowUpTemplateMissing,
    compose_follow_up,
    deliver_follow_up,
)
from abacus.modules.communications.inbox_read import inbox_waiting, waiting_for_work_item
from abacus.modules.communications.intake import (
    Inbound,
    Recorded,
    add_attachment,
    record_inbound_message,
)
from abacus.modules.communications.intake_contract import destinations_router, intake_router
from abacus.modules.communications.invitations import deliver_invitation, deliver_staff_invitation
from abacus.modules.communications.notification_email import (
    NotificationMail,
    send_notification_email,
    template_key,
)
from abacus.modules.communications.notification_email import (
    display_name as engagement_display_name,
)
from abacus.modules.communications.portal_intake import ACTIVITIES as PORTAL_INTAKE_ACTIVITIES
from abacus.modules.communications.portal_intake import WORKFLOWS as PORTAL_INTAKE_WORKFLOWS
from abacus.modules.communications.portal_intake import on_withdrawn
from abacus.modules.communications.preview_scope import PreviewSelection, viewer_scoped
from abacus.modules.communications.render import Block as TemplateBlockContent
from abacus.modules.communications.render import TemplateContent
from abacus.modules.communications.routes import router
from abacus.modules.communications.scheduled_reminders import (
    ScheduledReminder,
    send_scheduled_reminder,
)
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
from abacus.modules.communications.sending_domains import (
    check_sending_domain_activity,
    client_mail_open,
    on_status_changed,
    sender_for,
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
from abacus.modules.communications.template_import import BundleEntry as EmailTemplateBundleEntry
from abacus.modules.communications.template_import import import_bundle as import_email_templates
from abacus.modules.communications.template_registry import (
    VARIABLES as TEMPLATE_VARIABLES,
)
from abacus.modules.communications.template_registry import (
    EmailTemplateRegistration,
    RecipientRef,
    SendOutcome,
    SendRefusal,
    SendScope,
    TemplateRegistrationInvalid,
    TemplateVariable,
    ValueFinding,
    lint_values,
    register_email_template,
    registered_templates,
    scheduled_send_enabled,
    send_templated,
    templated_outcome,
)
from abacus.modules.communications.template_service import (
    discard_draft as discard_email_template_draft,
)
from abacus.modules.communications.template_service import publish as publish_email_template
from abacus.modules.communications.template_service import save_draft as save_email_template_draft
from abacus.modules.communications.template_service import template_state as email_template_state
from abacus.modules.communications.templates_contract import (
    FollowUpPolicyFields,
    NextSendOut,
    domains_router,
    policy_router,
    templates_router,
)
from abacus.modules.communications.transport import LocalMailbox, Transport, configure_transport
from abacus.modules.communications.triage import ACTIVITIES as TRIAGE_ACTIVITIES
from abacus.modules.communications.triage import WORKFLOWS as TRIAGE_WORKFLOWS
from abacus.modules.communications.triage import on_attachment_received
from abacus.modules.communications.triage_apply import (
    IntakeDestination,
    Placement,
    register_intake_destination,
)
from abacus.modules.communications.triage_workflow import (
    AttachmentTriageWorkflow,
    TriageInput,
    attachment_triage_id,
)
from abacus.modules.communications.workflows import (
    DrainSesEventsWorkflow,
    SendingDomainVerificationInput,
    SendingDomainVerificationWorkflow,
)
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
from abacus.modules.platform.api import register_home_count
from abacus.modules.requests.api import register_comment_scope_check

# SPEC-015: invitation emails are sent when the relay delivers `client_invitation.issued`.
SUBSCRIPTIONS = {
    ClientInvitationIssued.event_type: deliver_invitation,
    StaffInvitationIssued.event_type: deliver_staff_invitation,  # SPEC-024 (TASK-041)
    PortalSignInCodeRequested.event_type: deliver_sign_in_code,  # P-08-T10
    PortalLinkRenewRequested.event_type: deliver_renewed_link,  # P-08-T21
    PortalMfaResetNoticeRequested.event_type: deliver_mfa_reset_notice,  # P-08-T21
    ClientAccessRevoked.event_type: revoke_links_on_access_revoked,  # P-08-T21: links die too
    # R-01-T27: a new domain's verification starts once its row is committed.
    SendingDomainStatusChanged.event_type: on_status_changed,
    # N-01-T12: a received intake attachment goes through the upload steps (AttachmentTriage).
    InboxAttachmentReceived.event_type: on_attachment_received,
    PortalIntakeWithdrawn.event_type: on_withdrawn,  # N-01-T14: the upload's 30-day purge
}
# N-01-T13: HOME-01's `inbox_waiting` pill counts the Inbox summary's waiting attachments.
register_home_count("inbox_waiting", inbox_waiting)
# P-08-T21: identity's sign-in start uses a portal email's link through this.
register_link_claim(claim)
# P-08-T21: organisations revokes a contact's links where their access or address changes.
register_contact_links_revoker(revoke_links_of)
# SPEC-032 (TASK-062 D1): a firm comment is checked before it's shared with the client.
register_comment_scope_check(comment_scope_kinds)
# Q-01-T46: the every-minute drain of SES delivery events, on its Schedule `ses_events:platform`
# (Q-01-T26; `abacus_tools.schedules ensure`). Without `ses_events_queue_url` a run drains nothing.
SES_EVENTS_ID = "ses_events:platform"
WORKFLOWS: dict[type, WorkClass] = {
    DrainSesEventsWorkflow: "time_sensitive",
    SendingDomainVerificationWorkflow: "background",  # R-01-T27: every 15 minutes, 72 hours
    **TRIAGE_WORKFLOWS,
    **PORTAL_INTAKE_WORKFLOWS,
}
register_work_classes(WORKFLOWS)
ACTIVITIES: tuple[object, ...] = (
    drain_ses_events_activity,
    check_sending_domain_activity,
    *TRIAGE_ACTIVITIES,
    *PORTAL_INTAKE_ACTIVITIES,
)
SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=SES_EVENTS_ID,
        workflow=DrainSesEventsWorkflow,
        every=timedelta(minutes=1),
        note="Q-01-T46: the SES delivery-event drain, every minute (Q-01-T26)",
    ),
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,  # P-01-T05: platform email templates
    secure_link_router,  # P-08-T21: a recipient's link renewal (pre-session)
    templates_router,  # C16 v1.1 stub (R-01-T16): firm email templates
    domains_router,  # C16 v1.1 stub (R-01-T16): sending domains
    policy_router,  # C16 v1.1 stub (R-01-T16): the follow-up policy
    intake_router,  # C5 v1.2 intake half stub (N-01-T02): firm intake
    destinations_router,  # C5 v1.2 intake half stub (N-01-T02): the File-to picker
)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "LOCAL_SINK_DOMAIN",
    "REMINDER_TEMPLATE",
    "RETURN_TEMPLATE",
    "ROUTERS",
    "SCHEDULES",
    "SES_EVENTS_ID",
    "SUBSCRIPTIONS",
    "TEMPLATE_VARIABLES",
    "WORKFLOWS",
    "AttachmentTriageWorkflow",
    "ComposedFollowUp",
    "DnsRecord",
    "Draft",
    "DrainSesEventsWorkflow",
    "EmailTemplateBundleEntry",
    "EmailTemplateRegistration",
    "FakeSesEventQueue",
    "FakeSesTransport",
    "FollowUpPolicy",
    "FollowUpPolicyFields",
    "FollowUpTemplateMissing",
    "IdentitySetup",
    "IdentityStatus",
    "InMemorySesIdentities",
    "Inbound",
    "IntakeDestination",
    "IssuedLink",
    "LocalMailbox",
    "MessageBounced",
    "MessageComplained",
    "MessageDeliveryStatusChanged",
    "MessageView",
    "NextSend",
    "NextSendOut",
    "NotificationMail",
    "OutOfScope",
    "Placement",
    "PreviewSelection",
    "RecipientRef",
    "Recorded",
    "ReminderHistory",
    "ScheduledReminder",
    "SecureLinkView",
    "SendOutcome",
    "SendRefusal",
    "SendScope",
    "SendingDomainFailed",
    "SendingDomainStatusChanged",
    "SendingDomainVerificationInput",
    "SendingDomainVerificationWorkflow",
    "SendingDomainVerified",
    "Sent",
    "SesEventQueue",
    "SesIdentities",
    "SesIdentityInvalid",
    "SesIdentityNotFound",
    "SesIdentityPort",
    "SesIdentityUnavailable",
    "TemplateBlockContent",
    "TemplateContent",
    "TemplateRegistrationInvalid",
    "TemplateVariable",
    "Transport",
    "TriageInput",
    "ValueFinding",
    "Violation",
    "add_attachment",
    "attachment_triage_id",
    "check_scope",
    "client_mail_open",
    "compose_follow_up",
    "configure_ses_event_queue",
    "configure_ses_identities",
    "configure_transport",
    "deliver_follow_up",
    "delivery_status",
    "discard_email_template_draft",
    "drain_ses_events",
    "email_template_state",
    "engagement_display_name",
    "first_tick_on_or_after",
    "follow_up_policy",
    "import_email_templates",
    "is_suppressed",
    "issue_secure_link",
    "limit_reached_today",
    "lint_values",
    "next_send_at",
    "next_send_on",
    "next_sequence_by_policy",
    "on_sink",
    "portal_intake",
    "publish_email_template",
    "record_inbound_message",
    "register_email_template",
    "register_intake_destination",
    "register_reminder_history",
    "registered_templates",
    "resolve_secure_link",
    "save_email_template_draft",
    "save_follow_up_policy",
    "scheduled_send_enabled",
    "send",
    "send_email",
    "send_notification_email",
    "send_scheduled_reminder",
    "send_templated",
    "sender_for",
    "ses_identities",
    "sink_address",
    "sink_domain",
    "template_key",
    "templated_outcome",
    "viewer_scoped",
    "waiting_for_work_item",
    "write_follow_up_policy",
]
