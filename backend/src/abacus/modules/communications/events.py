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
