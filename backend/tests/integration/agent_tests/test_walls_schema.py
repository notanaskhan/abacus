"""AC-20 (database): migration 0012, `ethical_walls` (TASK-016 interface contract, "Database").

Forced row-level security, one active wall per (tenant, user, client), column grants for the app,
the forward-only trigger, the CHECK and the foreign keys, and a downgrade that refuses while walls
exist. Setup rows are written as the superuser; grant and row-level-security checks run as
`abacus_app` through `tenant_session`.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.kernel.db import TenantContext, tenant_session
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .support import Person, Seeder

INSERT = (
    "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
    "VALUES ($1, $2, $3, $4) RETURNING id"
)
APP_INSERT = (
    "INSERT INTO ethical_walls (id, tenant_id, user_id, client_id, created_by) "
    "VALUES (:id, :t, :u, :c, :by)"
)


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    admin: Person
    member: Person
    client_id: uuid.UUID

    @property
    def ctx(self) -> TenantContext:
        return TenantContext(self.tenant_id, "human", str(self.admin.user_id))


async def _firm(seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id)
    member = await seed.person(tenant_id)
    entity_id = await seed.entity(tenant_id)
    client_id = cast(
        uuid.UUID,
        await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity_id),
    )
    return Firm(tenant_id, admin, member, client_id)


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    return await _firm(seed)


async def _wall(seed: Seeder, firm: Firm, *, user: Person | None = None) -> uuid.UUID:
    who = user or firm.member
    return cast(
        uuid.UUID,
        await seed.value(INSERT, firm.tenant_id, who.user_id, firm.client_id, firm.admin.user_id),
    )


async def _status(seed: Seeder, wall_id: uuid.UUID) -> str:
    return str(await seed.value("SELECT status FROM ethical_walls WHERE id = $1", wall_id))


# --- forced row-level security -------------------------------------------------------------------


async def test_ac20_row_level_security_is_enabled_and_forced(seed: Seeder) -> None:
    [row] = await seed.rows(
        "SELECT c.relrowsecurity, c.relforcerowsecurity, pg_get_userbyid(c.relowner) AS owner "
        "FROM pg_class c WHERE c.relname = 'ethical_walls' AND c.relkind = 'r'"
    )
    assert row["relrowsecurity"] is True
    assert row["relforcerowsecurity"] is True
    assert row["owner"] != "abacus_app"


async def test_ac20_the_app_sees_only_its_own_firms_walls(seed: Seeder, firm: Firm) -> None:
    mine = await _wall(seed, firm)
    other = await _firm(seed)
    theirs = await _wall(seed, other)
    async with tenant_session(firm.ctx) as session:
        found = (await session.execute(text("SELECT id FROM ethical_walls"))).scalars().all()
    assert mine in found
    assert theirs not in found


async def test_ac20_the_app_cannot_write_a_wall_into_another_firm(
    seed: Seeder, firm: Firm
) -> None:
    other = await _firm(seed)
    with pytest.raises(DBAPIError) as caught:
        async with tenant_session(firm.ctx) as session:
            await session.execute(
                text(APP_INSERT),
                {
                    "id": uuid.uuid4(),
                    "t": other.tenant_id,
                    "u": other.member.user_id,
                    "c": other.client_id,
                    "by": other.admin.user_id,
                },
            )
    assert "row-level security" in str(caught.value).lower()


async def test_ac20_the_app_cannot_remove_another_firms_wall(seed: Seeder, firm: Firm) -> None:
    other = await _firm(seed)
    theirs = await _wall(seed, other)
    async with tenant_session(firm.ctx) as session:
        result = await session.execute(
            text(
                "UPDATE ethical_walls SET status = 'removed', removed_by = :by, "
                "removed_at = now() WHERE id = :id RETURNING id"
            ),
            {"id": theirs, "by": firm.admin.user_id},
        )
        assert result.all() == []  # row-level security hides it: nothing was updated
    assert await _status(seed, theirs) == "active"


# --- grants: insert some columns, update the status columns only, no delete ----------------------

INSERTABLE = {"id", "tenant_id", "user_id", "client_id", "created_by"}
UPDATABLE = {"status", "removed_by", "removed_at"}
COLUMNS = [
    "id",
    "tenant_id",
    "user_id",
    "client_id",
    "status",
    "created_by",
    "created_at",
    "removed_by",
    "removed_at",
]


@pytest.mark.parametrize("name", COLUMNS)
async def test_ac20_the_app_may_insert_only_the_documented_columns(
    seed: Seeder, name: str
) -> None:
    allowed = await seed.value(
        "SELECT has_column_privilege('abacus_app', 'ethical_walls', $1, 'INSERT')", name
    )
    assert allowed is (name in INSERTABLE)


@pytest.mark.parametrize("name", COLUMNS)
async def test_ac20_the_app_may_update_only_the_status_columns(seed: Seeder, name: str) -> None:
    allowed = await seed.value(
        "SELECT has_column_privilege('abacus_app', 'ethical_walls', $1, 'UPDATE')", name
    )
    assert allowed is (name in UPDATABLE)


@pytest.mark.parametrize("privilege", ["DELETE", "TRUNCATE"])
async def test_ac20_the_app_cannot_delete_or_truncate_walls(seed: Seeder, privilege: str) -> None:
    allowed = await seed.value(
        "SELECT has_table_privilege('abacus_app', 'ethical_walls', $1)", privilege
    )
    assert allowed is False


async def test_ac20_the_app_cannot_delete_a_wall(seed: Seeder, firm: Firm) -> None:
    wall_id = await _wall(seed, firm)
    with pytest.raises(DBAPIError) as caught:
        async with tenant_session(firm.ctx) as session:
            await session.execute(
                text("DELETE FROM ethical_walls WHERE id = :id"), {"id": wall_id}
            )
    assert "permission denied" in str(caught.value).lower()
    assert await _status(seed, wall_id) == "active"


async def test_ac20_the_app_can_insert_and_then_remove_a_wall(firm: Firm) -> None:
    wall_id = uuid.uuid4()
    async with tenant_session(firm.ctx) as session:
        await session.execute(
            text(APP_INSERT),
            {
                "id": wall_id,
                "t": firm.tenant_id,
                "u": firm.member.user_id,
                "c": firm.client_id,
                "by": firm.admin.user_id,
            },
        )
        fresh = (
            await session.execute(
                text("SELECT status, removed_by, removed_at FROM ethical_walls WHERE id = :id"),
                {"id": wall_id},
            )
        ).one()
        assert tuple(fresh) == ("active", None, None)
        removed = (
            await session.execute(
                text(
                    "UPDATE ethical_walls SET status = 'removed', removed_by = :by, "
                    "removed_at = now() WHERE id = :id RETURNING status, removed_by"
                ),
                {"id": wall_id, "by": firm.admin.user_id},
            )
        ).one()
        assert tuple(removed) == ("removed", firm.admin.user_id)


async def test_ac20_the_app_cannot_set_status_on_insert(seed: Seeder, firm: Firm) -> None:
    with pytest.raises(DBAPIError) as caught:
        async with tenant_session(firm.ctx) as session:
            await session.execute(
                text(
                    "INSERT INTO ethical_walls "
                    "(tenant_id, user_id, client_id, created_by, status) "
                    "VALUES (:t, :u, :c, :by, 'removed')"
                ),
                {
                    "t": firm.tenant_id,
                    "u": firm.member.user_id,
                    "c": firm.client_id,
                    "by": firm.admin.user_id,
                },
            )
    assert "permission denied" in str(caught.value).lower()


APP_UPDATES = {
    "user_id": "UPDATE ethical_walls SET user_id = :v WHERE id = :id",
    "client_id": "UPDATE ethical_walls SET client_id = :v WHERE id = :id",
    "created_by": "UPDATE ethical_walls SET created_by = :v WHERE id = :id",
    "created_at": "UPDATE ethical_walls SET created_at = :v WHERE id = :id",
}


@pytest.mark.parametrize("column", sorted(APP_UPDATES))
async def test_ac20_the_app_cannot_update_identity_columns(
    seed: Seeder, firm: Firm, column: str
) -> None:
    wall_id = await _wall(seed, firm)
    values: dict[str, object] = {
        "user_id": firm.admin.user_id,
        "client_id": uuid.uuid4(),
        "created_by": firm.member.user_id,
        "created_at": datetime(2020, 1, 1, tzinfo=UTC),
    }
    with pytest.raises(DBAPIError) as caught:
        async with tenant_session(firm.ctx) as session:
            await session.execute(text(APP_UPDATES[column]), {"v": values[column], "id": wall_id})
    assert "permission denied" in str(caught.value).lower()


# --- one active wall per (tenant, user, client) --------------------------------------------------


async def test_ac20_two_active_walls_for_the_same_pair_are_a_unique_violation(
    seed: Seeder, firm: Firm
) -> None:
    await _wall(seed, firm)
    with pytest.raises(asyncpg.UniqueViolationError):
        await _wall(seed, firm)


async def test_ac20_a_removed_wall_does_not_block_a_new_active_one(
    seed: Seeder, firm: Firm
) -> None:
    first = await _wall(seed, firm)
    await seed.run(
        "UPDATE ethical_walls SET status = 'removed', removed_by = $2, removed_at = now() "
        "WHERE id = $1",
        first,
        firm.admin.user_id,
    )
    second = await _wall(seed, firm)
    assert await _status(seed, second) == "active"
    await seed.run(
        "UPDATE ethical_walls SET status = 'removed', removed_by = $2, removed_at = now() "
        "WHERE id = $1",
        second,
        firm.admin.user_id,
    )
    third = await _wall(seed, firm)  # many removed walls, one active
    assert await _status(seed, third) == "active"


async def test_ac20_the_same_pair_in_different_firms_or_other_pairs_is_fine(
    seed: Seeder, firm: Firm
) -> None:
    await _wall(seed, firm)
    await _wall(seed, firm, user=firm.admin)
    other = await _firm(seed)
    await _wall(seed, other)


# --- CHECK: removed <=> removed_at and removed_by set --------------------------------------------


REMOVED_INCOMPLETE = [
    "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by, status) "
    "VALUES ($1, $2, $3, $4, 'removed')",
    "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by, status, removed_at) "
    "VALUES ($1, $2, $3, $4, 'removed', now())",
    "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by, status, removed_by) "
    "VALUES ($1, $2, $3, $4, 'removed', $4)",
]


@pytest.mark.parametrize("sql", REMOVED_INCOMPLETE)
async def test_ac20_removed_without_who_and_when_is_a_check_violation(
    seed: Seeder, firm: Firm, sql: str
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            sql, firm.tenant_id, firm.member.user_id, firm.client_id, firm.admin.user_id
        )


async def test_ac20_active_with_a_removal_recorded_is_a_check_violation(
    seed: Seeder, firm: Firm
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by, removed_by, "
            "removed_at) VALUES ($1, $2, $3, $4, $4, now())",
            firm.tenant_id,
            firm.member.user_id,
            firm.client_id,
            firm.admin.user_id,
        )


async def test_ac20_an_unknown_status_is_a_check_violation(seed: Seeder, firm: Firm) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by, status) "
            "VALUES ($1, $2, $3, $4, 'paused')",
            firm.tenant_id,
            firm.member.user_id,
            firm.client_id,
            firm.admin.user_id,
        )


# --- foreign keys: members and clients of the same firm ------------------------------------------


async def test_ac20_the_user_must_be_a_member_of_the_firm(seed: Seeder, firm: Firm) -> None:
    other = await _firm(seed)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.value(
            INSERT, firm.tenant_id, other.member.user_id, firm.client_id, firm.admin.user_id
        )


async def test_ac20_the_creator_must_be_a_member_of_the_firm(seed: Seeder, firm: Firm) -> None:
    other = await _firm(seed)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.value(
            INSERT, firm.tenant_id, firm.member.user_id, firm.client_id, other.admin.user_id
        )


async def test_ac20_the_client_must_be_in_the_firm(seed: Seeder, firm: Firm) -> None:
    other = await _firm(seed)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.value(
            INSERT, firm.tenant_id, firm.member.user_id, other.client_id, firm.admin.user_id
        )
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.value(
            INSERT, firm.tenant_id, firm.member.user_id, uuid.uuid4(), firm.admin.user_id
        )


async def test_ac20_the_remover_must_be_a_member_of_the_firm(seed: Seeder, firm: Firm) -> None:
    other = await _firm(seed)
    wall_id = await _wall(seed, firm)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run(
            "UPDATE ethical_walls SET status = 'removed', removed_by = $2, removed_at = now() "
            "WHERE id = $1",
            wall_id,
            other.admin.user_id,
        )


# --- the forward-only trigger --------------------------------------------------------------------


async def test_ac20_an_active_wall_may_be_removed(seed: Seeder, firm: Firm) -> None:
    wall_id = await _wall(seed, firm)
    await seed.run(
        "UPDATE ethical_walls SET status = 'removed', removed_by = $2, removed_at = now() "
        "WHERE id = $1",
        wall_id,
        firm.admin.user_id,
    )
    assert await _status(seed, wall_id) == "removed"


async def test_ac20_a_removed_wall_cannot_change_even_for_the_superuser(
    seed: Seeder, firm: Firm
) -> None:
    wall_id = await _wall(seed, firm)
    await seed.run(
        "UPDATE ethical_walls SET status = 'removed', removed_by = $2, removed_at = now() "
        "WHERE id = $1",
        wall_id,
        firm.admin.user_id,
    )
    for sql in (
        "UPDATE ethical_walls SET status = 'active', removed_by = NULL, removed_at = NULL "
        "WHERE id = $1",
        "UPDATE ethical_walls SET removed_at = now() WHERE id = $1",
        "UPDATE ethical_walls SET status = 'removed' WHERE id = $1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run(sql, wall_id)
    assert await _status(seed, wall_id) == "removed"


SUPERUSER_UPDATES = {
    "user_id": "UPDATE ethical_walls SET status = 'removed', removed_by = $2, "
    "removed_at = now(), user_id = $3 WHERE id = $1",
    "client_id": "UPDATE ethical_walls SET status = 'removed', removed_by = $2, "
    "removed_at = now(), client_id = $3 WHERE id = $1",
    "created_by": "UPDATE ethical_walls SET status = 'removed', removed_by = $2, "
    "removed_at = now(), created_by = $3 WHERE id = $1",
    "created_at": "UPDATE ethical_walls SET status = 'removed', removed_by = $2, "
    "removed_at = now(), created_at = $3 WHERE id = $1",
}


@pytest.mark.parametrize("column", sorted(SUPERUSER_UPDATES))
async def test_ac20_identity_columns_are_immutable_even_for_the_superuser(
    seed: Seeder, firm: Firm, column: str
) -> None:
    wall_id = await _wall(seed, firm)
    other_client = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'x') RETURNING id", firm.tenant_id
        ),
    )
    values: dict[str, object] = {
        "user_id": firm.admin.user_id,
        "client_id": other_client,
        "created_by": firm.member.user_id,
        "created_at": datetime(2020, 1, 1, tzinfo=UTC),
    }
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(SUPERUSER_UPDATES[column], wall_id, firm.admin.user_id, values[column])
    assert await _status(seed, wall_id) == "active"


async def test_ac20_an_update_must_remove_the_wall_and_nothing_else(
    seed: Seeder, firm: Firm
) -> None:
    wall_id = await _wall(seed, firm)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(
            "UPDATE ethical_walls SET removed_by = $2 WHERE id = $1", wall_id, firm.admin.user_id
        )
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("UPDATE ethical_walls SET status = 'active' WHERE id = $1", wall_id)
    assert await _status(seed, wall_id) == "active"


async def test_ac20_the_app_cannot_remove_a_wall_twice(seed: Seeder, firm: Firm) -> None:
    wall_id = await _wall(seed, firm)
    remove = text(
        "UPDATE ethical_walls SET status = 'removed', removed_by = :by, removed_at = now() "
        "WHERE id = :id"
    )
    async with tenant_session(firm.ctx) as session:
        await session.execute(remove, {"id": wall_id, "by": firm.admin.user_id})
        with pytest.raises(DBAPIError):
            await session.execute(remove, {"id": wall_id, "by": firm.admin.user_id})


# --- downgrade -----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _script_head() -> str:
    """The newest migration in the repository (later tasks add migrations after 0012)."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(sc.BACKEND / "alembic.ini"))
    return str(ScriptDirectory.from_config(config).get_current_head())


