"""G-09 (ASVS 9.2.3), against the compose Postgres (which serves no TLS): a local connection
without TLS keeps working, and a DSN that asks for TLS never falls back to a plain connection."""

from __future__ import annotations

from typing import Protocol

import pytest
from sqlalchemy import text

from abacus.kernel.db import session as db_session


class Migrated(Protocol):
    app_url: str


async def test_a_local_connection_without_tls_keeps_working(migrated_db: Migrated) -> None:
    engine = db_session._create_engine(migrated_db.app_url)  # pyright: ignore[reportPrivateUsage] -- the engine factory under test
    try:
        async with engine.connect() as conn:
            plain = (
                await conn.execute(
                    text(
                        "SELECT NOT coalesce(ssl, false) FROM pg_stat_ssl "
                        "WHERE pid = pg_backend_pid()"
                    )
                )
            ).scalar_one()
        assert plain is True
    finally:
        await engine.dispose()


async def test_a_dsn_asking_for_tls_never_falls_back_to_plain(migrated_db: Migrated) -> None:
    separator = "&" if "?" in migrated_db.app_url else "?"
    engine = db_session._create_engine(  # pyright: ignore[reportPrivateUsage] -- the engine factory under test
        f"{migrated_db.app_url}{separator}sslmode=prefer"
    )
    try:
        with pytest.raises(ConnectionError, match="rejected SSL upgrade"):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()
