"""Retiring a connection's grant and revoking it at the provider (A-02-T16 security review M1 and
round 2; DEC-515, DEC-518; ADR-040, ADR-035).

- `retire_grant`: when a client disconnects, or a reconnect replaces a grant (and the legacy flow
  replaces a ledger), the live sealed secret is deleted at once, in the caller's unit of work, and
  its sealed blob moves to `connection_grant_revocations` with an outbox event naming the row.
- `abandon_grant`: a completion refused after the code exchange (no connection exists) seals the
  fresh credentials on the same queue, bound to the state that obtained them, and records
  `connection.failed` with the refusal's code. The caller re-raises its own exception.
- `revoke_retired`, the outbox consumer, opens the blob, asks the connector to revoke the grant,
  audits the result (`connection.grant_revoked`, a result index: never provider text) and deletes
  the row: the crypto-erase. A failure that may pass (an outage, a key or network error) is raised
  for the relay to retry, until the relay's last attempt, when it is recorded `unreachable` and
  the row erased all the same; an egress refusal is `refused`. No sealed copy outlives the relay.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, ClassVar, Final, Literal
from uuid import UUID

from sqlalchemy import delete, insert, select

from abacus.kernel.classification import classified
from abacus.kernel.clock import system_now
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.egress import EgressRefused
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import DomainEvent, Ref, Target, UnitOfWork, uow
from abacus.kernel.uow.relay import MAX_ATTEMPTS, MAX_BACKOFF_SECONDS, OutboxEvent
from abacus.modules.connections.connector import ConnectorError, NotSupported, Unavailable
from abacus.modules.connections.models import (
    Connection,
    ConnectionGrantRevocation,
    ConnectionSecret,
    ConnectionState,
)
from abacus.modules.connections.service import connector_for
from abacus.modules.identity.api import AuthContext, Forbidden

_log = get_logger(__name__)
Reason = Literal["disconnected", "replaced"]
# Audited as an index: keep the order, append only.
RESULTS: Final = ("revoked", "not_supported", "refused", "no_connection", "unreachable")
# The relay retries a failed event with back-off 2, 4, … seconds and parks it at MAX_ATTEMPTS.
# Its last attempt comes at least this long after the first, so a revocation still failing that
# late is given up (`unreachable`) rather than raised into a parked event.
_RELAY_WINDOW: Final = sum(min(2**n, MAX_BACKOFF_SECONDS) for n in range(1, MAX_ATTEMPTS - 1))
GIVE_UP_AFTER: Final = timedelta(seconds=_RELAY_WINDOW)


class GrantRevocationRequested(DomainEvent):
    """A retired grant waits for the provider's revoke (identifiers only)."""

    event_type: ClassVar[str] = "connection_grant.revocation_requested"

    revocation_id: Annotated[UUID, classified("internal")]
    connection_id: Annotated[UUID | None, classified("internal")] = None


def _state_binding(state_id: UUID) -> str:
    return f"connection_state:{state_id}"


async def retire_grant(
    tx: UnitOfWork, tenant_id: UUID, connection_id: UUID, reason: Reason
) -> bool:
    """Inside the caller's unit of work: move the connection's sealed secret to the revocation
    queue and delete the live row. True when there was one."""
    sealed = await tx.session.scalar(
        select(ConnectionSecret.sealed).where(ConnectionSecret.connection_id == connection_id)
    )
    connection = await tx.session.get(Connection, connection_id)
    if sealed is None or connection is None:
        return False
    revocation_id = await tx.session.scalar(
        insert(ConnectionGrantRevocation)
        .values(
            tenant_id=tenant_id,
            client_entity_id=connection.client_entity_id,
            provider=connection.provider,
            connection_id=connection_id,
            sealed=sealed,
            reason=reason,
        )
        .returning(ConnectionGrantRevocation.id)
    )
    await tx.session.execute(
        delete(ConnectionSecret).where(ConnectionSecret.connection_id == connection_id)
    )
    if revocation_id is not None:
        tx.emit(GrantRevocationRequested(revocation_id=revocation_id, connection_id=connection_id))
    return True


