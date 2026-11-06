"""P-10-T06 (TASK-5115; P-10 §4.2; ADR-148; SPEC-647): migration 0684 `agent_minute_ledger`.

Row acceptance: "The ledger is insert-only and a fixture rollup over stored integers foots 8,640 +
4,610 + 1,420 + 120 + 130 = 14,920."
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

LINES = (("audit", 8640), ("tax", 4610), ("cas", 1420), ("advisory", 120), ("firm_ops", 130))
INSERT = (
    "INSERT INTO agent_minute_ledger (tenant_id, usage_month, run_id, service_line, capability, "
    "minutes, agent_ms, cost_usd) VALUES ($1, '2026-09', $2, $3, 'engagements.run', $4, 0, 0)"
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _ledger(seeder: Seeder) -> uuid.UUID:
    tenant = asyncio.run(seeder.firm())
    for line, minutes in LINES:
        asyncio.run(seeder.run(INSERT, tenant, uuid.uuid4(), line, minutes))
    return tenant


def test_a_rollup_over_stored_integers_foots(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    tenant = _ledger(seeder)
    total = asyncio.run(
        seeder.value("SELECT sum(minutes) FROM agent_minute_ledger WHERE tenant_id = $1", tenant)
    )
    assert total == 14920


@pytest.mark.parametrize(
    "sql", ["UPDATE agent_minute_ledger SET minutes = 1", "DELETE FROM agent_minute_ledger"]
)
def test_the_ledger_is_insert_only(private_db: sc.Database, sql: str) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    tenant = _ledger(seeder)
    with pytest.raises(asyncpg.CheckViolationError, match="insert-only"):
        asyncio.run(seeder.run(f"{sql} WHERE tenant_id = $1", tenant))


def test_one_row_per_run(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    tenant = asyncio.run(seeder.firm())
    run_id = uuid.uuid4()
    asyncio.run(seeder.run(INSERT, tenant, run_id, "audit", 1))
    with pytest.raises(asyncpg.UniqueViolationError):
        asyncio.run(seeder.run(INSERT, tenant, run_id, "audit", 1))


def test_a_budget_defaults_to_1500_minutes_and_80_percent(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    rows = asyncio.run(
        seeder.rows(
            "SELECT column_name, column_default FROM information_schema.columns "
            "WHERE table_name = 'engagement_agent_budgets' AND column_default IS NOT NULL"
        )
    )
    assert {r["column_name"]: r["column_default"] for r in rows} == {
        "minutes_per_usage_month": "1500",
        "alert_pct": "80",
    }


def test_down_then_up(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, "0683", down=True)
    assert not asyncio.run(
        seeder.value("SELECT to_regclass('public.agent_minute_ledger') IS NOT NULL")
    )
    migrate(private_db.owner_url, "head")
    assert asyncio.run(
        seeder.value("SELECT to_regclass('public.agent_minute_ledger') IS NOT NULL")
    )
