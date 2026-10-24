"""A notification's email (P-01-T12; C16 email half; COMM-001).

The notifications module decides that a person gets an email; this renders and sends it. The
text is the published C16 template `notification.<kind>` (imported by platform staff, never in
code). It is filled only with the four whitelisted values: the recipient's first name, the kind
sentence, the engagement's display name ("Client · engagement", P-01 Q6) and a link to the
drawer. These are names and a link the recipient can already see, never a Restricted fact.

The send goes through `send_email`, so a synthetic firm's mail reaches only the sink and a
suppressed address is refused. The message ID is the notification's ID: one notification, one
message, matched by SES delivery events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.modules.communications.deliveries import send_email
from abacus.modules.communications.templates import current_version, render
from abacus.modules.engagements.api import engagement_label
from abacus.modules.identity.api import contact_emails, firm_name, names_of

Outcome = Literal["sent", "suppressed", "failed"]
_PLACES: Final = ("{engagement}", "{subject}")
_log = get_logger(__name__)


@dataclass(frozen=True)
class NotificationMail:
    tenant_id: UUID
    notification_id: UUID
    kind: str
    recipient_user_id: UUID
    engagement_id: UUID | None
    sentence: str  # the kind's sentence; `{engagement}` and `{subject}` take the display name


def template_key(kind: str) -> str:
    return f"notification.{kind}"


async def display_name(tenant_id: UUID, engagement_id: UUID | None) -> str:
    if engagement_id is None:
        return await firm_name(tenant_id)
    label = await engagement_label(
        TenantContext(tenant_id, "system", "notifications:email"), engagement_id
    )
    if label is None:
        return await firm_name(tenant_id)
    return f"{label.client_name} · {label.name}"


def single_line(value: str) -> str:
    return " ".join(value.split())


async def send_notification_email(mail: NotificationMail) -> Outcome:
    """Render and send. `failed` when no template is published for the kind or the person has
    no address; `suppressed` when `send_email` refused it (suppression or the sink rule)."""
    version = await current_version(template_key(mail.kind))
    if version is None:
        _log.warning(
            "notification_email.no_template",
            kind=mail.kind,
            tenant_id=mail.tenant_id,
            notification_id=mail.notification_id,
        )
        return "failed"
    address = (await contact_emails([mail.recipient_user_id])).get(mail.recipient_user_id)
    if address is None:
        return "failed"
    name = (await names_of([mail.recipient_user_id])).get(mail.recipient_user_id, "")
    display = single_line(await display_name(mail.tenant_id, mail.engagement_id))
    sentence = mail.sentence
    for place in _PLACES:
        sentence = sentence.replace(place, display)
    values = {
        "recipient_first_name": single_line(name).partition(" ")[0],
        "kind_sentence": single_line(sentence),
        "engagement_display_name": display,
        "app_link": f"{settings().app_base_url}/?ov=notifications",
    }
    rendered = render(version, {k: values[k] for k in version.variables})
    sent = await send_email(
        tenant_id=mail.tenant_id,
        message_id=mail.notification_id,
        to=address,
        subject=rendered.subject,
        body=rendered.body_text,
        sender_name=await firm_name(mail.tenant_id),
    )
    return "sent" if sent else "suppressed"
