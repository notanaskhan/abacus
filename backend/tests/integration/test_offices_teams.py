"""F-03-T23 against Postgres: "Brightwater Hale's three offices and 46 memberships are
representable with levels" (blueprint 01 §9: 22 in Chicago, 14 in Denver, 10 in New York), and the
new roles and attributes hold their constraints."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

OFFICES = {"Chicago": 22, "Denver": 14, "New York": 10}
LEVELS = ["partner", "manager", "senior", "staff", "seasonal", "admin"]


class _Db:
    """Superuser statements through the shared seeder; each test makes its own firm."""

    def __init__(self, seed: Seeder) -> None:
        self._seed = seed

    async def execute(self, sql: str, *args: object) -> None:
        await self._seed.run(sql, *args)

    async def fetchval(self, sql: str, *args: object) -> uuid.UUID:
        return uuid.UUID(str(await self._seed.value(sql, *args)))

    async def count(self, sql: str, *args: object) -> int:
        return int(str(await self._seed.value(sql, *args)))


@pytest.fixture
def db(migrated_db: MigratedDatabase) -> _Db:
    return _Db(Seeder(migrated_db.superuser_dsn))


async def _person(db: _Db) -> uuid.UUID:
    sub = uuid.uuid4().hex
    return await db.fetchval(
        "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
        "VALUES ('https://probe.test', $1, $2, 'Probe') RETURNING id",
        sub,
        f"{sub}@example.test",
    )


async def test_three_offices_and_46_levelled_memberships(db: _Db) -> None:
    tenant = uuid.uuid4()
    await db.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Brightwater Hale')", tenant)
    office_ids = {
        name: await db.fetchval(
            "INSERT INTO offices (tenant_id, name) VALUES ($1, $2) RETURNING id", tenant, name
        )
        for name in OFFICES
    }
    n = 0
    for office, seats in OFFICES.items():
        for i in range(seats):
            user = await _person(db)
            await db.execute(
                "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, "
                "office_id, service_lines, initials) "
                "VALUES ($1, $2, NULL, 'active', $3, $4, $5, $6)",
                tenant,
                user,
                LEVELS[(n + i) % len(LEVELS)],
                office_ids[office],
                ["audit"] if i % 2 else ["tax"],
                "AB",
            )
        n += seats
    counts = {
        office: await db.count(
            "SELECT count(*) FROM memberships WHERE tenant_id = $1 AND office_id = $2",
            tenant,
            office_ids[office],
        )
        for office in OFFICES
    }
    assert counts == OFFICES
    assert sum(OFFICES.values()) == 46


async def test_the_new_roles_are_accepted(db: _Db) -> None:
    tenant = uuid.uuid4()
    await db.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    user = await _person(db)
    await db.execute(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level) "
        "VALUES ($1, $2, 'security_admin', 'active', 'admin')",
        tenant,
        user,
    )


# One fixed statement per attribute: no SQL is built from a value.
BAD: dict[str, tuple[str, object]] = {
    "level": (
        "INSERT INTO memberships (tenant_id, user_id, status, level) "
        "VALUES ($1, $2, 'active', $3)",
        "intern",
    ),
    "initials-lower": (
        "INSERT INTO memberships (tenant_id, user_id, status, initials) "
        "VALUES ($1, $2, 'active', $3)",
        "abc",
    ),
    "initials-long": (
        "INSERT INTO memberships (tenant_id, user_id, status, initials) "
        "VALUES ($1, $2, 'active', $3)",
        "ABCDE",
    ),
    "service_lines": (
        "INSERT INTO memberships (tenant_id, user_id, status, service_lines) "
        "VALUES ($1, $2, 'active', $3)",
        ["hr"],
    ),
}


@pytest.mark.parametrize("case", sorted(BAD))
async def test_attributes_are_constrained(db: _Db, case: str) -> None:
    sql, value = BAD[case]
    tenant = uuid.uuid4()
    await db.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    user = await _person(db)
    with pytest.raises(asyncpg.CheckViolationError):
        await db.execute(sql, tenant, user, value)


async def test_a_client_membership_has_no_level_or_office(db: _Db) -> None:
    tenant = uuid.uuid4()
    await db.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    user = await _person(db)
    with pytest.raises(asyncpg.CheckViolationError):
        await db.execute(
            "INSERT INTO memberships (tenant_id, user_id, status, kind, level) "
            "VALUES ($1, $2, 'active', 'client', 'staff')",
            tenant,
            user,
        )


async def test_an_office_belongs_to_one_firm(db: _Db) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    for t in (a, b):
        await db.execute("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", t)
    office = await db.fetchval(
        "INSERT INTO offices (tenant_id, name) VALUES ($1, 'Denver') RETURNING id", a
    )
    user = await _person(db)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await db.execute(
            "INSERT INTO memberships (tenant_id, user_id, status, office_id) "
            "VALUES ($1, $2, 'active', $3)",
            b,
            user,
            office,
        )
