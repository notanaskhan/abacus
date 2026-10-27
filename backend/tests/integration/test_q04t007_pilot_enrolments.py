"""Q-04-T007 (TASK-1621; DEC-716): migration 0276, pilot enrolments and metric snapshots.

"schema_check passes up-down-up, the snapshot key is UNIQUE NULLS NOT DISTINCT so a NULL subject
cannot duplicate, the app role cannot update or delete a snapshot, and an enrolment cannot reach
system_of_record without a named confirming person" (Q-04-T007 acceptance).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0275"


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def test_ac_snapshots_once_insert_only_and_a_named_confirmer(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def run() -> None:
        tenant = await seed.firm()
        person = await seed.person(tenant)
        entity = await seed.entity(tenant)
        engagement = await seed.engagement(tenant, entity, person.user_id)
        work_item = await seed.value(
            "SELECT id FROM work_items WHERE tenant_id = $1 AND engagement_id = $2 LIMIT 1",
            tenant,
            engagement,
        )
        if work_item is None:
            pytest.skip("the seeded engagement has no work item")
        enrolment = await seed.value(
            "INSERT INTO pilot_enrolments (tenant_id, work_item_id, window_start, window_end, "
            "created_by) VALUES ($1, $2, '2027-06-01', '2027-07-12', $3) RETURNING id",
            tenant,
            work_item,
            person.user_id,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "UPDATE pilot_enrolments SET mode = 'system_of_record' WHERE id = $1", enrolment
            )
        snap = (
            "INSERT INTO pilot_metric_snapshots (tenant_id, enrolment_id, metric_key, "
            "period_start, period_end, value) VALUES ($1, $2, 'turnaround.days', "
            "'2027-06-01', '2027-06-07', 3.5)"
        )
        await seed.run(snap, tenant, enrolment)
        with pytest.raises(asyncpg.UniqueViolationError):
            await seed.run(snap, tenant, enrolment)
        app = await asyncpg.connect(sc._dsn(private_db.app_url))  # pyright: ignore[reportPrivateUsage]
        try:
            await app.execute("SELECT set_config('app.tenant_id', $1, false)", str(tenant))
            for statement in (
                "UPDATE pilot_metric_snapshots SET value = 1",
                "DELETE FROM pilot_metric_snapshots",
            ):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await app.execute(statement)
        finally:
            await app.close()
        assert uuid.UUID(str(enrolment))

    asyncio.run(run())
    migrate(private_db.owner_url, BEFORE, down=True)
    migrate(private_db.owner_url, "head")
    assert sc.check(private_db.owner_url, private_db.app_url) == []
