"""AUD-06's *Ask client to reconnect* (A-02-T23; TASK-1471; SPEC-333 AC-44, A-02 AC-11.1;
DEC-611).

The route authorises before it reads anything: the connection's entity (404 when absent), then
`connection.reconnect_request` on an engagement of it (`authorised_engagement`: walls, other
clients and other firms answer 404; a role or independence 403), then `connections.portal_v2`
(404 off), and replays through `Idempotency-Key`.

A new request (`connections.request_reconnect`, one open per connection) is mailed to the
entity's owners: the firm's Reconnect request template (`reconnect_request`, R-01's database
rows, POR-20) through `communications.send_templated`, as the person who asked, so
`message.send`, the value lint, the scope check and suppression all apply, and a missing template
is recorded `blocked`, never sent from a constant. The values are the owner's first name, the
firm's name, the system's catalogue name (never the masked account label: the lint refuses an
account-number shape) and the portal link. Each send's idempotency key names the request, so a
replay sends nothing twice. A second ask while a request is open answers it and sends nothing,
unless that request's email never went out (blocked or failed): then the re-ask sends it once
more, in the next of a few numbered slots, so it never goes twice (review L1). A per-entity
cooldown across feeds is a follow-up (DEC-611).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel._flags import CONNECTIONS_PORTAL_V2
from abacus.kernel.config import settings
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.communications.api import (
    RecipientRef,
    SendScope,
    send_templated,
    templated_outcome,
)
from abacus.modules.connections.api import (
    ReconnectRequested,
    authorised_engagement,
    entity_of_connection,
    request_reconnect,
)
from abacus.modules.identity.api import AuthContext, client_owners, firm_name, names_of
from abacus.modules.integrations.catalog import client_catalog
from abacus.modules.integrations.contract import ConnectionPersonOut, ReconnectRequestOut

TEMPLATE_KEY: Final = "reconnect_request"
ACTION: Final = "connection.reconnect_request"
RESEND_SLOTS: Final = 5  # attempts per owner and request (review L1)
_log = get_logger(__name__)


def portal_link() -> str:
    """The portal's home, where the reconnect to-do waits (POR-02 → POR-16)."""
    return f"{settings().app_base_url.rstrip('/')}/portal"


async def _system_name(ctx: AuthContext, provider: str) -> str:
    for entry in await client_catalog(ctx.tenant):
        if entry.row.connector_provider == provider:
            return entry.row.name
    return "your connected system"


async def _send_one(
    ctx: AuthContext, asked: ReconnectRequested, owner: UUID, values: dict[str, str]
) -> bool:
    """One owner's email; True once it is queued (now or before). Attempts are keyed by the
    request and a slot number: a slot already queued means sent (nothing more), a slot recorded
    `blocked` (no published template, a lint finding, suppression) moves to the next, the first
    unused slot is tried once. So a re-ask sends what never went out and never sends twice
    (review L1); after `RESEND_SLOTS` blocked attempts the request needs a new one."""
    recipient = RecipientRef("user", owner)
    scope = SendScope(asked.engagement_id)
    for slot in range(RESEND_SLOTS):
        key = f"reconnect_request:{asked.id}" + (f":{slot}" if slot else "")
        try:
            recorded = await templated_outcome(
                ctx, TEMPLATE_KEY, recipient, scope=scope, idempotency_key=key
            )
            if recorded is not None:
                if recorded.status == "queued":
                    return True
                continue  # this slot never went out: try the next
            outcome = await send_templated(
                ctx, TEMPLATE_KEY, recipient, values, scope=scope, idempotency_key=key
            )
        except Exception as exc:  # the request stays recorded; a re-ask may send again
            _log.warning("reconnect_request.mail_failed", error=type(exc).__name__)
            return False
        if outcome.status != "queued":
            _log.info("reconnect_request.mail_blocked", reason=outcome.blocked_reason)
        return outcome.status == "queued"
    return False


async def _mail_owners(ctx: AuthContext, asked: ReconnectRequested, client_id: UUID) -> int:
    """The Reconnect request email to each owner of the entity; the number queued."""
    owners = await client_owners(
        ctx.tenant,
        client_id=client_id,
        client_entity_id=asked.client_entity_id,
        engagement_id=asked.engagement_id,
    )
    if not owners:
        return 0
    names = await names_of(owners)
    shared = {
        "firm_name": await firm_name(ctx.tenant_id),
        "connection_name": await _system_name(ctx, asked.provider),
        "portal_link": portal_link(),
    }
    queued = 0
    for owner in owners:
        first = (names.get(owner) or "").split(" ")[0] or "there"
        queued += await _send_one(ctx, asked, owner, {**shared, "client_first_name": first})
    return queued


async def reconnect_request(
    ctx: AuthContext, connection_id: UUID, idempotency_key: str | None = None
) -> ReconnectRequestOut:
    """AC-11.1: one open request, one email per owner for a new one; a repeated
    `Idempotency-Key` answers the first response."""
    entity_id = await entity_of_connection(ctx, connection_id)
    ref = await authorised_engagement(ctx, entity_id, ACTION)
    if not await flag_enabled(ctx.tenant, CONNECTIONS_PORTAL_V2):
        raise NotFound(CONNECTIONS_PORTAL_V2.name)

    async def run() -> tuple[int, dict[str, object]]:
        asked = await request_reconnect(ctx, ref, connection_id)
        await _mail_owners(ctx, asked, ref.client_id)
        names = await names_of([asked.requested_by_user_id])
        out = ReconnectRequestOut(
            id=asked.id,
            connection_id=asked.connection_id,
            requested_by=ConnectionPersonOut(
                user_id=asked.requested_by_user_id,
                display_name=names.get(asked.requested_by_user_id, "Former member"),
                kind="firm",
            ),
            requested_at=asked.requested_at,
        )
        return 201, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route=ACTION,
        key=idempotency_key,
        body={"connection_id": str(connection_id)},
        run=run,
    )
    return ReconnectRequestOut.model_validate(stored.body)
