"""Q-03-T353 (TASK-8805): the contract step drops `connections_one_live_ledger`; the coverage
index still holds one live ledger per entity (A-09 OQ-9)."""

from __future__ import annotations

import pytest

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def test_old_index_dropped_coverage_index_kept(migrated_db: MigratedDatabase) -> None:
    seeder = Seeder(_dsn(migrated_db.owner_url))
    old = await seeder.value(
        "SELECT count(*) FROM pg_indexes WHERE indexname = 'connections_one_live_ledger'"
    )
    kept = str(
        await seeder.value(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'connection_coverage_one_live'"
        )
    )
    assert old == 0
    assert "UNIQUE" in kept
    assert "live" in kept
