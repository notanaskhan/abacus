"""Overdue reminders, in the firm's name (SPEC-027 P-4; TASK-051 D3).

The engagement agent works out who is reminded about what; this module sends. Only
communications sends (COMM-001). The caller — the agent (Routine autonomy) or a person sending a
drafted reminder — must be allowed `follow_up.send` on the engagement; for the agent that's the
firm's autonomy policy, bounded by its initiator (ADR-025). A fixed template: item descriptions,
counts and a portal link, never evidence content.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.communications.invitations import firm_wording
from abacus.modules.communications.repository import insert_message
from abacus.modules.communications.transport import transport
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import Actor, AgentContext, AuthContext, authorise, contact_emails

SUBJECT: Final = "{firm} is still waiting for {count} {items} for their FY{year} audit of {client}"
TEMPLATE: Final = (
    "{firm} is still waiting for the following for their FY{year} audit of {client}:\n\n"
    "{lines}\n\n{note}Open your list: {link}\n"
)


def _creator(ctx: Actor) -> UUID:
    if isinstance(ctx, AuthContext):
        return ctx.user_id
    if isinstance(ctx, AgentContext):
        return ctx.initiator.user_id
    raise TypeError("a reminder is sent by a person or the engagement agent")


async def send_reminder(
    ctx: AuthContext | AgentContext,
    engagement_id: UUID,
    recipient_user_id: UUID,
    descriptions: Sequence[str],
    note: str | None = None,
) -> UUID:
    """Send one reminder email listing `descriptions`; returns the recorded message's id."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "follow_up.send", ref.resource())
    email = (await contact_emails([recipient_user_id])).get(recipient_user_id)
    if email is None:
        raise NotFound("recipient")
    names = await firm_wording(ctx.tenant_id, engagement_id)
    count = len(descriptions)
    lines = "\n".join(f"- {d}" for d in descriptions)
    kept = (note or "").strip()[:500]
    body = TEMPLATE.format(
        lines=lines,
        note=f"{kept}\n\n" if kept else "",
        link=f"{settings().app_base_url}/client/engagements/{engagement_id}",
        **names,
    )
    subject = SUBJECT.format(count=count, items="item" if count == 1 else "items", **names)
    await asyncio.to_thread(
        transport().send, to=email, subject=subject, body=body, sender_name=names["firm"]
    )
    message_id = uuid4()
    system = TenantContext(ctx.tenant_id, "system", f"reminder:{engagement_id}")
    async with uow(system) as tx:
        await insert_message(
            tx.session,
            message_id=message_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            channel="email",
            recipient_ref=f"user:{recipient_user_id}",
            body=body,
            status="sent",
            violations=[],
            created_by=_creator(ctx),
        )
        tx.record("message.sent", target=Target("message", message_id))
    return message_id
