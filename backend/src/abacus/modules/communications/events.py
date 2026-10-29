"""Domain events published by the communications module (ADR-018). Identifiers only."""

from __future__ import annotations

from typing import Annotated, ClassVar
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.uow import DomainEvent


class MessageReady(DomainEvent):
    """A checked message for delivery (a transport consumes it, increments 2 and 8)."""

    event_type: ClassVar[str] = "message.ready"
    message_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]


class MessageBounced(DomainEvent):
    """SES reported a bounce for this send (Q-01-T46). A permanent one suppressed the address."""

    event_type: ClassVar[str] = "message.bounced"
    message_id: Annotated[UUID, classified("internal")]


class MessageComplained(DomainEvent):
    """The recipient marked this send as spam (Q-01-T46); the address is suppressed."""

    event_type: ClassVar[str] = "message.complained"
    message_id: Annotated[UUID, classified("internal")]


class PortalLinkRenewRequested(DomainEvent):
    """A recipient renewed a portal email's link (P-08-T21; SPEC-320 AC-14): the new link's token
    is issued at delivery and sent to the address the old one went to. Identifiers only."""

    event_type: ClassVar[str] = "portal.link_renew_requested"
    secure_link_id: Annotated[UUID, classified("internal")]


class EmailTemplatePublished(DomainEvent):
    """A firm published a new version of a template key (R-01-T19; C16 v1.1 §7). Later sends of
    the key use it; messages already sent keep their `template_version_id`."""

    event_type: ClassVar[str] = "email_template.published"
    key: Annotated[str, classified("internal")]
    version: Annotated[int, classified("internal")]


class SendingDomainStatusChanged(DomainEvent):
    """A firm's sender domain moved (R-01-T27; C16 v1.1 §7): `pending_dns`, `verified`, `failed`
    or `revoked`. The From of later client mail follows it."""

    event_type: ClassVar[str] = "sending_domain.status_changed"
    domain_id: Annotated[UUID, classified("internal")]
    status: Annotated[str, classified("internal")]


class SendingDomainVerified(DomainEvent):
    """The firm's sender domain passed DKIM and MAIL FROM (R-01-T27): the in-app
    `sending_domain_verified` for its firm and security admins (R-01 §4.8)."""

    event_type: ClassVar[str] = "sending_domain.verified"
    domain_id: Annotated[UUID, classified("internal")]


class SendingDomainFailed(DomainEvent):
    """72 hours went by without verification (R-01-T27): the in-app `sending_domain_failed`."""

    event_type: ClassVar[str] = "sending_domain.failed"
    domain_id: Annotated[UUID, classified("internal")]


class MessageDeliveryStatusChanged(DomainEvent):
    """SES said what happened to a send (R-01-T27; C16 v1.1 §7): `delivered`, `bounced`,
    `complained` or `rejected`. TXP-12's "Bounced" reads the same status."""

    event_type: ClassVar[str] = "message.delivery_status_changed"
    message_id: Annotated[UUID, classified("internal")]
    status: Annotated[str, classified("internal")]


class InboundMessageRecorded(DomainEvent):
    """A message reached the firm inbox (N-01-T09): any channel; identifiers only."""

    event_type: ClassVar[str] = "inbound_message.recorded"

    thread_id: Annotated[UUID, classified("internal")]
    message_id: Annotated[UUID, classified("internal")]
    channel: Annotated[str, classified("internal")]
    client_id: Annotated[UUID | None, classified("internal")]


class InboxAttachmentReceived(DomainEvent):
    """A file of an inbound message was scanned and stored (N-01-T09), New or Waiting."""

    event_type: ClassVar[str] = "inbox_attachment.received"

    attachment_id: Annotated[UUID, classified("internal")]
    message_id: Annotated[UUID, classified("internal")]
    thread_id: Annotated[UUID, classified("internal")]
    status: Annotated[str, classified("internal")]
