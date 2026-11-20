"""Q-03-T353 (TASK-8805): the contract step drops `connections_one_live_ledger`; the coverage
index still holds one live ledger per entity (A-09 OQ-9)."""

from __future__ import annotations

import asyncpg
import pytest

from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def test_old_index_dropped_coverage_index_kept(migrated_db: MigratedDatabase) -> None:
    conn = await asyncpg.connect(_dsn(migrated_db.owner_url))
    try:
        rows = await conn.fetch(
            "SELECT indexname, indexdef FROM pg_indexes WHERE indexname IN "
            "('connections_one_live_ledger', 'connection_coverage_one_live')"
        )
    finally:
        await conn.close()
    names = {r["indexname"]: r["indexdef"] for r in rows}
    assert "connections_one_live_ledger" not in names
    assert "UNIQUE" in names["connection_coverage_one_live"]
    assert "live" in names["connection_coverage_one_live"]
