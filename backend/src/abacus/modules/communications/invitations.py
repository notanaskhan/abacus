"""Invitation emails (SPEC-015 AC-1, AC-10; TASK-030 D1, D4).

On `client_invitation.issued`, ask identity for a fresh token (only its hash is kept), send the
fixed template through the transport, and record the message with the link redacted, so the
token is never stored. A redelivery issues a new token, and the previous one stops working.

A contact invitation (P-07-T25; CLI-04; DEC-301) is sent from the firm's database Invitation
template instead (C16 `portal.invitation`, imported per environment; never text in code): in
the firm's name, filled only with the firm's name, the contact's first name and the one link,
so it carries no amount and never says "Accrued". Without a published template nothing is sent
and the miss is logged by invitation id; the firm can resend once one is imported.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Target, uow
from abacus.modules.communications.deliveries import SUPPRESSED, send_email
from abacus.modules.communications.repository import insert_message
from abacus.modules.communications.templates import current_version, render
from abacus.modules.engagements.api import engagement_label
from abacus.modules.identity.api import (
    IssuedInvitation,
    firm_name,
    issue_invitation_token,
    issue_staff_invitation_token,
)

# SPEC-025 AC-8: in the firm's name, naming the client and the engagement's year.
SUBJECT: Final = "{firm} invites you to their FY{year} audit of {client}"
TEMPLATE: Final = (
    "{firm} has invited you to share documents for their FY{year} audit of {client}.\n\n"
    "Open this link to accept: {link}\n\n"
    "The link works once and expires on {expires}. If you weren't expecting this, ignore it."
)
CONTACT_TEMPLATE_KEY: Final = "portal.invitation"
_log = get_logger(__name__)


async def firm_wording(tenant_id: UUID, engagement_id: UUID) -> dict[str, str]:
    """The firm, client and fiscal year, for the invitation's wording (plain text)."""
    label = await engagement_label(
        TenantContext(tenant_id, "system", "invitations"), engagement_id
    )
    return {
        "firm": await firm_name(tenant_id),
        "client": label.client_name if label is not None else "your company",
        "year": str(label.fiscal_year) if label is not None else "",
    }


async def deliver_invitation(event: OutboxEvent) -> None:
    invitation_id = UUID(str(event.payload["invitation_id"]))
    issued = await issue_invitation_token(event.tenant_id, invitation_id)
    if issued is None:
        return  # revoked, accepted or expired meanwhile: nothing to send
    if issued.contact_invitation:
        await _deliver_contact_invitation(event.tenant_id, invitation_id, issued)
        return
    expires = f"{issued.expires_at:%d %B %Y}"
    link = f"{settings().app_base_url}/client/accept#token={issued.token}"
    names = await firm_wording(event.tenant_id, issued.engagement_id)
    message_id = uuid4()
    sent = await send_email(
        to=issued.email,
        subject=SUBJECT.format(**names),
        body=TEMPLATE.format(link=link, expires=expires, **names),
        sender_name=names["firm"],
        tenant_id=event.tenant_id,
        message_id=message_id,
    )
    ctx = TenantContext(event.tenant_id, "system", f"invitation:{invitation_id}")
    async with uow(ctx) as tx:
        await insert_message(
            tx.session,
            message_id=message_id,
            tenant_id=event.tenant_id,
            engagement_id=issued.engagement_id,
            channel="email",
            recipient_ref=f"invitation:{invitation_id}",
            body=TEMPLATE.format(link="[link removed]", expires=expires, **names),
            status="sent" if sent else "blocked",
            violations=[] if sent else [SUPPRESSED],
            created_by=issued.invited_by,
        )
        tx.record(
            "message.sent" if sent else "message.blocked", target=Target("message", message_id)
        )
    _log.info(
        "invitation.email_sent", invitation_id=invitation_id, message_id=message_id, sent=sent
    )


async def _deliver_contact_invitation(
    tenant_id: UUID, invitation_id: UUID, issued: IssuedInvitation
) -> None:
    """CLI-04's invitation: the firm's template, its name as the sender, one call to action."""
    version = await current_version(CONTACT_TEMPLATE_KEY)
    if version is None:
        _log.warning("invitation.no_template", invitation_id=invitation_id)
        return
    firm = await firm_name(tenant_id)
    first = (issued.invitee_name or "").split(" ", 1)[0].strip()
    values = {
        "firm_name": firm,
        "recipient_first_name": first or "there",
        "app_link": f"{settings().app_base_url}/portal/invitation#token={issued.token}",
    }
    rendered = render(version, {k: values.get(k, "") for k in version.variables})
    message_id = uuid4()
    sent = await send_email(
        to=issued.email,
        subject=rendered.subject,
        body=rendered.body_text,
        sender_name=firm,
        tenant_id=tenant_id,
        message_id=message_id,
    )
    redacted = render(
        version,
        {k: (values | {"app_link": "[link removed]"}).get(k, "") for k in version.variables},
    )
    ctx = TenantContext(tenant_id, "system", f"invitation:{invitation_id}")
    async with uow(ctx) as tx:
        await insert_message(
            tx.session,
            message_id=message_id,
            tenant_id=tenant_id,
            engagement_id=issued.engagement_id,
            channel="email",
            recipient_ref=f"invitation:{invitation_id}",
            body=redacted.body_text,
            status="sent" if sent else "blocked",
            violations=[] if sent else [SUPPRESSED],
            created_by=issued.invited_by,
        )
        tx.record(
            "message.sent" if sent else "message.blocked", target=Target("message", message_id)
        )
    _log.info(
        "invitation.email_sent", invitation_id=invitation_id, message_id=message_id, sent=sent
    )


STAFF_SUBJECT: Final = "{firm} invites you to join their workspace"
STAFF_TEMPLATE: Final = (
    "{firm} has invited you to join their workspace on Abacus.\n\n"
    "Open this link to accept: {link}\n\n"
    "The link works once and expires on {expires}. If you weren't expecting this, ignore it."
)


async def deliver_staff_invitation(event: OutboxEvent) -> None:
    """SPEC-024 (TASK-041): the staff invitation's email. The token is issued now and never
    stored; the issue is audited by identity (`staff_invitation.token_issued`). Staff
    invitations have no engagement, so no engagement message is recorded."""
    invitation_id = UUID(str(event.payload["invitation_id"]))
    issued = await issue_staff_invitation_token(event.tenant_id, invitation_id)
    if issued is None:
        return  # revoked, accepted or expired meanwhile: nothing to send
    link = f"{settings().app_base_url}/join#token={issued.token}"
    firm = await firm_name(event.tenant_id)
    sent = await send_email(
        to=issued.email,
        subject=STAFF_SUBJECT.format(firm=firm),
        body=STAFF_TEMPLATE.format(firm=firm, link=link, expires=f"{issued.expires_at:%d %B %Y}"),
        sender_name=firm,
        tenant_id=event.tenant_id,
        message_id=uuid4(),  # no message is recorded for a staff invitation; the ID is for events
    )
    _log.info("staff_invitation.email_sent", invitation_id=invitation_id, sent=sent)
