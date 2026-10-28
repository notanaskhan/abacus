"""G-02-T23 (TASK-1616; ADR-186; DEC-711): migration 0272, the AI policy's drafts and versions.

"up/down/up passes, every firm has a published v1 equal to its current level" (G-02-T23
acceptance). Around it: a version needs two different people; its content never changes; its
state moves forward once and only by the session's own human actor; the named approver
publishes; nothing is deleted.
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

BEFORE = "0271"  # the revision before 0272 (re-pointed with the chain at the batch merge)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _as(conn: asyncpg.Connection, tenant: uuid.UUID, kind: str, actor: str) -> None:
    await conn.execute("SELECT set_config('app.tenant_id', $1, false)", str(tenant))
    await conn.execute("SELECT set_config('app.actor_kind', $1, false)", kind)
    await conn.execute("SELECT set_config('app.actor_id', $1, false)", actor)


def test_ac_every_firm_gets_a_published_v1_at_its_level_and_the_rules_hold(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)

    async def firms() -> tuple[uuid.UUID, uuid.UUID]:
        first, second = await seed.firm(), await seed.firm()
        await seed.run("UPDATE firms SET autonomy_level = 3 WHERE tenant_id = $1", second)
        return first, second

    first, second = asyncio.run(firms())
    migrate(private_db.owner_url, "head")

    async def after() -> None:
        rows = await seed.rows(
            "SELECT tenant_id, version_no, state, carried_over, "
            "(sections->'autonomy'->>'level')::int AS level FROM autonomy_policy_versions "
            "WHERE tenant_id = ANY($1::uuid[]) ORDER BY level",
            [first, second],
        )
        assert [(r["version_no"], r["state"], r["carried_over"], r["level"]) for r in rows] == [
            (1, "published", True, 1),
            (1, "published", True, 3),
        ]
        requester, approver = uuid.uuid4(), uuid.uuid4()
        conn = await asyncpg.connect(private_db.superuser_dsn)
        try:
            await _as(conn, first, "human", str(requester))
            with pytest.raises(asyncpg.CheckViolationError):  # one person both asks and approves
                await conn.execute(
                    "INSERT INTO autonomy_policy_versions (tenant_id, version_no, sections, "
                    "effective_from, requested_by, requested_at, approver_user_id) "
                    "VALUES ($1, 2, '{}', now(), $2, now(), $2)",
                    first,
                    requester,
                )
            await conn.execute(
                "INSERT INTO autonomy_policy_versions (tenant_id, version_no, sections, "
                "effective_from, requested_by, requested_at, approver_user_id) "
                "VALUES ($1, 2, '{}', now(), $2, now(), $3)",
                first,
                requester,
                approver,
            )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):  # content is immutable
                await conn.execute(
                    "UPDATE autonomy_policy_versions SET sections = '{\"x\": 1}' "
                    "WHERE tenant_id = $1 AND version_no = 2",
                    first,
                )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):  # not the named approver
                await conn.execute(
                    "UPDATE autonomy_policy_versions SET state = 'published', decided_by = $2, "
                    "decided_at = now() WHERE tenant_id = $1 AND version_no = 2",
                    first,
                    requester,
                )
            await _as(conn, first, "agent", str(approver))
            with pytest.raises(asyncpg.InsufficientPrivilegeError):  # never an agent
                await conn.execute(
                    "UPDATE autonomy_policy_versions SET state = 'published', decided_by = $2, "
                    "decided_at = now() WHERE tenant_id = $1 AND version_no = 2",
                    first,
                    approver,
                )
            await _as(conn, first, "human", str(approver))
            await conn.execute(
                "UPDATE autonomy_policy_versions SET state = 'published', decided_by = $2, "
                "decided_at = now() WHERE tenant_id = $1 AND version_no = 2",
                first,
                approver,
            )
            with pytest.raises(asyncpg.CheckViolationError):  # nothing leaves published
                await conn.execute(
                    "UPDATE autonomy_policy_versions SET state = 'withdrawn', decided_by = $2 "
                    "WHERE tenant_id = $1 AND version_no = 2",
                    first,
                    approver,
                )
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await conn.execute(
                    "DELETE FROM autonomy_policy_versions WHERE tenant_id = $1", first
                )
        finally:
            await conn.close()

    asyncio.run(after())
    migrate(private_db.owner_url, BEFORE, down=True)
    migrate(private_db.owner_url, "head")
    assert sc.check(private_db.owner_url, private_db.app_url) == []
