"""Q-05-T09 (TASK-8716; DEC-5712): the v2 tables are insert-only for the application role and a
disagreeing position blocks release until the QM owner resolves it (migrated database)."""

from __future__ import annotations

import pytest

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


async def test_ac_the_v2_tables_exist_insert_only(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    for table in ("consultation_links", "consultation_positions", "consultation_resolutions"):
        grants = await seed.rows(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee = 'abacus_app' AND table_name = $1",
            table,
        )
        privileges = {r["privilege_type"] for r in grants}
        assert "UPDATE" not in privileges and "DELETE" not in privileges
