"""AC-1, AC-18: local seeding (TASK-012 interface contract, "Seeding").

Runs `abacus_tools.local.seed_dev.seed` against the migrated test database as the superuser
(`migrated_db.superuser_dsn`). The Dev firm has a fixed id, so tests add engagements to it and
assert on what changes, not on absolute counts.
"""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast

import asyncpg
import pytest

from abacus.modules.connections.api import Period, fixture_path
from abacus_tools.local import seed_dev

PERIOD = (date(2024, 1, 1), date(2024, 12, 31))


class MigratedDatabase(Protocol):
    @property
    def superuser_dsn(self) -> str: ...


async def _run(dsn: str, sql: str, *args: object) -> object:
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


async def _rows(dsn: str, sql: str, *args: object) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(dsn)
    try:
        return list(await conn.fetch(sql, *args))
    finally:
        await conn.close()


async def _add_engagement(dsn: str, name: str, period: tuple[date, date] = PERIOD) -> uuid.UUID:
    """A client entity and engagement in the Dev firm; returns the client entity id."""
    leader = await _run(
        dsn,
        "SELECT id FROM users WHERE idp_subject = 'dev-leader' AND idp_issuer = $1",
        seed_dev.ISSUER,
    )
    client_id = await _run(
        dsn,
        "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
        seed_dev.FIRM,
        f"Client {name}",
    )
    entity = await _run(
        dsn,
        "INSERT INTO client_entities (tenant_id, client_id, name) "
        "VALUES ($1, $2, $3) RETURNING id",
        seed_dev.FIRM,
        client_id,
        f"Entity {name}",
    )
    await _run(
        dsn,
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by) "
        "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
        seed_dev.FIRM,
        client_id,
        entity,
        name,
        period[0],
        period[1],
        leader,
    )
    return cast(uuid.UUID, entity)


async def _connections(dsn: str, entity: uuid.UUID) -> list[asyncpg.Record]:
    return await _rows(
        dsn,
        "SELECT id, status, provider FROM connections WHERE tenant_id = $1 "
        "AND client_entity_id = $2",
        seed_dev.FIRM,
        entity,
    )


async def test_ac1_seed_creates_the_dev_firm_and_users(
    migrated_db: MigratedDatabase, tmp_path: Path
) -> None:
    dsn = migrated_db.superuser_dsn
    await seed_dev.seed(dsn, tmp_path)
    assert (
        await _run(dsn, "SELECT name FROM firms WHERE tenant_id = $1", seed_dev.FIRM) == "Dev firm"
    )
    rows = await _rows(
        dsn,
        "SELECT u.idp_subject, m.firm_role FROM memberships m JOIN users u ON u.id = m.user_id "
        "WHERE m.tenant_id = $1 AND u.idp_issuer = $2",
        seed_dev.FIRM,
        seed_dev.ISSUER,
    )
    roles = {row["idp_subject"]: row["firm_role"] for row in rows}
    assert roles == {"dev-leader": "practice_leader", "dev-staff": None}


async def test_ac1_seed_is_idempotent(migrated_db: MigratedDatabase, tmp_path: Path) -> None:
    dsn = migrated_db.superuser_dsn
    await seed_dev.seed(dsn, tmp_path)
    await seed_dev.seed(dsn, tmp_path)
    await seed_dev.seed(dsn, tmp_path)
    firms = await _run(dsn, "SELECT count(*) FROM firms WHERE tenant_id = $1", seed_dev.FIRM)
    members = await _run(
        dsn, "SELECT count(*) FROM memberships WHERE tenant_id = $1", seed_dev.FIRM
    )
    users = await _run(
        dsn,
        "SELECT count(*) FROM users WHERE idp_issuer = $1 AND idp_subject IN "
        "('dev-leader', 'dev-staff')",
        seed_dev.ISSUER,
    )
    assert (firms, members, users) == (1, 2, 2)


async def test_ac1_seed_connects_an_engagement_and_writes_a_balanced_fixture(
    migrated_db: MigratedDatabase, tmp_path: Path
) -> None:
    dsn = migrated_db.superuser_dsn
    await seed_dev.seed(dsn, tmp_path)
    entity = await _add_engagement(dsn, "Seed connect", (date(2023, 4, 1), date(2024, 3, 31)))
    assert await seed_dev.seed(dsn, tmp_path) == 1
    connections = await _connections(dsn, entity)
    assert len(connections) == 1
    assert connections[0]["status"] == "active"
    assert connections[0]["provider"] == "fake"
    path = fixture_path(
        tmp_path,
        connections[0]["id"],
        "trial_balance",
        Period(date(2023, 4, 1), date(2024, 3, 31)),
    )
    document = json.loads(path.read_text())
    assert document["period"] == {"start": "2023-04-01", "end": "2024-03-31"}
    lines = document["lines"]
    debit = sum((Decimal(line["debit"]) for line in lines), Decimal(0))
    credit = sum((Decimal(line["credit"]) for line in lines), Decimal(0))
    assert lines
    assert debit == credit
    assert document["control_totals"] == {"debit": f"{debit}", "credit": f"{credit}"}


async def test_ac1_seed_again_adds_no_connection_but_keeps_the_fixture(
    migrated_db: MigratedDatabase, tmp_path: Path
) -> None:
    dsn = migrated_db.superuser_dsn
    await seed_dev.seed(dsn, tmp_path)
    entity = await _add_engagement(dsn, "Seed twice")
    assert await seed_dev.seed(dsn, tmp_path) == 1
    first = (await _connections(dsn, entity))[0]["id"]
    path = fixture_path(tmp_path, first, "trial_balance", Period(*PERIOD))
    path.unlink()
    assert await seed_dev.seed(dsn, tmp_path) == 0
    connections = await _connections(dsn, entity)
    assert [row["id"] for row in connections] == [first]
    assert path.exists()


async def test_ac1_seed_reuses_an_existing_active_connection(
    migrated_db: MigratedDatabase, tmp_path: Path
) -> None:
    dsn = migrated_db.superuser_dsn
    await seed_dev.seed(dsn, tmp_path)
    entity = await _add_engagement(dsn, "Seed reuse")
    existing = await _run(
        dsn,
        "INSERT INTO connections (tenant_id, client_entity_id, provider, created_by) "
        "VALUES ($1, $2, 'fake', 'test') RETURNING id",
        seed_dev.FIRM,
        entity,
    )
    await seed_dev.seed(dsn, tmp_path)
    connections = await _connections(dsn, entity)
    assert [row["id"] for row in connections] == [existing]
    assert fixture_path(
        tmp_path, cast(uuid.UUID, existing), "trial_balance", Period(*PERIOD)
    ).exists()


async def test_ac1_seed_counts_each_new_connection(
    migrated_db: MigratedDatabase, tmp_path: Path
) -> None:
    dsn = migrated_db.superuser_dsn
    await seed_dev.seed(dsn, tmp_path)
    await _add_engagement(dsn, "Seed count a")
    await _add_engagement(dsn, "Seed count b")
    assert await seed_dev.seed(dsn, tmp_path) == 2


@pytest.mark.parametrize(
    ("environment", "fixtures"),
    [("production", "fixtures"), ("local", None), ("test", None)],
)
def test_ac1_seed_main_refuses_outside_local_or_without_a_fixture_dir(
    monkeypatch: pytest.MonkeyPatch, environment: str, fixtures: str | None
) -> None:
    monkeypatch.setattr(
        seed_dev,
        "settings",
        lambda: SimpleNamespace(environment=environment, fake_connector_dir=fixtures),
    )
    with pytest.raises(RuntimeError):
        seed_dev.main()
