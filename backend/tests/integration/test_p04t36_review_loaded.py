"""P-04-T36 (TASK-3247; DEC-2228) on the loaded Brightwater Hale tenant: the `review` slice loads
past Apr 13. Kevin Osei's Checkpoint 1 on the Feld 1040 is dated Apr 13, before the setup instant
that creates the firm and the return, so it replays at setup and keeps its own date (SHL-16 c, d).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale import loader, review_slice

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
TENANT = loader.TENANT


@pytest.fixture(scope="module")
def own_db(migrated_db: MigratedDatabase) -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database
    configure_engine(migrated_db.app_url)  # hand the session's database back to later tests


async def test_the_review_slice_loads_and_the_feld_checkpoints_keep_their_dates(
    own_db: Database, migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    del migrated_db
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", own_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(own_db.app_url)
    await loader.load(own_db.superuser_dsn, "2026-09-24", slices=("review",), wait=False)
    seed = Seeder(own_db.superuser_dsn)
    saved = cast(
        list[datetime] | None,
        await seed.value(
            "SELECT array_agg(created_at ORDER BY seq) FROM checkpoints "
            "WHERE tenant_id = $1 AND cause = 'manual_save'",
            TENANT,
        ),
    )
    assert saved == [at for _, _, at in review_slice.CHECKPOINTS]
