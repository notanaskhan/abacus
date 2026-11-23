"""K-03-T11 (TASK-8901; SPEC-720 §4; K-03 §4.2): migration 1010, templates v2 core.

"The migration goes up/down/up on testcontainers, a published version or its components refuse
UPDATE and DELETE, and every published methodology version gets exactly one published
template-version wrapper" (the row's acceptance).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Person, Seeder

BEFORE = "1003"
TABLES = (
    "engagement_templates",
    "template_versions",
    "template_sheet_definitions",
    "template_sheet_columns",
    "template_sheet_views",
    "template_agent_column_defs",
    "template_forms",
    "template_form_fields",
    "scoping_rules",
    "template_requests",
    "template_trigger_defaults",
    "template_report_template_refs",
    "template_skill_pins",
    "template_changes",
    "agent_skills",
    "agent_skill_versions",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _methodology(
    seed: Seeder, states: tuple[str, ...]
) -> tuple[uuid.UUID, Person, uuid.UUID, list[uuid.UUID]]:
    """A firm with one methodology template and one version per state, in order."""
    tenant = await seed.firm()
    person = await seed.person(tenant)
    template = uuid.uuid4()
    await seed.run(
        "INSERT INTO methodology_templates (id, tenant_id, name, created_by, engagement_types, "
        "family) VALUES ($1, $2, 'BH Audit Methodology · FS', $3, '{audit}', 'fs')",
        template,
        tenant,
        person.user_id,
    )
    versions: list[uuid.UUID] = []
    for number, state in enumerate(states, start=1):
        version = uuid.uuid4()
        await seed.run(
            "INSERT INTO methodology_versions (id, tenant_id, template_id, version, "
            "source_fingerprint, imported_by, label) VALUES ($1, $2, $3, $4, $5, $6, $7)",
            version,
            tenant,
            template,
            number,
            f"{number:x}" * 64,
            person.user_id,
            f"FS v{number}",
        )
        await seed.run(
            "INSERT INTO methodology_version_states (tenant_id, version_id, template_id, status, "
            "effective_from, approval_basis) VALUES ($1, $2, $3, $4, "
            "CASE WHEN $4 IN ('published', 'superseded') THEN DATE '2026-07-01' END, "
            "CASE WHEN $4 IN ('published', 'superseded') THEN 'legacy_import' END)",
            tenant,
            version,
            template,
            state,
        )
        versions.append(version)
    return tenant, person, template, versions


def test_ac_up_down_up_and_one_wrapper_per_published_version(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    tenant, _, template, (v1, v2, v3) = asyncio.run(
        _methodology(seed, ("superseded", "published", "draft"))
    )
    migrate(private_db.owner_url, "head")

    async def wrappers() -> None:
        templates = await seed.rows(
            "SELECT id, name, family, service_line FROM engagement_templates "
            "WHERE tenant_id = $1 AND methodology_template_id = $2",
            tenant,
            template,
        )
        assert [(r["name"], r["family"], r["service_line"]) for r in templates] == [
            ("BH Audit Methodology · FS", "fs", "audit")
        ]
        rows = await seed.rows(
            "SELECT methodology_version_id, seq, label, status, origin, retired_at IS NOT NULL "
            "AS retired FROM template_versions WHERE tenant_id = $1 ORDER BY seq",
            tenant,
        )
        assert [
            (r["methodology_version_id"], r["seq"], r["label"], r["status"], r["retired"])
            for r in rows
        ] == [(v1, 1, "FS v1", "published", True), (v2, 2, "FS v2", "published", False)]
        assert {r["origin"] for r in rows} == {"bootstrap"}
        assert v3 not in {r["methodology_version_id"] for r in rows}  # a draft is not wrapped

    asyncio.run(wrappers())
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert asyncio.run(seed.value("SELECT to_regclass($1) IS NULL", table)), table
    migrate(private_db.owner_url, "head")
    asyncio.run(wrappers())
    forced = asyncio.run(
        seed.value(
            "SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class "
            "WHERE relnamespace = 'public'::regnamespace AND relname = ANY($1::text[])",
            [*TABLES, "methodology_templates", "methodology_versions", "engagements"],
        )
    )
    assert forced is True
    assert sc.check(private_db.owner_url, private_db.app_url) == []


def test_ac_a_pinned_draft_version_is_wrapped_too(private_db: sc.Database) -> None:
    """Every existing pin gets a template version, even one on a version never published."""
    seed = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    tenant, person, _, (v1,) = asyncio.run(_methodology(seed, ("needs_review",)))

    async def pin() -> None:
        entity = await seed.entity(tenant)
        engagement = await seed.engagement(tenant, entity, person.user_id)
        await seed.run(
            "UPDATE engagements SET methodology_version_id = $2 WHERE id = $1", engagement, v1
        )

    asyncio.run(pin())
    migrate(private_db.owner_url, "head")
    rows = asyncio.run(
        seed.rows(
            "SELECT status, change_summary->>'methodology_state' AS state FROM template_versions "
            "WHERE tenant_id = $1 AND methodology_version_id = $2",
            tenant,
            v1,
        )
    )
    assert [(r["status"], r["state"]) for r in rows] == [("published", "needs_review")]


async def _draft_with_components(
    app: Seeder, seed: Seeder, tenant: uuid.UUID, person: Person
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    template = await seed.value("SELECT id FROM engagement_templates WHERE tenant_id = $1", tenant)
    actor = ("human", str(person.user_id))
    draft = uuid.uuid4()
    await app.as_actor(
        tenant,
        actor,
        "INSERT INTO template_versions (id, tenant_id, template_id, seq, label, created_by) "
        "VALUES ($1, $2, $3, 3, 'FS v6', $4)",
        draft,
        tenant,
        template,
        person.user_id,
    )
    sheet, column = uuid.uuid4(), uuid.uuid4()
    await app.as_actor(
        tenant,
        actor,
        "INSERT INTO template_sheet_definitions (id, tenant_id, template_version_id, sheet_key, "
        "title, step_key, row_source) VALUES ($1, $2, $3, 'BH-FS-430', "
        "'Search for Unrecorded Liabilities', '430', 'sample_set')",
        sheet,
        tenant,
        draft,
    )
    await app.as_actor(
        tenant,
        actor,
        "INSERT INTO template_sheet_columns (id, tenant_id, template_version_id, "
        "sheet_definition_id, column_key, name, type, classification) "
        "VALUES ($1, $2, $3, $4, 'recorded', 'Recorded in period?', 'single_select', "
        "'confidential')",
        column,
        tenant,
        draft,
        sheet,
    )
    return draft, sheet, column


def test_ac_a_published_version_and_its_components_refuse_update_and_delete(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    migrate(private_db.owner_url, BEFORE, down=True)
    tenant, person, _, _ = asyncio.run(_methodology(seed, ("published",)))
    migrate(private_db.owner_url, "head")
    actor = ("human", str(person.user_id))

    async def lifecycle() -> None:
        draft, sheet, column = await _draft_with_components(app, seed, tenant, person)
        # A draft's components move freely.
        await app.as_actor(
            tenant, actor, "UPDATE template_sheet_columns SET name = 'Recorded?' WHERE id = $1",
            column,
        )  # fmt: skip
        # A second draft of the same template is refused (one draft per template).
        template = await seed.value(
            "SELECT template_id FROM template_versions WHERE id = $1", draft
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await app.as_actor(
                tenant,
                actor,
                "INSERT INTO template_versions (tenant_id, template_id, seq, label, created_by) "
                "VALUES ($1, $2, 4, 'FS v7', $3)",
                tenant,
                template,
                person.user_id,
            )
        # Publish.
        await app.as_actor(
            tenant,
            actor,
            "UPDATE template_versions SET status = 'published', effective_from = DATE "
            "'2026-10-01', fingerprint = $2, published_by = $3, published_at = now() "
            "WHERE id = $1",
            draft,
            "c" * 64,
            person.user_id,
        )
        refused = (
            ("UPDATE template_versions SET label = 'FS v6b' WHERE id = $1", draft),
            ("UPDATE template_versions SET fingerprint = $2 WHERE id = $1", draft, "d" * 64),
            ("DELETE FROM template_versions WHERE id = $1", draft),
            ("UPDATE template_sheet_columns SET name = 'x' WHERE id = $1", column),
            ("DELETE FROM template_sheet_columns WHERE id = $1", column),
            ("UPDATE template_sheet_definitions SET title = 'x' WHERE id = $1", sheet),
            ("DELETE FROM template_sheet_definitions WHERE id = $1", sheet),
            (
                "INSERT INTO scoping_rules (tenant_id, template_version_id, position, "
                "conditions, effect, target_kind, target_ref) VALUES ($2, $1, 1, "
                '\'[{"source_path": "x", "operator": "is", "value": 1}]\', \'show\', '
                "'step', '430')",
                draft,
                tenant,
            ),
        )
        for statement, *args in refused:
            with pytest.raises(asyncpg.PostgresError) as caught:
                await app.as_actor(tenant, actor, statement, *args)
            assert getattr(caught.value, "sqlstate", None) == "AB409", statement
        # Deprecate and retire still move.
        await app.as_actor(
            tenant,
            actor,
            "UPDATE template_versions SET status = 'deprecated', deprecated_by = $2, "
            "deprecated_at = now(), retired_at = now() WHERE id = $1",
            draft,
            person.user_id,
        )
        with pytest.raises(asyncpg.PostgresError):  # never back to published
            await app.as_actor(
                tenant, actor, "UPDATE template_versions SET status = 'published' WHERE id = $1",
                draft,
            )  # fmt: skip

    asyncio.run(lifecycle())


def test_ac_a_draft_discarded_takes_its_components(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    migrate(private_db.owner_url, BEFORE, down=True)
    tenant, person, _, _ = asyncio.run(_methodology(seed, ("published",)))
    migrate(private_db.owner_url, "head")
    actor = ("human", str(person.user_id))

    async def discard() -> None:
        draft, _, _ = await _draft_with_components(app, seed, tenant, person)
        await app.as_actor(tenant, actor, "DELETE FROM template_versions WHERE id = $1", draft)
        assert (
            await seed.value(
                "SELECT count(*) FROM template_sheet_columns WHERE template_version_id = $1",
                draft,
            )
            == 0
        )

    asyncio.run(discard())


def test_ac_a_column_needs_a_classification_and_one_of_eleven_types(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    migrate(private_db.owner_url, BEFORE, down=True)
    tenant, person, _, _ = asyncio.run(_methodology(seed, ("published",)))
    migrate(private_db.owner_url, "head")
    actor = ("human", str(person.user_id))

    async def columns() -> None:
        draft, sheet, _ = await _draft_with_components(app, seed, tenant, person)
        base = (
            "INSERT INTO template_sheet_columns (tenant_id, template_version_id, "
            "sheet_definition_id, column_key, name, type, classification) "
            "VALUES ($1, $2, $3, $4, 'Probe', $5, $6)"
        )
        with pytest.raises(asyncpg.NotNullViolationError):
            await app.as_actor(tenant, actor, base, tenant, draft, sheet, "a", "text", None)
        with pytest.raises(asyncpg.CheckViolationError):
            await app.as_actor(
                tenant, actor, base, tenant, draft, sheet, "b", "formula", "internal"
            )

    asyncio.run(columns())


def test_ac_skill_versions_and_change_lists_are_insert_only(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    app = Seeder(_dsn(private_db.app_url))
    tenant = asyncio.run(seed.firm())
    person = asyncio.run(seed.person(tenant))
    actor = ("human", str(person.user_id))

    async def skills() -> None:
        skill, version = uuid.uuid4(), uuid.uuid4()
        await app.as_actor(
            tenant,
            actor,
            "INSERT INTO agent_skills (id, tenant_id, skill_key, name, created_by) "
            "VALUES ($1, $2, 'BH-SK-430', 'Unrecorded liabilities reviewer', $3)",
            skill,
            tenant,
            person.user_id,
        )
        await app.as_actor(
            tenant,
            actor,
            "INSERT INTO agent_skill_versions (id, tenant_id, skill_id, version, status, body_md, "
            "body_sha256, source, created_by, published_by, published_at) VALUES ($1, $2, $3, 2, "
            "'published', '# Skill', $4, 'imported', $5, $5, now())",
            version,
            tenant,
            skill,
            "e" * 64,
            person.user_id,
        )
        for statement, target in (
            ("UPDATE agent_skill_versions SET body_md = 'x' WHERE id = $1", version),
            ("DELETE FROM agent_skill_versions WHERE id = $1", version),
            ("UPDATE agent_skills SET name = 'x' WHERE id = $1", skill),
            ("DELETE FROM template_changes WHERE id = $1", uuid.uuid4()),
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await app.as_actor(tenant, actor, statement, target)

    asyncio.run(skills())
