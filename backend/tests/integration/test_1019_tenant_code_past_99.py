"""Migration 1019 (TASK-8965; DEC-5944): the 100th firm with the same initials gets a code.

Before 1019, `lpad(n::text, 2, '0')` truncated 100 to `10`: the trigger looped forever on the
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


async def _function_sources(dsn: str) -> dict[str, str]:
    conn = await connect(dsn)
    try:
        rows = await conn.fetch(
            "SELECT proname, prosrc FROM pg_proc WHERE proname = ANY($1::text[])",
            ["firms_tenant_code_default", "provision_firm", "firm_signup"],
        )
        return {str(r["proname"]): str(r["prosrc"]) for r in rows}
    finally:
        await conn.close()


def test_every_tenant_code_function_keeps_long_numbers_whole(db: sc.Database) -> None:
    """firm_signup (1003) numbered sign-up codes with the same truncating pad; it needs a sign-up
    code and an identity to call, so its body is checked here beside the two run above."""
    sources = asyncio.run(_function_sources(db.superuser_dsn))
    assert set(sources) == {"firms_tenant_code_default", "provision_firm", "firm_signup"}
    for name, body in sources.items():
        assert "lpad(v_n::text, 2," not in body, name
        assert "greatest(2, length(v_n::text))" in body, name
