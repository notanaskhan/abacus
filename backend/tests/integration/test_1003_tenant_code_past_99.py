"""Migration 1003 (TASK-8868; DEC-5865): the 100th firm with the same initials gets a code.

Before 1003, `lpad(n::text, 2, '0')` truncated 100 to `10`: the trigger looped forever on the
100th `Firm x…` (the hang that held CI shards to their timeout) and `provision_firm` could never
provision it. Every statement here runs under a short statement timeout, so a regression fails
in seconds instead of hanging the shard.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest

from abacus_tools.db_connect import connect
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

TIMEOUT = "SET statement_timeout = '10s'"


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _codes_from_trigger(dsn: str, count: int) -> list[str]:
    conn = await connect(dsn)
    try:
        await conn.execute(TIMEOUT)
        codes: list[str] = []
        for _ in range(count):
            tenant = uuid.uuid4()
            codes.append(
                await conn.fetchval(
                    "INSERT INTO firms (tenant_id, name) VALUES ($1, $2) RETURNING tenant_code",
                    tenant,
                    f"Firm x{tenant.hex[:8]}",
                )
            )
        return codes
    finally:
        await conn.close()


async def _codes_from_provisioning(dsn: str, count: int) -> list[str]:
    conn = await connect(dsn)
    try:
        await conn.execute(TIMEOUT)
        codes: list[str] = []
        for _ in range(count):
            tenant = await conn.fetchval(
                "SELECT provision_firm($1, true, 'us', 'America/Chicago', $2, 'test')",
                "Pinned Probe Co",
                uuid.uuid4().hex,
            )
            codes.append(
                await conn.fetchval("SELECT tenant_code FROM firms WHERE tenant_id = $1", tenant)
            )
        return codes
    finally:
        await conn.close()


def test_the_trigger_numbers_past_99(db: sc.Database) -> None:
    codes = asyncio.run(_codes_from_trigger(db.superuser_dsn, 101))
    assert codes[0] == "tnt_fx01"
    assert codes[98:] == ["tnt_fx99", "tnt_fx100", "tnt_fx101"]
    assert len(set(codes)) == len(codes)


def test_provisioning_numbers_past_99(db: sc.Database) -> None:
    codes = asyncio.run(_codes_from_provisioning(db.superuser_dsn, 101))
    assert codes[0] == "tnt_ppc01"
    assert codes[98:] == ["tnt_ppc99", "tnt_ppc100", "tnt_ppc101"]
    assert len(set(codes)) == len(codes)
