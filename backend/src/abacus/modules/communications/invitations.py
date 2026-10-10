"""Invitation emails (SPEC-015 AC-1, AC-10; TASK-030 D1, D4).

On `client_invitation.issued`, ask identity for a fresh token (only its hash is kept), send the
fixed template through the transport, and record the message with the link redacted, so the
token is never stored. A redelivery issues a new token, and the previous one stops working.
"""

from __future__ import annotations

import asyncio
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Target, uow
from abacus.modules.communications.repository import insert_message
from abacus.modules.communications.transport import transport
from abacus.modules.engagements.api import engagement_label
from abacus.modules.identity.api import (
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
    expires = f"{issued.expires_at:%d %B %Y}"
    link = f"{settings().app_base_url}/client/accept#token={issued.token}"
    names = await firm_wording(event.tenant_id, issued.engagement_id)
    await asyncio.to_thread(
        transport().send,
        to=issued.email,
        subject=SUBJECT.format(**names),
        body=TEMPLATE.format(link=link, expires=expires, **names),
        sender_name=names["firm"],
    )
    message_id = uuid4()
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
            status="sent",
            violations=[],
            created_by=issued.invited_by,
        )
        tx.record("message.sent", target=Target("message", message_id))
    _log.info("invitation.email_sent", invitation_id=invitation_id, message_id=message_id)


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
    await asyncio.to_thread(
        transport().send,
        to=issued.email,
        subject=STAFF_SUBJECT.format(firm=firm),
        body=STAFF_TEMPLATE.format(firm=firm, link=link, expires=f"{issued.expires_at:%d %B %Y}"),
        sender_name=firm,
    )
    _log.info("staff_invitation.email_sent", invitation_id=invitation_id)
