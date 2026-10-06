"""Tenant-scoped database sessions (ADR-014). PROTECTED. TASK-005 design §3.

`tenant_session(ctx)` is the only way product code touches the database. It connects as
`abacus_app` (not the table owner, no BYPASSRLS), opens a transaction and sets `app.tenant_id` for
that transaction only, so row-level security confines every statement to the tenant and the setting
can never leak to the next user of a pooled connection.

It never commits. The session joins the connection's transaction in `rollback_only` mode, so
`session.commit()` is inert by design; the connection goes back to the pool at the end and the pool
rolls back whatever is open. Writes commit only through the unit of work (TASK-006), which must
own the transaction itself rather than build on this session's commit. (`conn.commit()` reached
through `session.connection()` would commit; UOW-001 forbids it outside `kernel.uow`.)

Before setting the tenant, every session `RESET`s the tenant and actor settings, so a session-level
`SET app.tenant_id` left on a pooled connection by earlier code can never carry over (TENANT-001
forbids writing that setting outside this package).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from abacus.kernel.config import settings

ActorKind = Literal["human", "agent", "system"]


@dataclass(frozen=True)
class TenantContext:
    """Who is acting, and for which firm. Built from a membership on every request (TASK-007)."""

    tenant_id: UUID
    actor_kind: ActorKind
    actor_id: str


_engine: AsyncEngine | None = None


def _create_engine(url: str) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_reset_on_return="rollback",
        connect_args={
            "server_settings": {
                "application_name": "abacus",
                "statement_timeout": str(settings().database_statement_timeout_ms),
            }
        },
    )


def configure_engine(url: str) -> None:
    """Point the process at a database (startup and tests). Replaces any existing engine."""
    global _engine
    _engine = _create_engine(url)


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def _current_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = settings().database_url
        if url is None:  # settings validation makes this unreachable outside local and test
            raise RuntimeError("database_url is not configured")
        _engine = _create_engine(url.get_secret_value())
    return _engine


@asynccontextmanager
async def tenant_session(ctx: TenantContext) -> AsyncGenerator[AsyncSession]:
    async with _current_engine().connect() as conn:
        # Clear anything a previous user of this pooled connection set at session level.
        await conn.execute(text("RESET app.tenant_id"))
        await conn.execute(text("RESET app.actor_kind"))
        await conn.execute(text("RESET app.actor_id"))
        # Transaction-local (`true`): gone when this transaction ends, whatever happens.
        await conn.execute(
            text(
                "SELECT set_config('app.tenant_id', :tenant, true), "
                "set_config('app.actor_kind', :kind, true), "
                "set_config('app.actor_id', :actor, true)"
            ),
            {"tenant": str(ctx.tenant_id), "kind": ctx.actor_kind, "actor": ctx.actor_id},
        )
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            autoflush=True,
            join_transaction_mode="rollback_only",
        )
        try:
            yield session
        finally:
            await session.close()
    # Leaving `connect()` returns the connection to the pool, which rolls the transaction back.
