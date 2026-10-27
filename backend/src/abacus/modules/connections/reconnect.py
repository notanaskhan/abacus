"""Reconnect requests: the firm asks the client to reconnect a connection (A-02-T23; TASK-1471;
SPEC-333 AC-44, A-02 AC-11.1; DEC-611).

- `request_reconnect`: one unit of work. The engagement the caller was authorised on is locked
  and `connection.reconnect_request` checked again on it; the connection is locked and must be
  live and of that engagement's entity (otherwise 404, as if absent). At most one request is open
  per connection (0195's partial unique index): a second ask answers the open request with
  `created=False` and records nothing. A new one is audited `connection.reconnect_requested`
  (identifiers only). The email to the entity's owners is the caller's (integrations sends the
  firm's Reconnect request template through communications), for a new request only.
- `reconnect_todo_count`: POR-02's reconnect to-do, the open requests on live connections of
  the entities of the engagements given, counted only where the person holds `connection.read`
  (the client Owner, `scope_only`; a contributor has nothing to reconnect). It clears when the
  reconnect completes (`complete_entity` fulfils open requests, A-02-T16).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.models import ReconnectRequest
from abacus.modules.connections.repository import (
    LIVE,
    insert_reconnect_request,
    lock_connection,
    open_reconnect_request,
    open_requests_on_entities,
)
from abacus.modules.engagements.api import EngagementRef, get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, allowed_actions, authorise

ACTION = "connection.reconnect_request"


@dataclass(frozen=True)
class ReconnectRequested:
    id: UUID
    connection_id: UUID
    provider: str
    engagement_id: UUID
    client_entity_id: UUID
    requested_by_user_id: UUID
    requested_at: datetime
    created: bool  # False: the connection's open request, answered again; nothing was sent


class _Open(Exception):
    """The connection already has an open request: nothing was written, so the unit of work is
    left without its commit (it would refuse a commit with no audit event)."""

    def __init__(self, found: ReconnectRequested) -> None:
        super().__init__("open")
        self.found = found


def _requested(
    row: ReconnectRequest, provider: str, ref: EngagementRef, *, created: bool
) -> ReconnectRequested:
    return ReconnectRequested(
        row.id,
        row.connection_id,
        provider,
        row.engagement_id,
        ref.client_entity_id,
        row.requested_by_user_id,
        row.created_at,
        created,
    )


async def request_reconnect(
    ctx: AuthContext, ref: EngagementRef, connection_id: UUID
) -> ReconnectRequested:
    """AC-11.1: one open reconnect request per connection, asked on `ref` (an engagement of the
    connection's entity on which the caller holds `connection.reconnect_request`)."""
    try:
        async with uow(ctx.tenant) as tx:
            locked = await lock_ref(tx, ref.id)
            await authorise(ctx, ACTION, locked.resource())
            connection = await lock_connection(tx.session, connection_id)
            if (
                connection is None
                or connection.client_entity_id != locked.client_entity_id
                or connection.status not in LIVE
            ):
                raise NotFound("connection")
            row = await insert_reconnect_request(
                tx.session,
                tenant_id=ctx.tenant_id,
                connection_id=connection.id,
                requested_by_user_id=ctx.user_id,
                engagement_id=locked.id,
            )
            if row is None:
                found = await open_reconnect_request(tx.session, connection.id)
                if found is None:  # fulfilled between the two statements: ask again
                    raise NotFound("reconnect_request")
                raise _Open(_requested(found, connection.provider, locked, created=False))
            tx.record(
                "connection.reconnect_requested",
                target=Target("connection", connection.id),
                after=Ref(engagement_id=locked.id, reconnect_request_id=row.id),
            )
            return _requested(row, connection.provider, locked, created=True)
    except _Open as already:
        return already.found


async def reconnect_todo_count(ctx: AuthContext, engagement_ids: Sequence[UUID]) -> int:
    """POR-02's reconnect to-do: open requests on the live connections of these engagements'
    entities, where the person holds `connection.read` on the engagement."""
    entities: set[UUID] = set()
    for engagement_id in engagement_ids:
        ref = await get_ref(ctx, engagement_id)
        if "connection.read" in await allowed_actions(ctx, ref.resource(), ["connection.read"]):
            entities.add(ref.client_entity_id)
    if not entities:
        return 0
    async with tenant_session(ctx.tenant) as session:
        return await open_requests_on_entities(session, sorted(entities, key=str))


__all__ = ["ReconnectRequested", "reconnect_todo_count", "request_reconnect"]
