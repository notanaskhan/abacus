"""F-03-T20: independent checks (ADR-078) of the work-item and lifecycle migrations, from
chapter 03 §3.1.4 steps 1 and 2 and F-03 story 1.1: "Given the migration has run, then every
pre-existing engagement has exactly one assurance work item and one primary engagement_entities
row", and the migrations go down and up again cleanly."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0067"  # the revision before work items (0068) and the lifecycle (0069)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _revision(database: sc.Database) -> str:
    seed = Seeder(database.superuser_dsn)
    return str(asyncio.run(seed.value("SELECT version_num FROM alembic_version")))


async def _seed_engagements(seed: Seeder) -> list[uuid.UUID]:
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe firm')", tenant)
    user = await seed.value(
        "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
        "VALUES ('https://probe.test', $1, $2, 'Probe') RETURNING id",
        f"sub-{uuid.uuid4().hex}",
        f"{uuid.uuid4().hex}@example.test",
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, 'firm_admin', 'active')",
        tenant,
        user,
    )
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Probe client') RETURNING id", tenant
    )
    entity = await seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) "
        "VALUES ($1, $2, 'Probe entity') RETURNING id",
        tenant,
        client,
    )
    ids: list[uuid.UUID] = []
    for name, status in (("Open", "active"), ("Done", "archived")):
        ids.append(
            uuid.UUID(
                str(
                    await seed.value(
                        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                        "fiscal_period_start, fiscal_period_end, created_by, status) "
                        "VALUES ($1, $2, $3, $4, '2025-01-01', '2025-12-31', $5, $6) RETURNING id",
                        tenant,
                        client,
                        entity,
                        name,
                        user,
                        status,
                    )
                )
            )
        )
    return ids


def test_story_1_1_backfill_and_down_up(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    head = _revision(private_db)
    migrate(private_db.owner_url, BEFORE, down=True)
    assert _revision(private_db) == BEFORE
    assert asyncio.run(seed.value("SELECT to_regclass('work_items') IS NULL")) is True
    engagements = asyncio.run(_seed_engagements(seed))

    migrate(private_db.owner_url, "head")
    assert _revision(private_db) == head
    for engagement in engagements:
        assurance = asyncio.run(
            seed.value(
                "SELECT count(*) FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
                engagement,
            )
        )
        primary = asyncio.run(
            seed.value(
                "SELECT count(*) FROM engagement_entities "
                "WHERE engagement_id = $1 AND role = 'primary'",
                engagement,
            )
        )
        assert (assurance, primary) == (1, 1), engagement
    # The archived engagement's assurance work item is archived too (§3.1.4 step 1).
    phase = asyncio.run(
        seed.value(
            "SELECT a.phase FROM assurance_work_items a "
            "JOIN work_items w ON w.id = a.work_item_id WHERE w.engagement_id = $1",
            engagements[1],
        )
    )
    assert phase == "archived"
    # Every row carries (tenant_id, engagement_id, work_item_id) scope (story 1.1).
    unscoped = asyncio.run(
        seed.value(
            "SELECT count(*) FROM work_items WHERE tenant_id IS NULL OR engagement_id IS NULL"
        )
    )
    assert unscoped == 0

    # Down and up again: the schema comes back the same and passes the schema check.
    migrate(private_db.owner_url, BEFORE, down=True)
    assert asyncio.run(seed.value("SELECT to_regclass('work_items') IS NULL")) is True
    migrate(private_db.owner_url, "head")
    assert _revision(private_db) == head
    assert sc.check(private_db.owner_url, private_db.app_url) == []
