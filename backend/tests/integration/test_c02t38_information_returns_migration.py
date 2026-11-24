"""C-02-T38 (TASK-8904; C-02 §4.2): migration 1013, information returns.

"Up/down/up passes, no column can hold a full TIN, and the insert-only tables reject UPDATE and
DELETE" (the row's acceptance).
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

BEFORE = "1012"
TABLES = (
    "vendors_1099",
    "vendor_payment_rollups",
    "w9_requests",
    "tin_match_results",
    "backup_withholding_events",
    "information_return_batches",
    "information_returns",
)
INSERT_ONLY = ("w9_requests", "tin_match_results", "backup_withholding_events",
               "information_returns")  # fmt: skip


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


def test_ac_up_down_up(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert asyncio.run(seed.value("SELECT to_regclass($1) IS NULL", table)), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        assert asyncio.run(seed.value("SELECT to_regclass($1) IS NOT NULL", table)), table
    assert sc.check(private_db.owner_url, private_db.app_url) == []


def test_ac_no_column_can_hold_a_full_tin(private_db: sc.Database) -> None:
    """Only `tin_sealed` (an envelope), `tin_last4` (four digits), `tin_kind` and
    `tin_fingerprint` carry anything of a TIN, and they come together."""
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    tenant = asyncio.run(seed.firm())
    person = asyncio.run(seed.person(tenant))
    entity = asyncio.run(seed.entity(tenant))
    actor = ("human", str(person.user_id))
    vendor = uuid.uuid4()

    async def tins() -> None:
        columns = await seed.rows(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ANY($1) "
            "AND column_name LIKE '%tin%'",
            list(TABLES),
        )
        assert {r["column_name"] for r in columns} == {
            "tin_sealed",
            "tin_last4",
            "tin_kind",
            "tin_fingerprint",
        }
        await app.as_actor(
            tenant,
            actor,
            "INSERT INTO vendors_1099 (id, tenant_id, client_entity_id, external_vendor_id, "
            "display_name) VALUES ($1, $2, $3, 'QBO-58', 'Hartwell & Lowe LLP')",
            vendor,
            tenant,
            entity,
        )
        update = (
            "UPDATE vendors_1099 SET tin_sealed = $2, tin_last4 = $3, tin_kind = 'ein', "
            "tin_fingerprint = $4 WHERE id = $1"
        )
        with pytest.raises(asyncpg.CheckViolationError):  # nine digits in the last-four column
            await app.as_actor(tenant, actor, update, vendor, b"x" * 64, "123456789", b"f" * 32)
        with pytest.raises(asyncpg.CheckViolationError):  # last four without the envelope
            await app.as_actor(
                tenant,
                actor,
                "UPDATE vendors_1099 SET tin_last4 = '6789' WHERE id = $1",
                vendor,
            )
        await app.as_actor(tenant, actor, update, vendor, b"x" * 64, "6789", b"f" * 32)

    asyncio.run(tins())


def test_ac_the_insert_only_tables_refuse_update_and_delete(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    tenant = asyncio.run(seed.firm())
    person = asyncio.run(seed.person(tenant))
    actor = ("human", str(person.user_id))

    async def refused() -> None:
        for table in INSERT_ONLY:
            for statement in (
                f"UPDATE {table} SET tenant_id = tenant_id WHERE id = $1",  # noqa: S608
                f"DELETE FROM {table} WHERE id = $1",  # noqa: S608
            ):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await app.as_actor(tenant, actor, statement, uuid.uuid4())
        # A vendor link request waits for R-03's link principal.
        entity = await seed.entity(tenant)
        vendor = uuid.uuid4()
        await seed.run(
            "INSERT INTO vendors_1099 (id, tenant_id, client_entity_id, external_vendor_id, "
            "display_name) VALUES ($1, $2, $3, 'QBO-61', 'Marlow Signs')",
            vendor,
            tenant,
            entity,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await app.as_actor(
                tenant,
                actor,
                "INSERT INTO w9_requests (tenant_id, client_entity_id, vendor_ids, channel, "
                "sent_by) VALUES ($1, $2, $3, 'vendor_link', $4)",
                tenant,
                entity,
                [vendor],
                person.user_id,
            )
        # Backup withholding starts at 24% only, and a batch is approved by a person.
        with pytest.raises(asyncpg.CheckViolationError):
            await app.as_actor(
                tenant,
                actor,
                "INSERT INTO backup_withholding_events (tenant_id, vendor_id, event, reason, "
                "rate_percent, recorded_by) VALUES ($1, $2, 'started', 'TIN missing', 28, $3)",
                tenant,
                vendor,
                person.user_id,
            )
        batch = uuid.uuid4()
        await app.as_actor(
            tenant,
            actor,
            "INSERT INTO information_return_batches (id, tenant_id, client_entity_id, "
            "tax_year, due_on) VALUES ($1, $2, $3, 2026, DATE '2027-02-01')",
            batch,
            tenant,
            entity,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await app.as_actor(
                tenant,
                actor,
                "UPDATE information_return_batches SET status = 'approved' WHERE id = $1",
                batch,
            )

    asyncio.run(refused())
