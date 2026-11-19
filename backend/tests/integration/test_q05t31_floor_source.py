"""Q-05-T31 (TASK-8712; DEC-5708): the retention floor's source switch on a migrated database.
Before the switch the floor reads Q-02's published `retention_floors`; the switch to
`retention_minimums` is refused while any floor differs (`floors_differ`); with equal rows it
switches and the floor readers read the set."""

from __future__ import annotations

import json

import pytest

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


async def test_ac_the_switch_waits_for_equal_floors(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    source = await seed.value("SELECT retention_floor_source()")
    assert source == "retention_floors"
    differs = await seed.rows("SELECT * FROM retention_floor_differences()")
    if differs:
        with pytest.raises(Exception, match="floors_differ"):
            await seed.value(
                "SELECT platform_setting_put('retention_floor_source', $1::jsonb, 0, "
                "'rowan', 'Q-05-T31 switch rehearsal')",
                json.dumps({"source": "retention_minimums"}),
            )
    else:
        version = await seed.value(
            "SELECT platform_setting_put('retention_floor_source', $1::jsonb, 0, "
            "'rowan', 'Q-05-T31 switch rehearsal')",
            json.dumps({"source": "retention_minimums"}),
        )
        assert version == 1
        assert await seed.value("SELECT retention_floor_source()") == "retention_minimums"
