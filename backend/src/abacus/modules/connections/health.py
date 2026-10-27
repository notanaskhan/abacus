"""The daily connection health pass (A-02-T25; A-02 §3.11; DEC-708).

`ConnectionHealthWorkflow` runs `check_connection_health()` once a day on the Schedule
`connection_health:platform` (`kernel.dispatch`; overlap SKIP). For each firm, inside its own
session, every live connection of a provider that reaches a host (not the demo ledger's local
files or an import) is refreshed and asked for its health:

- **Healthy:** the connection is `active` again, its reason cleared and `last_checked_at` set.
- **A grant problem** (`token_expired`, `invalid_grant`, the C20 reauth reasons): `needs_attention`
  with that reason, which C2 shows as **Needs reauth**; the first time only, the
  `connection.needs_reauth` event tells its leads (`connection_needs_reauth`). Retries are refused
  for it (`entity.REAUTH_REASONS`) until the client signs in again.
- **Anything else** (an outage, a provider error): `needs_attention` with the code, which a retry
  may clear.
- **Reauth due:** a connection whose `reauth_due_at` falls within seven days is told once per due
  date (`connection.reauth_due`).

No pull runs on a connection that needs attention: `pipeline.pull_raw` refuses anything that is
not `active`. A failing firm is logged and counted and the others still run. The audit row is the
system's (`connection.health_checked`, identifiers and the reason code only).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import select, text
from temporalio import activity

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.connect import credentials_of
from abacus.modules.connections.connector import ConnectorError
from abacus.modules.connections.entity import REAUTH_REASONS
from abacus.modules.connections.events import ConnectionNeedsReauth, ConnectionReauthDue
from abacus.modules.connections.models import Connection
from abacus.modules.connections.repository import LIVE, lock_connection, set_connection
from abacus.modules.connections.service import (
    FAKE_PREFIX,
    NETWORKLESS_PROVIDERS,
    connector_for,
)
from abacus.modules.identity.api import firm_tenant_ids

REAUTH_NOTICE_DAYS: Final = 7
_ACTOR: Final = "connections:health"
_log = get_logger(__name__)
_checked = meter(__name__).create_counter(
    "abacus.connection_health.checked", description="Connections checked, by outcome"
)
_firm_failures = meter(__name__).create_counter(
    "abacus.connection_health.firm_failed", description="Firms a health pass could not check"
)


async def _engagement_of(tenant: TenantContext, connection: Connection) -> UUID | None:
    """The engagement the connection was last started from (its leads are told)."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(
                "SELECT engagement_id FROM connection_states WHERE client_entity_id = :e "
                "AND provider = :p ORDER BY created_at DESC LIMIT 1"
            ),
            {"e": connection.client_entity_id, "p": connection.provider},
        )
    return found if isinstance(found, UUID) else None


async def _probe(tenant: TenantContext, connection: Connection) -> str | None:
    """None when healthy, else the failure's safe code."""
    connector = connector_for(connection, await credentials_of(tenant, connection))
    try:
        await connector.refresh()
        return None if await connector.health() else "health_check_failed"
    except ConnectorError as exc:
        return exc.code


async def check_connection(tenant: TenantContext, connection: Connection) -> str:
    """One connection's check; returns its outcome (`ok`, `needs_reauth`, `needs_attention`,
    `skipped`). Re-read under a row lock, so a connection revoked or replaced meanwhile is left
    alone."""
    code = await _probe(tenant, connection)
    engagement_id = await _engagement_of(tenant, connection)
    now = system_now()
    async with uow(tenant) as tx:
        current = await lock_connection(tx.session, connection.id)
        if current is None or current.status not in LIVE:
            return "skipped"
        was_reauth = current.status_reason_code in REAUTH_REASONS
        if code is None:
            await set_connection(
                tx.session,
                current.id,
                status="active",
                status_reason_code=None,
                last_checked_at=now,
                last_check_ok=True,
            )
            outcome = "ok"
        else:
            await set_connection(
                tx.session,
                current.id,
                status="needs_attention",
                status_reason_code=code,
                last_checked_at=now,
                last_check_ok=False,
            )
            outcome = "needs_reauth" if code in REAUTH_REASONS else "needs_attention"
            if outcome == "needs_reauth" and not was_reauth:
                tx.emit(
                    ConnectionNeedsReauth(
                        connection_id=current.id, engagement_id=engagement_id, reason=code
                    )
                )
        due = current.reauth_due_at
        if (
            due is not None
            and due - now <= timedelta(days=REAUTH_NOTICE_DAYS)
            and current.reauth_noticed_for != due
        ):
            await set_connection(tx.session, current.id, reauth_noticed_for=due)
            tx.emit(ConnectionReauthDue(connection_id=current.id, engagement_id=engagement_id))
        tx.record(
            "connection.health_checked",
            target=Target("connection", current.id),
            after=Ref(outcome=outcome, **({"reason": code} if code else {})),
        )
    return outcome


async def _check_firm(tenant_id: UUID) -> int:
    tenant = TenantContext(tenant_id, "system", _ACTOR)
    async with tenant_session(tenant) as session:
        connections = (
            (
                await session.execute(
                    select(Connection)
                    .where(Connection.status.in_(LIVE))
                    .where(Connection.provider.not_in(NETWORKLESS_PROVIDERS))
                    .where(Connection.provider.not_like(f"{FAKE_PREFIX}%"))
                    .order_by(Connection.created_at, Connection.id)
                )
            )
            .scalars()
            .all()
        )
    for connection in connections:
        outcome = await check_connection(tenant, connection)
        _checked.add(1, {"outcome": outcome})
    return len(connections)


async def check_connection_health() -> int:
    """Every firm's pass; returns how many connections were checked."""
    total = 0
    for tenant_id in await firm_tenant_ids():
        try:
            total += await _check_firm(tenant_id)
        except Exception:  # one firm's failure never stops the others
            _firm_failures.add(1)
            _log.error("connection_health.firm_failed", tenant_id=tenant_id)
    return total


@activity.defn(name="connections.check_connection_health")
async def check_connection_health_activity() -> int:
    return await check_connection_health()
