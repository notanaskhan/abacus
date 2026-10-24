"""Alembic environment (ADR-015, ADR-091). PROTECTED. TASK-005 design §4.

Connects as `abacus_owner` (ABACUS_MIGRATIONS_DATABASE_URL, or `-x url=...`), never as the app
role, and bounds every migration session with lock and statement timeouts so a migration can't
stall production traffic. Online mode only: every migration is reviewed as SQL in its own file.
"""

from __future__ import annotations

import asyncio

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from abacus.kernel.clock import check_startup as check_clock
from abacus.kernel.config import LOCAL_STACK, settings
from abacus.kernel.db_tls import database_tls

LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "60s"


def _url() -> str:
    check_clock()  # F-04-T02: the migration job refuses a demo clock in production too
    override = context.get_x_argument(as_dictionary=True).get("url")
    if override:
        return override
    url = settings().migrations_database_url
    if url is None:
        raise RuntimeError("ABACUS_MIGRATIONS_DATABASE_URL is not set")
    return url.get_secret_value()


def _migrate(connection: Connection) -> None:
    # Timeouts arrive as connection parameters (see _run), so nothing here opens a transaction
    # before Alembic does: each migration really gets its own transaction, and a failure leaves
    # earlier migrations applied with their locks already released.
    context.configure(connection=connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run() -> None:
    # G-09: the owner's connection verifies the server's certificate too (`kernel.db_tls`).
    config = settings()
    tls = database_tls(
        _url(), local=config.environment in LOCAL_STACK, ca_file=config.database_ca_file
    )
    engine = create_async_engine(
        tls.url,
        connect_args={
            "ssl": tls.ssl,
            "server_settings": {
                "lock_timeout": LOCK_TIMEOUT,
                "statement_timeout": STATEMENT_TIMEOUT,
                "application_name": "abacus-migrations",
            },
        },
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline (SQL script) mode is not supported; run migrations online")
asyncio.run(_run())
