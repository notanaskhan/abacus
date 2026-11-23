"""K-03-T13 (TASK-8903; SPEC-721; K-03 §4.2): migration 1012, the Sheets engine core.

"The migration goes up/down/up, a column without classification or a twelfth type is refused, an
archived engagement's sheet refuses writes, and forced RLS isolates two tenants" (the row's
acceptance).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Person, Seeder

BEFORE = "1011"
TABLES = (
    "sheets",
    "sheet_columns",
    "sheet_sections",
    "sheet_rows",
    "sheet_cells",
    "sheet_views",
    "sheet_row_links",
    "agent_columns",
    "agent_column_previews",
    "agent_column_runs",
    "agent_column_run_rows",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    person: Person
    engagement: uuid.UUID
    item: uuid.UUID
    sheet: uuid.UUID

    @property
    def actor(self) -> tuple[str, str]:
        return ("human", str(self.person.user_id))


async def _world(seed: Seeder) -> World:
    """A firm with a published template version holding BH-FS-430, and an engagement whose
    assurance work item has that sheet."""
    tenant = await seed.firm()
    person = await seed.person(tenant)
    methodology, engagement_template, version, definition = (uuid.uuid4() for _ in range(4))
    await seed.run(
        "INSERT INTO methodology_templates (id, tenant_id, name, created_by) "
        "VALUES ($1, $2, 'BH Audit Methodology · FS', $3)",
        methodology,
        tenant,
        person.user_id,
    )
    await seed.run(
        "INSERT INTO engagement_templates (id, tenant_id, methodology_template_id, name) "
        "VALUES ($1, $2, $3, 'BH Audit Methodology · FS')",
        engagement_template,
        tenant,
        methodology,
    )
    await seed.run(
        "INSERT INTO template_versions (id, tenant_id, template_id, seq, label, created_by) "
        "VALUES ($1, $2, $3, 6, 'FS v6', $4)",
        version,
        tenant,
        engagement_template,
        person.user_id,
    )
    await seed.run(
        "INSERT INTO template_sheet_definitions (id, tenant_id, template_version_id, sheet_key, "
        "title, row_source) VALUES ($1, $2, $3, 'BH-FS-430', "
        "'Search for Unrecorded Liabilities', 'sample_set')",
        definition,
        tenant,
        version,
    )
    await seed.run(
        "UPDATE template_versions SET status = 'published', effective_from = DATE '2026-10-01', "
        "fingerprint = $2, published_by = $3, published_at = now() WHERE id = $1",
        version,
        "6" * 64,
        person.user_id,
    )
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    item = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 ORDER BY created_at LIMIT 1",
        engagement,
    )
    if item is None:
        client = await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
        item = await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'assurance', 'Granite Peak FY2026', "
            "$5) RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            person.user_id,
        )
    sheet = uuid.uuid4()
    await seed.run(
        "INSERT INTO sheets (id, tenant_id, engagement_id, work_item_id, sheet_key, title, "
        "template_version_id, sheet_definition_id, created_by) VALUES ($1, $2, $3, $4, "
        "'BH-FS-430', 'Search for Unrecorded Liabilities', $5, $6, $7)",
        sheet,
        tenant,
        engagement,
        item,
        version,
        definition,
        person.user_id,
    )
    return World(tenant, person, engagement, uuid.UUID(str(item)), sheet)


def _column_sql(world: World) -> tuple[str, tuple[object, ...]]:
    return (
        "INSERT INTO sheet_columns (tenant_id, engagement_id, work_item_id, sheet_id, "
        "column_key, name, type, classification, origin) VALUES ($1, $2, $3, $4, $5, $6, $7, "
        "$8, 'engagement')",
        (world.tenant, world.engagement, world.item, world.sheet),
    )


def test_ac_up_down_up(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert asyncio.run(seed.value("SELECT to_regclass($1) IS NULL", table)), table
    migrate(private_db.owner_url, "head")
    forced = asyncio.run(
        seed.value(
            "SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class "
            "WHERE relnamespace = 'public'::regnamespace AND relname = ANY($1::text[])",
            list(TABLES),
        )
    )
    assert forced is True
    guarded = asyncio.run(
        seed.value(
            "SELECT count(DISTINCT c.relname) FROM pg_trigger t JOIN pg_class c "
            "ON c.oid = t.tgrelid WHERE t.tgname = 'archived_guard' "
            "AND c.relname = ANY($1::text[])",
            list(TABLES),
        )
    )
    assert guarded == len(TABLES)
    assert sc.check(private_db.owner_url, private_db.app_url) == []


def test_ac_a_column_needs_a_classification_and_one_of_eleven_types(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    world = asyncio.run(_world(seed))
    sql, scope = _column_sql(world)

    async def columns() -> None:
        with pytest.raises(asyncpg.NotNullViolationError):
            await app.as_actor(
                world.tenant, world.actor, sql, *scope, "conclusion", "Conclusion", "text", None
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await app.as_actor(
                world.tenant, world.actor, sql, *scope, "formula", "Formula", "formula",
                "internal",
            )  # fmt: skip
        await app.as_actor(
            world.tenant, world.actor, sql, *scope, "conclusion", "Conclusion", "agent",
            "confidential",
        )  # fmt: skip
        # A client-visible column on an internal sheet is refused.
        with pytest.raises(asyncpg.CheckViolationError):
            await app.as_actor(
                world.tenant,
                world.actor,
                "UPDATE sheet_columns SET client_visible = true WHERE sheet_id = $1",
                world.sheet,
            )

    asyncio.run(columns())


def test_ac_an_archived_engagements_sheet_refuses_writes(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    world = asyncio.run(_world(seed))
    sql, scope = _column_sql(world)

    async def archived() -> None:
        await app.as_actor(
            world.tenant, world.actor, sql, *scope, "recorded", "Recorded?", "single_select",
            "confidential",
        )  # fmt: skip
        await app.as_actor(
            world.tenant,
            world.actor,
            "INSERT INTO sheet_sections (tenant_id, engagement_id, work_item_id, sheet_id, "
            "section_key, title) VALUES ($1, $2, $3, $4, 'stratum_1', 'STRATUM 1')",
            *scope,
        )
        await seed.run(
            "UPDATE engagements SET status = 'archived' WHERE id = $1", world.engagement
        )
        writes = (
            (
                "INSERT INTO sheet_rows (tenant_id, engagement_id, work_item_id, sheet_id, "
                "row_key, section_key, source_ref, created_by) VALUES ($1, $2, $3, $4, 'r1', "
                "'stratum_1', $5::jsonb, $6)",
                *scope,
                json.dumps({"kind": "manual"}),
                world.person.user_id,
            ),
            ("UPDATE sheet_columns SET name = 'x' WHERE sheet_id = $1", world.sheet),
            ("UPDATE sheets SET title = 'x' WHERE id = $1", world.sheet),
        )
        for statement, *args in writes:
            with pytest.raises(asyncpg.PostgresError) as caught:
                await app.as_actor(world.tenant, world.actor, statement, *args)
            assert getattr(caught.value, "sqlstate", None) == "AB409", statement

    asyncio.run(archived())


def test_ac_forced_rls_isolates_two_tenants(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    first, second = asyncio.run(_world(seed)), asyncio.run(_world(seed))

    async def isolated() -> None:
        conn = await asyncpg.connect(_dsn(private_db.app_url))
        try:
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.tenant_id', $1, true)", str(first.tenant)
                )
                seen = await conn.fetch("SELECT id FROM sheets")
            assert {r["id"] for r in seen} == {first.sheet}
        finally:
            await conn.close()
        sql, scope = _column_sql(first)
        # The first tenant cannot write into the second tenant's sheet.
        with pytest.raises(asyncpg.PostgresError):
            await app.as_actor(
                first.tenant,
                first.actor,
                sql,
                first.tenant,
                second.engagement,
                second.item,
                second.sheet,
                "probe",
                "Probe",
                "text",
                "internal",
            )
        assert scope[0] == first.tenant

    asyncio.run(isolated())