def failure_code(exc: BaseException) -> str:
    if isinstance(exc, Forbidden):
        return "forbidden"
    found = getattr(exc, "code", None)
    return found if isinstance(found, str) else "error"


async def abandon_grant(
    ctx: AuthContext,
    found: ConnectionState,
    credentials: bytes | None,
    exc: BaseException,
    code_of: str,
) -> None:
    """A completion refused after the exchange: queue the fresh grant for revocation and record
    `connection.failed` (`code_of` is the refusal's fingerprint). Never raises: the caller's own
    exception is the one the person sees."""
    del exc
    try:
        async with uow(ctx.tenant) as tx:
            if credentials is not None:
                sealed = await seal(ctx.tenant_id, credentials, _state_binding(found.id))
                revocation_id = await tx.session.scalar(
                    insert(ConnectionGrantRevocation)
                    .values(
                        tenant_id=ctx.tenant_id,
                        client_entity_id=found.client_entity_id,
                        provider=found.provider,
                        state_id=found.id,
                        sealed=sealed,
                        reason="abandoned",
                    )
                    .returning(ConnectionGrantRevocation.id)
                )
                if revocation_id is not None:
                    tx.emit(GrantRevocationRequested(revocation_id=revocation_id))
            fields: dict[str, str | int] = {"code": code_of}
            if ctx.client:
                fields["client_actor"] = 1
            tx.record(
                "connection.failed",
                target=Target("connection_state", found.id),
                after=Ref(**fields),
            )
    except Exception as failed:  # the grant could not be queued: logged by class name only
        _log.error("connection.abandon_failed", error=type(failed).__name__)


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "connections.grant_revoke")


def _connection_of(row: ConnectionGrantRevocation, found: Connection | None) -> Connection | None:
    if row.connection_id is not None:
        return found
    return Connection(  # an abandoned grant: the connection that never was, for the connector
        id=UUID(int=0),
        tenant_id=row.tenant_id,
        client_entity_id=row.client_entity_id,
        provider=row.provider,
        status="revoked",
        scopes=[],
        created_by="system",
    )


def _binding(row: ConnectionGrantRevocation) -> str:
    """The sealed copy's associated data: the connection's id, or the abandoning state's."""
    if row.connection_id is not None:
        return str(row.connection_id)
    if row.state_id is None:  # the table's CHECK holds one of the two
        raise ValueError("revocation without an owner")
    return _state_binding(row.state_id)


def _target(row: ConnectionGrantRevocation) -> Target:
    if row.connection_id is not None:
        return Target("connection", row.connection_id)
    return Target("connection_state", row.state_id or UUID(int=0))


async def _revoke(
    tenant: TenantContext, row: ConnectionGrantRevocation, connection: Connection
) -> str:
    binding = _binding(row)
    try:
        credentials = await open_sealed(tenant.tenant_id, row.sealed, binding)
        await connector_for(connection, credentials).revoke()
    except NotSupported:
        return "not_supported"
    except EgressRefused:
        return "refused"
    except Unavailable:
        raise
    except ConnectorError:
        return "refused"
    return "revoked"


async def revoke_retired(event: OutboxEvent) -> None:
    """The outbox consumer. Raises a failure that may pass, so the relay retries, until the
    relay's last attempt: then the grant is recorded `unreachable` and the row erased."""
    raw = event.payload.get("revocation_id")
    if raw is None:
        return
    revocation_id = UUID(str(raw))
    tenant = _system(event.tenant_id)
    async with tenant_session(tenant) as session:
        row = await session.get(ConnectionGrantRevocation, revocation_id)
        found = (
            None
            if row is None or row.connection_id is None
            else await session.get(Connection, row.connection_id)
        )
    if row is None:
        return  # already answered (a replay)
    connection = _connection_of(row, found)
    if connection is None:
        result = "no_connection"
    else:
        try:
            result = await _revoke(tenant, row, connection)
        except Exception:
            if system_now() - row.created_at < GIVE_UP_AFTER:
                raise  # retried by the relay
            result = "unreachable"
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
            target=_target(row),
            after=Ref(result=RESULTS.index(result)),
        )
    _log.info("connection.grant_revoked", result=result)


SUBSCRIPTIONS = {GrantRevocationRequested.event_type: revoke_retired}
