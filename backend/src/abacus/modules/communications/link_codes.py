"""The link principal's email code (A-08-T15; ADR-146; the ADR-152 amendment).

Identity's `link_principal.code_requested` names a challenge only. Here the code is issued at
delivery (`issue_link_code`, so it is never stored) and sent to the address the link was minted
for,
in the firm's name, from the published C16 template `confirmation.respond_code` (imported per
environment, never in code), filled only with the code, the firm's name and the minutes it lasts.
Without the template nothing is sent and the miss is logged by challenge id.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.crypto import open_sealed
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent
from abacus.modules.communications.deliveries import send_email
from abacus.modules.communications.templates import current_version, render
from abacus.modules.identity.api import LINK_EMAIL_AAD, firm_name, issue_link_code

TEMPLATE_KEY: Final = "confirmation.respond_code"
_MINUTES: Final = "10"
_log = get_logger(__name__)


async def deliver_link_code(event: OutboxEvent) -> None:
    challenge_id = UUID(str(event.payload["challenge_id"]))
    version = await current_version(TEMPLATE_KEY)
    if version is None:
        _log.warning("link_code.no_template", challenge_id=challenge_id)
        return
    issued = await issue_link_code(challenge_id)
    if issued is None:
        return
    address = (await open_sealed(issued.tenant_id, issued.email_sealed, LINK_EMAIL_AAD)).decode()
    firm = await firm_name(issued.tenant_id)
    values = {"code": issued.code, "firm_name": firm, "expires_minutes": _MINUTES}
    rendered = render(version, {k: values.get(k, "") for k in version.variables})
    message_id = uuid4()
    sent = await send_email(
        tenant_id=issued.tenant_id,
        message_id=message_id,
        to=address,
        subject=rendered.subject,
        body=rendered.body_text,
        sender_name=firm,
    )
    _log.info("link_code.sent", challenge_id=challenge_id, message_id=message_id, sent=sent)