def _revision(database: sc.Database) -> str:
    return str(
        asyncio.run(
            Seeder(database.superuser_dsn).value("SELECT version_num FROM alembic_version")
        )
    )


def test_ac20_downgrading_0012_is_refused_while_walls_exist(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def setup() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        firm = await _firm(seed)
        wall_id = await _wall(seed, firm)
        return wall_id, firm.admin.user_id, firm.tenant_id

    wall_id, admin_id, _tenant = asyncio.run(setup())
    # TASK-018b: head is 0013 now; step down to 0012 first (0013 holds no walls).
    migrate(private_db.owner_url, "0012", down=True)
    assert _revision(private_db) == "0012"
    with pytest.raises(DBAPIError, match="refusing to downgrade"):
        migrate(private_db.owner_url, "0011", down=True)
    assert _revision(private_db) == "0012"
    # A removed wall is still a record of who was walled: it refuses too.
    asyncio.run(
        seed.run(
            "UPDATE ethical_walls SET status = 'removed', removed_by = $2, removed_at = now() "
            "WHERE id = $1",
            wall_id,
            admin_id,
        )
    )
    with pytest.raises(DBAPIError, match="refusing to downgrade"):
        migrate(private_db.owner_url, "0011", down=True)
    assert _revision(private_db) == "0012"
    assert asyncio.run(seed.value("SELECT count(*) FROM ethical_walls")) == 1


def test_ac20_downgrading_0012_with_no_walls_drops_the_table_and_upgrading_restores_it(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    asyncio.run(seed.run("DELETE FROM ethical_walls"))
    migrate(private_db.owner_url, "0011", down=True)
    assert _revision(private_db) == "0011"
    assert asyncio.run(seed.value("SELECT to_regclass('public.ethical_walls')")) is None
    assert (
        asyncio.run(seed.value("SELECT count(*) FROM pg_proc WHERE proname LIKE 'ethical_walls%'"))
        == 0
    )
    migrate(private_db.owner_url, "head")
    assert _revision(private_db) == _script_head()  # whatever migration is newest
    assert asyncio.run(seed.value("SELECT to_regclass('public.ethical_walls')")) is not None
