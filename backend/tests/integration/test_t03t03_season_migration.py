"""T-03-T03 (TASK-3202; DEC-2202): migration 0655, the organizer editor and the tax schedules.

Row acceptance: "schema_check passes up/down/up, generated tenancy tests pass, and trigger tests
show a published template version, an answer, an effect row and an approved payment cannot
change." Down to 0654 removes the five new tables and the editor columns; up again restores them
with forced row-level security; the triggers refuse the four changes even to the owner role.
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

from .agent_tests.support import Seeder

BEFORE = "0654"
NEW_TABLES = (
    "answer_effects",
    "filing_extensions",
    "extension_payments",
    "estimate_schedules",
    "estimate_installments",
)
EDITOR_COLUMNS = (
    ("questionnaire_templates", "owner_id"),
    ("questionnaire_template_versions", "status"),
    ("questionnaires", "owner_kind"),
    ("questions", "internal_helper"),
    ("answer_versions", "question_wording_hash"),
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def _column(database: sc.Database, table: str, column: str) -> bool:
    return bool(
        _value(
            database,
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
            "WHERE table_name = $1 AND column_name = $2)",
            table,
            column,
        )
    )


def test_ac3_0655_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in NEW_TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    for table, column in EDITOR_COLUMNS:
        assert not _column(private_db, table, column), (table, column)
    migrate(private_db.owner_url, "head")
    for table in NEW_TABLES:
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        assert forced, table
    for table, column in EDITOR_COLUMNS:
        assert _column(private_db, table, column), (table, column)


@pytest.mark.parametrize("table", NEW_TABLES)
def test_ac3_the_app_role_never_deletes_or_writes_whole_rows(
    private_db: sc.Database, table: str
) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'INSERT')")
    assert _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'INSERT')"
    )


def test_ac3_an_effect_row_is_never_updated_by_the_app(private_db: sc.Database) -> None:
    assert not _value(
        private_db, "SELECT has_any_column_privilege('abacus_app', 'answer_effects', 'UPDATE')"
    )


async def _template_structure(seed: Seeder) -> dict[str, uuid.UUID]:
    """A template, a template-owned questionnaire, a section, a question and its version."""
    tenant = await seed.firm()
    person = await seed.person(tenant)
    ids = {"tenant": tenant, "person": person.user_id}
    ids["template"] = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO questionnaire_templates (tenant_id, name, created_by, key, form_family) "
            "VALUES ($1, '1040 organizer', $2, 'organizer_1040', '1040') RETURNING id",
            tenant,
            person.user_id,
        ),
    )
    ids["questionnaire"] = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO questionnaires (tenant_id, kind, title, created_by, owner_kind) "
            "VALUES ($1, 'organizer', '1040 organizer v6', $2, 'template_version') RETURNING id",
            tenant,
            person.user_id,
        ),
    )
    ids["section"] = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO questionnaire_sections (tenant_id, questionnaire_id, name, position, "
            "key) VALUES ($1, $2, 'Payments & refunds', 0, 'payments') RETURNING id",
            tenant,
            ids["questionnaire"],
        ),
    )
    ids["question"] = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO questions (tenant_id, questionnaire_id, section_id, question_key, "
            "position, type, client_wording, origin, created_by, required) VALUES ($1, $2, $3, "
            "'q5', 0, 'yes_no', 'Did you make 2025 estimated tax payments?', 'template', $4, "
            "true) RETURNING id",
            tenant,
            ids["questionnaire"],
            ids["section"],
            person.user_id,
        ),
    )
    ids["version"] = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO questionnaire_template_versions (tenant_id, template_id, version, "
            "imported_by, status, questionnaire_id, drafted_by) "
            "VALUES ($1, $2, 6, $3, 'draft', $4, $3) RETURNING id",
            tenant,
            ids["template"],
            person.user_id,
            ids["questionnaire"],
        ),
    )
    return ids


async def _refused(seed: Seeder, sql: str, *args: object) -> bool:
    try:
        await seed.run(sql, *args)
    except asyncpg.InsufficientPrivilegeError:
        return True
    return False


def test_ac3_a_published_version_and_its_questions_never_change(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _template_structure(seed)
        # A draft takes edits.
        await seed.run(
            "UPDATE questions SET client_wording = 'Did you pay 2025 estimates?' WHERE id = $1",
            ids["question"],
        )
        await seed.run(
            "UPDATE questionnaire_template_versions SET status = 'published', "
            "applies_to_tax_year = 2026, published_by = $2, published_at = now(), "
            "published_actor_kind = 'human' WHERE id = $1",
            ids["version"],
            ids["person"],
        )
        assert await _refused(
            seed,
            "UPDATE questionnaire_template_versions SET change_summary = 'x' WHERE id = $1",
            ids["version"],
        )
        assert await _refused(
            seed, "DELETE FROM questionnaire_template_versions WHERE id = $1", ids["version"]
        )
        assert await _refused(
            seed, "UPDATE questions SET required = false WHERE id = $1", ids["question"]
        )
        assert await _refused(
            seed, "UPDATE questionnaire_sections SET name = 'x' WHERE id = $1", ids["section"]
        )

    asyncio.run(scenario())


def test_ac3_publishing_needs_a_tax_year_and_a_human(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _template_structure(seed)
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "UPDATE questionnaire_template_versions SET status = 'published', "
                "published_actor_kind = 'human' WHERE id = $1",
                ids["version"],
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "UPDATE questionnaire_template_versions SET status = 'published', "
                "applies_to_tax_year = 2026, published_actor_kind = 'agent' WHERE id = $1",
                ids["version"],
            )

    asyncio.run(scenario())


def test_ac3_one_draft_per_template(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _template_structure(seed)
        with pytest.raises(asyncpg.UniqueViolationError):
            await seed.run(
                "INSERT INTO questionnaire_template_versions (tenant_id, template_id, version, "
                "imported_by, status, questionnaire_id, drafted_by) "
                "VALUES ($1, $2, 7, $3, 'draft', $4, $3)",
                ids["tenant"],
                ids["template"],
                ids["person"],
                ids["questionnaire"],
            )

    asyncio.run(scenario())


def test_ac3_an_answer_and_an_effect_row_never_change(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _template_structure(seed)
        answer = await seed.value(
            "INSERT INTO answer_versions (tenant_id, question_id, value, version_no, "
            "answered_by) VALUES ($1, $2, '\"yes\"', 1, $3) RETURNING id",
            ids["tenant"],
            ids["question"],
            ids["person"],
        )
        effect = await seed.value(
            "INSERT INTO answer_effects (tenant_id, answer_id, question_id, rule_key, "
            "effect_kind, actor_kind) VALUES ($1, $2, $3, 'q5_confirmations', "
            "'pending_handler', 'system') RETURNING id",
            ids["tenant"],
            answer,
            ids["question"],
        )
        assert await _refused(
            seed, "UPDATE answer_versions SET value = 'null' WHERE id = $1", answer
        )
        assert await _refused(
            seed,
            "UPDATE answer_effects SET effect_kind = 'review_point_raised' WHERE id = $1",
            effect,
        )
        assert await _refused(seed, "DELETE FROM answer_effects WHERE id = $1", effect)
        with pytest.raises(asyncpg.UniqueViolationError):  # once per answer and rule
            await seed.run(
                "INSERT INTO answer_effects (tenant_id, answer_id, question_id, rule_key, "
                "effect_kind, actor_kind) VALUES ($1, $2, $3, 'q5_confirmations', "
                "'pending_handler', 'system')",
                ids["tenant"],
                answer,
                ids["question"],
            )

    asyncio.run(scenario())


async def _extension(seed: Seeder) -> dict[str, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    client = await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', 'Feld 2025 1040', $5) "
            "RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            person.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, form, "
        "tax_year) VALUES ($1, $2, $3, $4, '1040', 2025) ON CONFLICT DO NOTHING",
        tenant,
        item,
        engagement,
        entity,
    )
    extension = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO filing_extensions (tenant_id, engagement_id, work_item_id, "
            "tax_return_id, tax_year, jurisdiction, form, original_due_on, extended_due_on, "
            "created_by) "
            "VALUES ($1, $2, $3, $3, 2025, 'US', '4868', '2026-04-15', '2026-10-15', $4) "
            "RETURNING id",
            tenant,
            engagement,
            item,
            person.user_id,
        ),
    )
    payment = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO extension_payments (tenant_id, filing_extension_id, kind, amount, "
            "proposed_by) VALUES ($1, $2, 'extension_payment', 10000.00, $3) RETURNING id",
            tenant,
            extension,
            person.user_id,
        ),
    )
    return {"tenant": tenant, "person": person.user_id, "extension": extension, "payment": payment}


def test_ac3_an_approved_payment_never_changes(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _extension(seed)
        await seed.run(
            "UPDATE extension_payments SET amount = 10500.00 WHERE id = $1", ids["payment"]
        )  # before approval a proposal may still change
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "UPDATE extension_payments SET approved_by = $2, approved_at = now(), "
                "approved_actor_kind = 'agent' WHERE id = $1",
                ids["payment"],
                ids["person"],
            )
        await seed.run(
            "UPDATE extension_payments SET approved_by = $2, approved_at = now(), "
            "approved_actor_kind = 'human' WHERE id = $1",
            ids["payment"],
            ids["person"],
        )
        assert await _refused(
            seed, "UPDATE extension_payments SET amount = 9000.00 WHERE id = $1", ids["payment"]
        )
        assert await _refused(seed, "DELETE FROM extension_payments WHERE id = $1", ids["payment"])
        # Recording the paid date once is allowed; changing it later is not.
        await seed.run(
            "UPDATE extension_payments SET paid_on = '2026-04-14' WHERE id = $1", ids["payment"]
        )
        assert await _refused(
            seed,
            "UPDATE extension_payments SET paid_on = '2026-04-15' WHERE id = $1",
            ids["payment"],
        )

    asyncio.run(scenario())


def test_ac3_a_rejected_extension_carries_its_code(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _extension(seed)
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "UPDATE filing_extensions SET status = 'rejected', filed_on = '2026-04-14', "
                "filed_recorded_by = $2 WHERE id = $1",
                ids["extension"],
                ids["person"],
            )

    asyncio.run(scenario())


def test_ac3_the_schema_check_registers_the_new_tables() -> None:
    from abacus.modules.requests import registry as requests_registry
    from abacus.modules.tax import registry as tax_registry

    assert "answer_effects" in requests_registry.INSERT_ONLY
    assert {"filing_extensions", "extension_payments", "estimate_schedules"} <= tax_registry.TABLES
    assert sc.IMMUTABLE_TABLES["answer_effects"] == "t03_frozen_row"
