"""Follow-ups to client contacts, in the firm's name (SPEC-027 P-4; P-06-T14; DEC-74, DEC-220).

The agents module works out who is followed up about what and keeps the drafts; this module
composes and sends (COMM-001). The text is the published C16 template, never code (AGENTS 16):
`notification.follow_up_sent` (the Reminder template) or, for an SHL-20 return,
`notification.follow_up_sent.screening_return` (the Return template). It is filled only with
the recipient's first name, the engagement's display name, the firm's name, a portal link and
the requests' titles, one per line: names and titles the recipient already sees in the portal.
No model text, no amounts, no account numbers (DEC-79, ADR-111).

A person sends: the agents module authorises `follow_up.send` (agent: deny) and the email
leaves when the relay delivers the grant-held `follow_up.sent` event after the 10-s Undo window
(ADR-161). `deliver_follow_up` is that delivery; the message ID is the follow-up's, so a
redelivery never sends twice.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Target, uow
from abacus.modules.communications.deliveries import SUPPRESSED, deliver
from abacus.modules.communications.models import Message
from abacus.modules.communications.notification_email import display_name, single_line
from abacus.modules.communications.repository import insert_message
from abacus.modules.communications.templates import TemplateInvalid, current_version, render
from abacus.modules.identity.api import contact_emails, firm_name, names_of

REMINDER_TEMPLATE: Final = "notification.follow_up_sent"
RETURN_TEMPLATE: Final = "notification.follow_up_sent.screening_return"
_SUPPORTED: Final = frozenset(
    {"recipient_first_name", "engagement_display_name", "firm_name", "app_link", "request_list"}
)
_log = get_logger(__name__)


class FollowUpTemplateMissing(DomainConflict):
    """No follow-up template is published yet; platform staff import it (C16)."""

    code = "follow_up_template_missing"


@dataclass(frozen=True)
class ComposedFollowUp:
    subject: str
    body: str
    template_key: str


def _system(tenant_id: UUID, engagement_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", f"follow-up:{engagement_id}")


async def compose_follow_up(
    tenant_id: UUID,
    engagement_id: UUID,
    recipient_user_id: UUID,
    titles: Sequence[str],
    template_key: str = REMINDER_TEMPLATE,
) -> ComposedFollowUp:
    """The subject and body from the published template. Byte-identical for the same template
    version and facts, so the preview is the email."""
    version = await current_version(template_key)
    if version is None:
        raise FollowUpTemplateMissing(facts={"template_key": template_key})
    if not set(version.variables) <= _SUPPORTED:
        raise TemplateInvalid  # e.g. `kind_sentence`: a notification's, not a follow-up's
    lines = [single_line(t) for t in titles if t.strip()]
    if not lines:
        raise TemplateInvalid
    name = (await names_of([recipient_user_id])).get(recipient_user_id, "")
    values = {
        "recipient_first_name": single_line(name).partition(" ")[0],
        "engagement_display_name": single_line(await display_name(tenant_id, engagement_id)),
        "firm_name": single_line(await firm_name(tenant_id)),
        "app_link": f"{settings().app_base_url}/client/engagements/{engagement_id}",
        "request_list": "\n".join(f"- {line}" for line in lines),
    }
    rendered = render(version, {k: values[k] for k in version.variables})
    return ComposedFollowUp(rendered.subject, rendered.body_text, template_key)


async def deliver_follow_up(
    tenant_id: UUID,
    follow_up_id: UUID,
    engagement_id: UUID,
    recipient_user_id: UUID,
    sent_by: UUID,
    subject: str,
    body: str,
) -> bool:
    """Send one follow-up email the person sent, once. True when it went out (or already had);
    False when the address is unknown or suppressed, or email is paused (recorded `blocked`)."""
    system = _system(tenant_id, engagement_id)
    async with tenant_session(system) as session:
        done = await session.scalar(select(Message.id).where(Message.id == follow_up_id))
    if done is not None:
        return True  # a redelivery: the message is already recorded
    address = (await contact_emails([recipient_user_id])).get(recipient_user_id)
    blocked: dict[str, str] | None = SUPPRESSED  # no address: recorded as not deliverable
    if address is not None:
        blocked = await deliver(
            to=address,
            subject=subject,
            body=body,
            sender_name=await firm_name(tenant_id),
            tenant_id=tenant_id,
            message_id=follow_up_id,
        )
    else:
        _log.warning("follow_up.no_address", tenant_id=tenant_id, follow_up_id=follow_up_id)
    async with uow(system) as tx:
        await insert_message(
            tx.session,
            message_id=follow_up_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            channel="email",
            recipient_ref=f"user:{recipient_user_id}",
            body=body,
            status="sent" if blocked is None else "blocked",
            violations=[] if blocked is None else [blocked],
            created_by=sent_by,
        )
        tx.record(
            "message.sent" if blocked is None else "message.blocked",
            target=Target("message", follow_up_id),
        )
    return blocked is None
