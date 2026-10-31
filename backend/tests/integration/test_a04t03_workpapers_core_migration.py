"""A-04-T03 (TASK-2710; A-04 §4.2 M1; DEC-1761): migration 0581, the workpaper core.

"up/down/up passes, every table has forced RLS and a work_item_id, the insert-only tables refuse
UPDATE and DELETE as the app role" (the row's acceptance). A workpaper made before 0581 keeps its
rows: its children are back-filled with the paper's engagement and work item, and an insert
after 0581 takes them from the paper whatever the caller sends.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from typing import cast

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Person, Seeder

BEFORE = "0580"
TABLES = (
    "workpapers",
    "workpaper_sections",
    "workpaper_cells",
    "workpaper_cell_citations",
    "workpaper_versions",
    "attention_flags",
    "attention_flag_events",
    "audit_procedures",
)
INSERT_ONLY = (
    "workpapers",
    "workpaper_sections",
    "workpaper_cells",
    "workpaper_cell_citations",
    "workpaper_versions",
    "attention_flag_events",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


class Paper:
    def __init__(self, tenant: uuid.UUID, engagement: uuid.UUID, item: uuid.UUID) -> None:
        self.tenant, self.engagement, self.item = tenant, engagement, item
        self.workpaper = uuid.uuid4()


async def _paper(seed: Seeder) -> tuple[Paper, Person]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    client = await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'assurance', 'Northwind 2025', $5) "
            "RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            person.user_id,
        ),
    )
    paper = Paper(tenant, engagement, item)
    await seed.run(
        "INSERT INTO workpapers (id, tenant_id, engagement_id, work_item_id, code, title, "
        "created_by) VALUES ($1, $2, $3, $4, 'GAP', 'General Audit Planning', $5)",
        paper.workpaper,
        tenant,
        engagement,
        item,
        person.user_id,
    )
    return paper, person


async def _legacy_children(seed: Seeder, paper: Paper, person: Person) -> None:
    """What SPEC-308 writes before 0581: a section, a cell and a version, with no scope."""
    await seed.run(
        "INSERT INTO workpaper_sections (tenant_id, workpaper_id, sheet_key, title, position) "
        "VALUES ($1, $2, 'planning', 'Planning', 0)",
        paper.tenant,
        paper.workpaper,
    )
    await seed.run(
        "INSERT INTO workpaper_cells (tenant_id, workpaper_id, cell_key, raw, set_by) "
        "VALUES ($1, $2, 'D2', '48600.00', $3)",
        paper.tenant,
        paper.workpaper,
        person.user_id,
    )
    await seed.run(
        "INSERT INTO workpaper_versions (tenant_id, workpaper_id, version_no, content_hash, "
        "content, created_by) VALUES ($1, $2, 1, $3, '{}'::jsonb, $4)",
        paper.tenant,
        paper.workpaper,
        "a" * 64,
        person.user_id,
    )


def test_ac_0581_goes_up_down_up_and_scopes_every_row(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    paper, person = asyncio.run(_paper(seed))
    asyncio.run(_legacy_children(seed, paper, person))
    migrate(private_db.owner_url, "0581")

    async def scoped() -> None:
        for table in ("workpaper_sections", "workpaper_cells", "workpaper_versions"):
            rows = await seed.rows(
                f"SELECT engagement_id, work_item_id FROM {table} WHERE workpaper_id = $1",  # noqa: S608 -- fixed tables
                paper.workpaper,
            )
            assert [(r["engagement_id"], r["work_item_id"]) for r in rows] == [
                (paper.engagement, paper.item)
            ], table

    asyncio.run(scoped())
    migrate(private_db.owner_url, BEFORE, down=True)
    migrate(private_db.owner_url, "head")
    asyncio.run(scoped())
    assert sc.check(private_db.owner_url, private_db.app_url) == []


def test_ac_every_table_forces_rls_and_carries_a_work_item(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def read() -> None:
        for table in TABLES:
            forced = await seed.value(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                "WHERE relname = $1 AND relnamespace = 'public'::regnamespace",
                table,
            )
            assert forced is True, table
            nullable = await seed.value(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = $1 AND column_name = $2",
                table,
                "work_item_id",
            )
            assert nullable == "NO", table

    asyncio.run(read())


def test_ac_the_insert_only_tables_refuse_update_and_delete_as_the_app(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    paper, person = asyncio.run(_paper(seed))
    actor = ("human", str(person.user_id))
    flag = uuid.uuid4()

    async def write() -> None:
        # The caller's scope is ignored: the workpaper's is written.
        await app.as_actor(
            paper.tenant,
            actor,
            "INSERT INTO attention_flags (id, tenant_id, workpaper_id, section_key, kind, text, "
            "created_by) VALUES ($1, $2, $3, 'service_organizations', 'pbc_gap', "
            "'SOC 1 report for Keystone not received', $4)",
            flag,
            paper.tenant,
            paper.workpaper,
            person.user_id,
        )
        await app.as_actor(
            paper.tenant,
            actor,
            "INSERT INTO attention_flag_events (tenant_id, workpaper_id, flag_id, event, "
            "actor_user_id) VALUES ($1, $2, $3, 'raised', $4)",
            paper.tenant,
            paper.workpaper,
            flag,
            person.user_id,
        )
        row = (
            await seed.rows(
                "SELECT engagement_id, work_item_id, created_by_kind FROM attention_flags "
                "WHERE id = $1",
                flag,
            )
        )[0]
        assert (row["engagement_id"], row["work_item_id"]) == (paper.engagement, paper.item)
        assert row["created_by_kind"] == "human"
        for table in INSERT_ONLY:
            key = "id" if table == "workpapers" else "workpaper_id"
            for statement in (
                f"UPDATE {table} SET tenant_id = tenant_id WHERE {key} = $1",  # noqa: S608 -- fixed tables
                f"DELETE FROM {table} WHERE {key} = $1",  # noqa: S608 -- fixed tables
            ):
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    await app.as_actor(paper.tenant, actor, statement, paper.workpaper)
        # A flag converts by its state columns alone, and is never deleted.
        await app.as_actor(
            paper.tenant,
            actor,
            "UPDATE attention_flags SET state = 'converted', converted_to_kind = 'request_item', "
            "converted_to_id = $2 WHERE id = $1",
            flag,
            uuid.uuid4(),
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.as_actor(
                paper.tenant, actor, "UPDATE attention_flags SET text = 'x' WHERE id = $1", flag
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await app.as_actor(
                paper.tenant, actor, "DELETE FROM attention_flags WHERE id = $1", flag
            )

    asyncio.run(write())


def test_ac_a_mandatory_procedure_is_never_tailored_and_a_tailoring_needs_its_reason(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    paper, person = asyncio.run(_paper(seed))

    async def procedures() -> None:
        template = uuid.uuid4()
        version = uuid.uuid4()
        await seed.run(
            "INSERT INTO methodology_templates (id, tenant_id, name, created_by, "
            "engagement_types) VALUES ($1, $2, 'BH EBP', $3, '{ebp_audit}')",
            template,
            paper.tenant,
            person.user_id,
        )
        await seed.run(
            "INSERT INTO methodology_versions (id, tenant_id, template_id, version, "
            "source_fingerprint, imported_by) VALUES ($1, $2, $3, 3, $4, $5)",
            version,
            paper.tenant,
            template,
            "e" * 64,
            person.user_id,
        )
        insert = (
            "INSERT INTO audit_procedures (tenant_id, engagement_id, work_item_id, "
            "methodology_version_id, program_step_key, level, mandatory, tailored, "
            "tailored_rationale, created_by) VALUES ($1, $2, $3, $4, $5, 'planning', $6, $7, $8, "
            "$9)"
        )
        args = (paper.tenant, paper.engagement, paper.item, version)
        with pytest.raises(asyncpg.CheckViolationError, match="mandatory_untailored"):
            await seed.run(insert, *args, "BH-EBP-110.4", True, True, "Not needed", person.user_id)
        with pytest.raises(asyncpg.CheckViolationError, match="tailored_reason"):
            await seed.run(insert, *args, "BH-EBP-120.2", False, True, None, person.user_id)
        await seed.run(insert, *args, "BH-EBP-120.2", False, True, "No IT", person.user_id)

    asyncio.run(procedures())
