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
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine

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
    global _engine, _relay_engine, _identity_engine
    for engine in (_engine, _relay_engine, _identity_engine):
        if engine is not None:
            await engine.dispose()
    _engine = _relay_engine = _identity_engine = None


_relay_engine: AsyncEngine | None = None


def configure_relay_engine(url: str) -> None:
    """Point the outbox relay at a database (abacus_relay role). Startup and tests."""
    global _relay_engine
    _relay_engine = _create_engine(url)


def relay_engine() -> AsyncEngine:
    """Engine for the abacus_relay role: reads and marks the outbox, nothing else (TASK-006)."""
    global _relay_engine
    if _relay_engine is None:
        url = settings().relay_database_url
        if url is None:  # settings validation makes this unreachable outside local and test
            raise RuntimeError("relay_database_url is not configured")
        _relay_engine = _create_engine(url.get_secret_value())
    return _relay_engine


_identity_engine: AsyncEngine | None = None


def configure_identity_engine(url: str) -> None:
    """Point sign-in at a database (abacus_identity role). Startup and tests."""
    global _identity_engine
    _identity_engine = _create_engine(url)


def identity_engine() -> AsyncEngine:
    """Engine for the abacus_identity role: reads users, memberships and firm names before a
    tenant is chosen, nothing else, read-only (TASK-007). Only the identity repository uses it
    (UOW-002)."""
    global _identity_engine
    if _identity_engine is None:
        url = settings().identity_database_url
        if url is None:  # settings validation makes this unreachable outside local and test
            raise RuntimeError("identity_database_url is not configured")
        _identity_engine = _create_engine(url.get_secret_value())
    return _identity_engine


def _current_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        url = settings().database_url
        if url is None:  # settings validation makes this unreachable outside local and test
            raise RuntimeError("database_url is not configured")
        _engine = _create_engine(url.get_secret_value())
    return _engine


async def _begin_tenant(conn: AsyncConnection, ctx: TenantContext) -> None:
    """Clear stale settings, then set tenant and actor for this transaction only."""
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


@asynccontextmanager
async def tenant_connection(ctx: TenantContext) -> AsyncGenerator[AsyncConnection]:
    """A tenant-scoped connection whose transaction the caller owns. Only `kernel.uow` uses it
    (UOW-002): it commits; leaving without a commit rolls back (pool reset on return)."""
    async with _current_engine().connect() as conn:
        await _begin_tenant(conn, ctx)
        yield conn


@asynccontextmanager
async def tenant_session(ctx: TenantContext) -> AsyncGenerator[AsyncSession]:
    async with _current_engine().connect() as conn:
        await _begin_tenant(conn, ctx)
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
