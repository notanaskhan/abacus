"""Alembic environment (ADR-015, ADR-091). PROTECTED. TASK-005 design §4.

Connects as `abacus_owner` (ABACUS_MIGRATIONS_DATABASE_URL, or `-x url=...`), never as the app
role, and bounds every migration session with lock and statement timeouts so a migration can't
stall production traffic. Online mode only: every migration is reviewed as SQL in its own file.
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import create_async_engine

from abacus.kernel.config import settings

LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "60s"


def _url() -> str:
    override = context.get_x_argument(as_dictionary=True).get("url")
    if override:
        return override
    url = settings().migrations_database_url
    if url is None:
        raise RuntimeError("ABACUS_MIGRATIONS_DATABASE_URL is not set")
    return url.get_secret_value()


def _migrate(connection: Connection) -> None:
    connection.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
    connection.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'"))
    context.configure(connection=connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run() -> None:
    engine = create_async_engine(_url())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_migrate)
            await connection.commit()
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline (SQL script) mode is not supported; run migrations online")
asyncio.run(_run())
