# ac-test-author: ayushkbhatia
"""K-02-T09 (TASK-2211; ADR-078): independent acceptance tests for N's red work in K-02-T03,
migration 0400's global reference sets, written from K-02 §4.2, ADR-300 and the contract
(`docs/contracts/rules-tables.md`), not from the implementing suite.

- Global-table privileges: no application role holds any privilege on the three tables, read
  from the catalog for every privilege, not by trying a few statements.
- The readers are the app's only door and never return a draft (resolve, list or history); the
  operators' functions are not executable by any application role.
- Two people: the database refuses a published version whose approver is its drafter even when
  the status is written directly, bypassing `reference_set_publish`; a withdrawal is two-person.
- Immutability after publish: the payload, effective date, handles and hash are frozen, the only
  later status is `withdrawn`, nothing is deleted, and the publication log is insert-only.

The suite fails if `abacus_app` can read a draft reference-set version. Every value is a synthetic
probe (`probe.*` keys), never a real rule (AGENTS 16).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import date
from typing import cast

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

AY, AN = "ayushkbhatia", "notanaskhan"
TABLES = ("reference_sets", "reference_set_versions", "reference_set_publications")
PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")
READERS = ("reference_set_resolve", "reference_set_list", "reference_set_history")
OPERATORS = (
    "reference_set_draft",
    "reference_set_publish",
    "reference_set_withdraw",
    "active_tenant_ids",
    "standards_sets_apply",
)


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


@pytest.fixture
async def owner(db: sc.Database) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn(db.owner_url))
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def app(db: sc.Database) -> AsyncIterator[asyncpg.Connection]:
    conn = await asyncpg.connect(_dsn(db.app_url))
    try:
        yield conn
    finally:
        await conn.close()


async def _app_roles(owner: asyncpg.Connection) -> list[str]:
    """Every login or group role the services run as (everything but the owner and superusers)."""
    me = cast(str, await owner.fetchval("SELECT current_user"))
    rows = await owner.fetch(
        "SELECT rolname FROM pg_roles WHERE rolname LIKE 'abacus%' AND NOT rolsuper "
        "AND rolname <> $1",
        me,
    )
    roles = [cast(str, r["rolname"]) for r in rows]
    assert "abacus_app" in roles
    return roles


async def _draft(
    owner: asyncpg.Connection, key: str, *, effective_from: date = date(2020, 1, 1)
) -> uuid.UUID:
    payload = json.dumps(
        {
            "kind": "legal_holidays",
            "rows": [{"date": "2027-01-01", "name": "Probe", "jurisdiction": "US"}],
        }
    )
    return cast(
        uuid.UUID,
        await owner.fetchval(
            "SELECT reference_set_draft($1, 'legal_holidays', 'Probe', 'US', $2, NULL, 2026, $3, "
            "$4::jsonb, $5, '[]'::jsonb, $2, 'probe')",
            key,
            AY,
            effective_from,
            payload,
            "sha256:" + hashlib.sha256(payload.encode()).hexdigest(),
        ),
    )


def _key() -> str:
    return f"probe.k02t09.{uuid.uuid4().hex[:10]}"


async def test_no_application_role_holds_any_privilege_on_the_tables(
    owner: asyncpg.Connection,
) -> None:
    for role in await _app_roles(owner):
        for table in TABLES:
            for privilege in PRIVILEGES:
                held = await owner.fetchval(
                    "SELECT has_table_privilege($1, $2, $3)", role, table, privilege
                )
                assert held is False, (role, table, privilege)


async def test_the_app_executes_the_readers_and_no_operator_function(
    owner: asyncpg.Connection,
) -> None:
    roles = await _app_roles(owner)
    for name in (*READERS, *OPERATORS):
        oids = await owner.fetch("SELECT oid FROM pg_proc WHERE proname = $1", name)
        assert oids, name
        for row in oids:
            for role in roles:
                held = await owner.fetchval(
                    "SELECT has_function_privilege($1, $2::oid, 'EXECUTE')", role, row["oid"]
                )
                expected = name in READERS and role == "abacus_app"
                assert held is expected, (role, name)
    # PUBLIC holds nothing on any of them.
    for name in (*READERS, *OPERATORS):
        public = await owner.fetchval(
            "SELECT bool_or(acl.grantee = 0) FROM pg_proc p, aclexplode(p.proacl) acl "
            "WHERE p.proname = $1",
            name,
        )
        assert public is not True, name


async def test_the_app_never_reads_a_draft_through_any_reader(
    owner: asyncpg.Connection, app: asyncpg.Connection
) -> None:
    key = _key()
    await _draft(owner, key)
    assert (
        await app.fetch("SELECT * FROM reference_set_resolve($1, $2)", key, date(2030, 1, 1)) == []
    )
    assert await app.fetch("SELECT * FROM reference_set_history($1)", key) == []
    listed = await app.fetch("SELECT key FROM reference_set_list('legal_holidays')")
    assert key not in {r["key"] for r in listed}
    for statement in (
        "SELECT * FROM reference_sets LIMIT 1",
        "SELECT * FROM reference_set_versions LIMIT 1",
        "SELECT * FROM reference_set_publications LIMIT 1",
    ):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.fetch(statement)


async def test_the_database_refuses_an_approver_who_drafted_even_bypassing_publish(
    owner: asyncpg.Connection,
) -> None:
    version = await _draft(owner, _key())
    with pytest.raises(asyncpg.CheckViolationError):
        await owner.execute(
            "UPDATE reference_set_versions SET status = 'published', approved_by = drafted_by, "
            "published_at = clock_timestamp() WHERE id = $1",
            version,
        )
    with pytest.raises(asyncpg.CheckViolationError):
        await owner.execute(
            "UPDATE reference_set_versions SET status = 'published', approved_by = NULL, "
            "published_at = clock_timestamp() WHERE id = $1",
            version,
        )


async def test_a_published_version_is_frozen_and_only_withdrawn_later(
    owner: asyncpg.Connection,
) -> None:
    version = await _draft(owner, _key())
    await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", version, AN)
    for change in (
        "UPDATE reference_set_versions SET payload = jsonb_set(payload, '{rows}', '[]') "
        "WHERE id = $1",
        "UPDATE reference_set_versions SET effective_from = '2031-01-01' WHERE id = $1",
        "UPDATE reference_set_versions SET drafted_by = 'someone' WHERE id = $1",
        "UPDATE reference_set_versions SET approved_by = 'someone' WHERE id = $1",
        "UPDATE reference_set_versions SET payload_hash = 'sha256:" + "0" * 64 + "' WHERE id = $1",
        (
            "UPDATE reference_set_versions SET status = 'draft', approved_by = NULL, "
            "published_at = NULL WHERE id = $1"
        ),
        "DELETE FROM reference_set_versions WHERE id = $1",
    ):
        with pytest.raises(asyncpg.PostgresError):
            await owner.execute(change, version)
    # A withdrawal is two-person too.
    with pytest.raises(asyncpg.InsufficientPrivilegeError, match="approver_is_operator"):
        await owner.execute("SELECT reference_set_withdraw($1, $2, $2, 'probe')", version, AY)
    await owner.execute("SELECT reference_set_withdraw($1, $2, $3, 'probe')", version, AY, AN)
    status = await owner.fetchval(
        "SELECT status FROM reference_set_versions WHERE id = $1", version
    )
    assert status == "withdrawn"
    with pytest.raises(asyncpg.PostgresError):
        await owner.execute(
            "UPDATE reference_set_versions SET status = 'published' WHERE id = $1", version
        )


async def test_the_publication_log_is_insert_only(owner: asyncpg.Connection) -> None:
    version = await _draft(owner, _key())
    await owner.execute("SELECT reference_set_publish($1, $2, 'probe')", version, AN)
    for change in (
        "UPDATE reference_set_publications SET reason = 'rewritten' WHERE version_id = $1",
        "DELETE FROM reference_set_publications WHERE version_id = $1",
    ):
        with pytest.raises(asyncpg.PostgresError):
            await owner.execute(change, version)
    with pytest.raises(asyncpg.PostgresError):
        await owner.execute("TRUNCATE reference_set_publications")
