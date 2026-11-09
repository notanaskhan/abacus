"""The client's "approval requested" email (R-02-T14; R-02 AC-36; DEC-3140).

Subscribes to C18's `client_approval.requested`. When the provider names the contact the item went
to and the person who sent it (A-06's proposed entries do), the contact gets the firm's
`approval_requested` email in the sender's name, as they are now (`member_context`: None once
they have left the firm, and then nothing is sent). One email per send: the message id derives
from the send and the contact, so the other items of the same send, and any redelivery, answer
what the first recorded and send nothing again. The words are each firm's (database content); a
template the firm has not published blocks the email (recorded `blocked`, logged) while the item
still shows on the portal's Home. No amount, no account and no entry text is a variable.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.logging import get_logger
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.communications.api import RecipientRef, SendScope, send_templated
from abacus.modules.engagements.api import ClientApprovalRequested, work_item_titles
from abacus.modules.identity.api import Forbidden, firm_name, member_context
from abacus.modules.organisations.api import contact_facts

TEMPLATE_KEY: Final = "approval_requested"
_log = get_logger(__name__)


def _uuid(payload: dict[str, object], key: str) -> UUID | None:
    value = payload.get(key)
    try:
        return UUID(str(value)) if value is not None else None
    except ValueError:
        return None


async def on_approval_requested(event: OutboxEvent) -> None:
    contact = _uuid(event.payload, "recipient_contact_id")
    sender = _uuid(event.payload, "sent_by")
    engagement_id = _uuid(event.payload, "engagement_id")
    send_id = _uuid(event.payload, "send_id") or _uuid(event.payload, "item_id")
    scope_id = _uuid(event.payload, "scope_id")
    if contact is None or sender is None or engagement_id is None or send_id is None:
        return  # a provider that names no recipient or sender sends no email
    ctx = await member_context(event.tenant_id, sender)
    if ctx is None:
        _log.info("approval_requested.sender_gone", send_id=send_id)
        return
    async with tenant_session(ctx.tenant) as session:
        person = (await contact_facts(session, [contact])).get(contact)
    if person is None:
        _log.info("approval_requested.contact_missing", send_id=send_id)
        return
    titles = (
        await work_item_titles(ctx.tenant, [scope_id])
        if scope_id is not None and event.payload.get("scope_kind") == "work_item"
        else {}
    )
    recipient = (
        RecipientRef("user", person.user_id)
        if person.user_id is not None
        else RecipientRef("contact", contact)
    )
    try:
        sent = await send_templated(
            ctx,
            TEMPLATE_KEY,
            recipient,
            {
                "client_first_name": person.display_name.split(" ")[0] or "there",
                "firm_name": await firm_name(event.tenant_id),
                "work_item": titles.get(scope_id, "") if scope_id is not None else "",
                "portal_link": f"{settings().app_base_url.rstrip('/')}/portal",
            },
            scope=SendScope(engagement_id=engagement_id),
            idempotency_key=f"{TEMPLATE_KEY}:{send_id}:{contact}",
        )
    except (Forbidden, NotFound, DomainInvalid, DomainConflict) as refused:
        # Fail closed and logged: the sender may no longer send on the engagement.
        _log.warning("approval_requested.refused", send_id=send_id, error=type(refused).__name__)
        return
    if sent.status == "blocked":
        _log.info("approval_requested.blocked", send_id=send_id, reason=sent.blocked_reason)


SUBSCRIPTIONS: Final = {ClientApprovalRequested.event_type: on_approval_requested}
