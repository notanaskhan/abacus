"""The portal sign-in code email (P-08-T10; DEC-155; SPEC-320 Story 2).

Identity's `portal.sign_in_code_requested` names a challenge only. Here the code is issued at
delivery (`issue_sign_in_code`, so it is never stored) and sent in the firm's name from the
published C16 template `portal.sign_in_code` (imported per environment, never in code). The
template is filled only with the code, the firm's name and the minutes it lasts. Without a
published template nothing is sent and the miss is logged by challenge id; the person can resend.
The send goes through `send_email`: a synthetic firm's mail reaches only the sink.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent
from abacus.modules.communications.deliveries import send_email
from abacus.modules.communications.templates import current_version, render
from abacus.modules.identity.api import contact_emails, firm_name, issue_sign_in_code

TEMPLATE_KEY: Final = "portal.sign_in_code"
_MINUTES: Final = "10"
_log = get_logger(__name__)


async def deliver_sign_in_code(event: OutboxEvent) -> None:
    challenge_id = UUID(str(event.payload["challenge_id"]))
    version = await current_version(TEMPLATE_KEY)
    if version is None:
        _log.warning("portal_sign_in.no_template", challenge_id=challenge_id)
        return
    issued = await issue_sign_in_code(challenge_id)
    if issued is None:
        return  # used, expired or already sent meanwhile: nothing to send
    address = (await contact_emails([issued.user_id])).get(issued.user_id)
    if address is None:
        _log.warning("portal_sign_in.no_address", challenge_id=challenge_id)
        return
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
    _log.info(
        "portal_sign_in.code_sent", challenge_id=challenge_id, message_id=message_id, sent=sent
    )


MFA_RESET_TEMPLATE_KEY: Final = "portal.mfa_reset_notice"


async def deliver_mfa_reset_notice(event: OutboxEvent) -> None:
    """P-08-T21 (Story 7.2): the firm reset the person's second step; tell them, in the firm's
    name, from the C16 template `portal.mfa_reset_notice` (imported per environment; without it
    nothing is sent and the miss is logged). Filled only with the firm's name."""
    user_id = UUID(str(event.payload["user_id"]))
    version = await current_version(MFA_RESET_TEMPLATE_KEY)
    if version is None:
        _log.warning("portal_mfa.no_reset_template", tenant_id=event.tenant_id)
        return
    address = (await contact_emails([user_id])).get(user_id)
    if address is None:
        _log.warning("portal_mfa.no_address", tenant_id=event.tenant_id)
        return
    firm = await firm_name(event.tenant_id)
    rendered = render(version, {k: {"firm_name": firm}.get(k, "") for k in version.variables})
    message_id = uuid4()
    sent = await send_email(
        tenant_id=event.tenant_id,
        message_id=message_id,
        to=address,
        subject=rendered.subject,
        body=rendered.body_text,
        sender_name=firm,
    )
    _log.info("portal_mfa.reset_notice_sent", message_id=message_id, sent=sent)
