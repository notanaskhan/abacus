"""Who reads which inbox thread (N-01-T08; DEC-75; ADR-210 clause 3; DEC-20; DEC-819).

- An **unmatched** thread (no client yet) is the intake scope's only: a person on an intake team
  reads it by sender and subject; anyone else gets 404, as if it did not exist.
- A **matched** thread is read as its client is: walled or unknown answers 404 (DEC-43), then
  `inbox.read` on the client; the intake scope reads it too.
The thread read models (N-01-T13) list and open threads through these checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.identity.api import AuthContext, Resource, authorise, in_intake_scope
from abacus.modules.organisations.api import readable_client

READ = "inbox.read"


@dataclass(frozen=True)
class ThreadHeader:
    """What the intake scope sees of a thread: sender and subject, never a body."""

    id: UUID
    client_id: UUID | None
    sender_display: str
    subject_display: str
    last_received_at: datetime


_THREAD = text(
    "SELECT id, client_id, sender_display, subject_display, last_received_at "
    "FROM inbox_threads WHERE id = :id"
)
_UNMATCHED = text(
    "SELECT id, client_id, sender_display, subject_display, last_received_at "
    "FROM inbox_threads WHERE client_id IS NULL ORDER BY last_received_at DESC, id LIMIT :limit"
)


async def intake_member(ctx: AuthContext) -> bool:
    """A firm person on an intake team now (a client principal never is)."""
    return not ctx.client and await in_intake_scope(ctx.tenant, ctx.user_id)


async def unmatched_threads(ctx: AuthContext, limit: int = 50) -> list[ThreadHeader]:
    """The unmatched threads, newest first, for the intake scope only (404 for anyone else).
    LIST_EXEMPT: the intake scope reads every unmatched thread of the firm (DEC-75)."""
    if not await intake_member(ctx):
        raise NotFound("inbox_thread")
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_UNMATCHED, {"limit": limit})).all()
    return [ThreadHeader(*row) for row in rows]


async def readable_thread(ctx: AuthContext, thread_id: UUID) -> ThreadHeader:
    """One thread's header, or 404 when the caller may not know it exists."""
    if ctx.client:
        raise NotFound("inbox_thread")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_THREAD, {"id": thread_id})).one_or_none()
    if row is None:
        raise NotFound("inbox_thread")
    header = ThreadHeader(*row)
    if header.client_id is None:
        if not await in_intake_scope(ctx.tenant, ctx.user_id):
            raise NotFound("inbox_thread")
        return header
    await readable_client(ctx, header.client_id)  # walled or unknown: 404 (DEC-43)
    if not await in_intake_scope(ctx.tenant, ctx.user_id):
        await authorise(ctx, READ, Resource.client(ctx.tenant_id, header.client_id))
    return header
