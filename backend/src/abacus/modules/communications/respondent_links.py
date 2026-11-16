"""A respondent's single-use link, emailed at delivery (A-08-T18; A-08 §3 F4; SPEC-657 AC-6.4;
DEC-5324; red).

A confirmation's send asks for its link (`confirmation.link_requested`, identifiers only); this
delivers it. The owner of the subject (assurance, for a confirmation) registers two callables:
the facts the message needs (the address, opened only here, and the template's values) and a
minter that issues the link principal now and returns its raw token. The token lives only in
memory: it is never stored (the principal keeps its hash), logged or put in an event. The message
is the firm's published `confirmation_request` template; a firm whose client mail is not open
sends nothing (the respondent audience is gated, DEC-953). Only communications sends (COMM-001).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent
from abacus.modules.communications.deliveries import send_email
from abacus.modules.communications.sending_domains import client_mail_open
from abacus.modules.communications.templates import current_version, render
from abacus.modules.identity.api import firm_name

_log = get_logger(__name__)
TEMPLATE_KEY: Final = "confirmation_request"


@dataclass(frozen=True)
class RespondentFacts:
    address: str
    respondent_org: str
    organisation_name: str
    due_date: str


FactsProvider = Callable[[TenantContext, UUID], Awaitable[RespondentFacts | None]]
LinkMinter = Callable[[TenantContext, UUID], Awaitable[str | None]]
_SLOTS: dict[str, tuple[FactsProvider, LinkMinter]] = {}


def register_respondent_link(kind: str, facts: FactsProvider, minter: LinkMinter) -> None:
    """The subject's owner registers once, at import; a reload replaces itself."""
    _SLOTS[kind] = (facts, minter)


async def deliver_respondent_link(event: OutboxEvent) -> None:
    """On `confirmation.link_requested`: mint the link now and email it to the respondent."""
    kind, subject = "confirmation", UUID(str(event.payload["confirmation_id"]))
    slot = _SLOTS.get(kind)
    if slot is None:
        _log.warning("respondent_link.no_owner", kind=kind)
        return
    if not await client_mail_open(event.tenant_id):
        _log.info("respondent_link.client_mail_closed", subject_id=subject)
        return
    version = await current_version(TEMPLATE_KEY)
    if version is None:
        _log.warning("respondent_link.no_template", subject_id=subject)
        return
    tenant = TenantContext(event.tenant_id, "system", f"respondent_link:{subject}")
    facts_of, mint = slot
    facts = await facts_of(tenant, subject)
    if facts is None:
        return  # revoked, answered or no longer sent: nothing to deliver
    token = await mint(tenant, subject)
    if token is None:
        return
    firm = await firm_name(event.tenant_id)
    values = {
        "respondent_org": facts.respondent_org,
        "firm_name": firm,
        "organisation_name": facts.organisation_name,
        "due_date": facts.due_date,
        "portal_link": f"{settings().app_base_url.rstrip('/')}/confirm/{token}",
    }
    rendered = render(version, {k: values.get(k, "") for k in version.variables})
    message_id = uuid4()
    sent = await send_email(
        tenant_id=event.tenant_id,
        message_id=message_id,
        to=facts.address,
        subject=rendered.subject,
        body=rendered.body_text,
        sender_name=firm,
    )
    _log.info("respondent_link.sent", subject_id=subject, message_id=message_id, sent=sent)
