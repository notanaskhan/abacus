"""A firm app's disable suspends its client connections (W-01-T08 rest; SPEC-659 AC-25; OQ-5;
DEC-5083).

When a firm disables a client-authorised firm app (QuickBooks Online) from WB-10, every live
client connection of that provider in the firm is suspended inside the caller's unit of work:
status `needs_attention` with the reason `firm_app_disabled` (read as "Needs reauth" in closes
and POR-16, `entity.REAUTH_REASONS`), the sealed secret retired to the revocation queue (so the
client re-authorises; the provider revokes the grant after commit), and one
`connection.suspended` audit row per connection. Received data stays. The health pass leaves a
suspended connection alone: there is no secret to probe until the client reconnects.

The integrations service calls it after authorising `integration.disconnect_firm` (typed name,
fresh MFA); nothing here authorises again. The firm-wide scope is the action's: every client
entity's connection of the provider, walls notwithstanding (the firm app is the firm's).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.connections.grants import retire_grant
from abacus.modules.connections.models import Connection
from abacus.modules.connections.repository import LIVE, set_connection

FIRM_APP_DISABLED: Final = "firm_app_disabled"


async def suspend_for_firm_app(tx: UnitOfWork, tenant_id: UUID, provider: str) -> int:
    """Suspend the firm's live connections of `provider`; returns how many were suspended."""
    found = await tx.session.scalars(
        select(Connection)
        .where(
            Connection.tenant_id == tenant_id,
            Connection.provider == provider,
            Connection.status.in_(LIVE),
        )
        .order_by(Connection.id)
        .with_for_update()
    )
    suspended = 0
    for connection in found.all():
        if connection.status_reason_code == FIRM_APP_DISABLED:
            continue  # already suspended by an earlier disable
        await set_connection(
            tx.session,
            connection.id,
            status="needs_attention",
            status_reason_code=FIRM_APP_DISABLED,
        )
        await retire_grant(tx, tenant_id, connection.id, FIRM_APP_DISABLED)
        tx.record(
            "connection.suspended",
            target=Target("connection", connection.id),
            after=Ref(client_entity_id=connection.client_entity_id),
        )
        suspended += 1
    return suspended
