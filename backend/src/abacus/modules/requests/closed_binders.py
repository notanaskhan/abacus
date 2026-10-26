"""A closed binder takes no client act (ED-118, DEC-461).

DEC-333 reads a binder closed after it was published as read-only to the client: no
`allowed_actions` on the binder, its rows or POR-04. The writes agree here. Every client write on
the binder or one of its requests (Ignore and its Undo, Mark as Done and its Undo, an upload
intent, an upload or its unlock, a withdrawal, a comment, a SPEC-042 response) answers
409 `binder_closed` with the binder's id, after the caller's own authorisation, and writes
nothing. A binder that was not published when it closed was never the client's to read: 404, as
its reads answer (DEC-333 security review (1)). The firm's own acts are not changed here. A
drop keeps answering 404 on any binder that is not Published (R-01-T15's INV-4 case).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.modules.identity.api import Actor, AuthContext
from abacus.modules.requests.models import RequestList
from abacus.modules.requests.repository import get_binder, get_request_item


class BinderClosed(DomainConflict):
    """The binder is closed: the client reads it and acts on nothing in it (DEC-461)."""

    code = "binder_closed"


def _client(ctx: Actor) -> bool:
    return isinstance(ctx, AuthContext) and ctx.client


def _published_when_closed(binder: RequestList) -> bool:
    """DEC-333 (AC-7): published, and not unpublished since."""
    return binder.published_at is not None and (
        binder.unpublished_at is None or binder.unpublished_at < binder.published_at
    )


def refuse_closed(
    ctx: Actor, binder: RequestList | None, *, missing: str = "request_item"
) -> None:
    """For a client, 409 `binder_closed` on a closed binder the client reads, 404 on one it never
    read; nothing for anyone else or an open binder."""
    if binder is None or binder.status != "closed" or not _client(ctx):
        return
    if not _published_when_closed(binder):
        raise NotFound(missing)
    raise BinderClosed(facts={"binder_id": str(binder.id)})


async def refuse_closed_item_in(session: AsyncSession, ctx: Actor, item_id: UUID) -> None:
    """`refuse_closed` for the request's binder, in the caller's session or unit of work."""
    if not _client(ctx):
        return
    item = await get_request_item(session, item_id)
    if item is None:
        return  # the caller answers a missing request
    refuse_closed(ctx, await get_binder(session, item.request_list_id))


async def refuse_closed_item(ctx: Actor, item_id: UUID) -> None:
    """`refuse_closed` for the request's binder, read in a session of its own (a check before a
    body is read; the unit of work checks again)."""
    if not _client(ctx):
        return
    async with tenant_session(ctx.tenant) as session:
        await refuse_closed_item_in(session, ctx, item_id)
