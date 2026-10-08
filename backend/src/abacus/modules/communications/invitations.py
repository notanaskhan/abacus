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
from abacus.modules.identity.api import issue_invitation_token

SUBJECT: Final = "You're invited to an audit engagement"
TEMPLATE: Final = (
    "You've been invited to share documents for an audit engagement.\n\n"
    "Open this link to accept: {link}\n\n"
    "The link works once and expires on {expires}. If you weren't expecting this, ignore it."
)
_log = get_logger(__name__)


async def deliver_invitation(event: OutboxEvent) -> None:
    invitation_id = UUID(str(event.payload["invitation_id"]))
    issued = await issue_invitation_token(event.tenant_id, invitation_id)
    if issued is None:
        return  # revoked, accepted or expired meanwhile: nothing to send
    expires = f"{issued.expires_at:%d %B %Y}"
    link = f"{settings().app_base_url}/client/accept#token={issued.token}"
    await asyncio.to_thread(
        transport().send,
        to=issued.email,
        subject=SUBJECT,
        body=TEMPLATE.format(link=link, expires=expires),
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
            body=TEMPLATE.format(link="[link removed]", expires=expires),
            status="sent",
            violations=[],
            created_by=issued.invited_by,
        )
        tx.record("message.sent", target=Target("message", message_id))
    _log.info("invitation.email_sent", invitation_id=invitation_id, message_id=message_id)
