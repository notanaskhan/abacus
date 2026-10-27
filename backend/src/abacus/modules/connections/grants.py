"""Retiring a connection's grant and revoking it at the provider (A-02-T16 security review M1;
DEC-515; ADR-040, ADR-035).

When a client disconnects, or a reconnect replaces a grant (and the legacy flow replaces a
ledger), the live sealed secret is deleted at once, in the caller's unit of work, and its sealed
blob moves to `connection_grant_revocations` with an outbox event naming the row. After commit,
the outbox consumer opens it, asks the connector to revoke the grant at the provider, audits the
result (`connection.grant_revoked`, a result index: never provider text), and deletes the row:
the crypto-erase. A provider that is down is retried by the relay; one without revocation, or
one that refuses, is recorded and the row erased all the same.
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Final, Literal
from uuid import UUID

from sqlalchemy import delete, insert, select

from abacus.kernel.classification import classified
from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import DomainEvent, Ref, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.connections.connector import ConnectorError, NotSupported, Unavailable
from abacus.modules.connections.models import (
    Connection,
    ConnectionGrantRevocation,
    ConnectionSecret,
)
from abacus.modules.connections.service import connector_for

_log = get_logger(__name__)
Reason = Literal["disconnected", "replaced"]
# Audited as an index: keep the order, append only.
RESULTS: Final = ("revoked", "not_supported", "refused", "no_connection")


class GrantRevocationRequested(DomainEvent):
    """A retired grant waits for the provider's revoke (identifiers only)."""

    event_type: ClassVar[str] = "connection_grant.revocation_requested"

    revocation_id: Annotated[UUID, classified("internal")]
    connection_id: Annotated[UUID, classified("internal")]


async def retire_grant(
    tx: UnitOfWork, tenant_id: UUID, connection_id: UUID, reason: Reason
) -> bool:
    """Inside the caller's unit of work: move the connection's sealed secret to the revocation
    queue and delete the live row. True when there was one."""
    sealed = await tx.session.scalar(
        select(ConnectionSecret.sealed).where(ConnectionSecret.connection_id == connection_id)
    )
    if sealed is None:
        return False
    revocation_id = await tx.session.scalar(
        insert(ConnectionGrantRevocation)
        .values(tenant_id=tenant_id, connection_id=connection_id, sealed=sealed, reason=reason)
        .returning(ConnectionGrantRevocation.id)
    )
    await tx.session.execute(
        delete(ConnectionSecret).where(ConnectionSecret.connection_id == connection_id)
    )
    if revocation_id is not None:
        tx.emit(GrantRevocationRequested(revocation_id=revocation_id, connection_id=connection_id))
    return True


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "connections.grant_revoke")


async def revoke_retired(event: OutboxEvent) -> None:
    """The outbox consumer. Raises on a provider outage, so the relay retries."""
    raw = event.payload.get("revocation_id")
    if raw is None:
        return
    revocation_id = UUID(str(raw))
    tenant = _system(event.tenant_id)
    async with tenant_session(tenant) as session:
        row = await session.get(ConnectionGrantRevocation, revocation_id)
        connection = None if row is None else await session.get(Connection, row.connection_id)
    if row is None:
        return  # already answered (a replay)
    if connection is None:
        result = "no_connection"
    else:
        credentials = await open_sealed(tenant.tenant_id, row.sealed, str(connection.id))
        try:
            await connector_for(connection, credentials).revoke()
            result = "revoked"
        except Unavailable:
            raise  # retried by the relay
        except NotSupported:
            result = "not_supported"
        except ConnectorError:
            result = "refused"
    async with uow(tenant) as tx:
        gone = await tx.session.scalar(
            delete(ConnectionGrantRevocation)
            .where(ConnectionGrantRevocation.id == revocation_id)
            .returning(ConnectionGrantRevocation.id)
        )
        if gone is None:
            return
        tx.record(
            "connection.grant_revoked",
            target=Target("connection", row.connection_id),
            after=Ref(result=RESULTS.index(result)),
        )
    _log.info("connection.grant_revoked", result=result)


SUBSCRIPTIONS = {GrantRevocationRequested.event_type: revoke_retired}
