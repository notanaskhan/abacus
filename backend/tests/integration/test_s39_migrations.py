"""S39: 0840 (P-02-T05, the firm search index) goes down to 0832 and back up with forced row-level
security; the app role reads only its own tenant's search documents and recents; the CHECKs keep
a scoped document naming its client, engagement or owner; the index carries the GIN tsv and
trigram indexes; `search_documents` stays out of `archived_guard()` (a rebuildable projection).

Row acceptance (P-02-T05): "The single-head check passes, an RLS test isolates two tenants on both
tables, and the migration merges in the Tue Apr 25, 2028 train after the freeze window."
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

BEFORE = "0832"
TABLES = ("search_documents", "search_recents")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def _app_dsn(database: sc.Database) -> str:
    return database.app_url.replace("postgresql+asyncpg://", "postgresql://")


async def _app_count(database: sc.Database, tenant_id: uuid.UUID, table: str) -> int:
    connection = await asyncpg.connect(_app_dsn(database))
    try:
        async with connection.transaction():
            await connection.execute(
                "SELECT set_config('app.tenant_id', $1, true)", str(tenant_id)
            )
            sql = f"SELECT count(*) FROM {table}"  # noqa: S608 -- a fixed table name
            return int(await connection.fetchval(sql))
    finally:
        await connection.close()


def test_0840_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        assert forced, table


def test_the_index_has_its_gin_and_trigram_indexes(private_db: sc.Database) -> None:
    for name, method in (
        ("search_documents_tsv", "gin"),
        ("search_documents_title_trgm", "gin"),
        ("search_documents_identifiers_text_trgm", "gin"),
        ("search_documents_related_text_trgm", "gin"),
    ):
        found = _value(
            private_db,
            "SELECT am.amname FROM pg_class c JOIN pg_am am ON am.oid = c.relam "
            "WHERE c.relname = $1",
            name,
        )
        assert found == method, name
    for extension in ("pg_trgm", "btree_gin"):
        assert _value(
            private_db, "SELECT count(*) FROM pg_extension WHERE extname = $1", extension
        )


def test_search_documents_is_out_of_the_archived_guard(private_db: sc.Database) -> None:
    triggers = _value(
        private_db,
        "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE c.relname = 'search_documents' AND t.tgname = 'archived_guard'",
    )
    assert triggers == 0


def test_two_tenants_are_isolated_on_both_tables(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def seed_both() -> tuple[uuid.UUID, uuid.UUID]:
        tenants = (await seed.firm(), await seed.firm())
        for tenant in tenants:
            person = await seed.person(tenant)
            await seed.run(
                "INSERT INTO search_documents (tenant_id, object_type, object_id, group_key, "
                "scope_kind, client_id, title, tsv, source_updated_at) VALUES ($1, 'client', $2, "
                "'clients', 'client', $3, 'Jonah & Claire Feld', "
                "to_tsvector('simple', 'Jonah & Claire Feld'), now())",
                tenant,
                uuid.uuid4(),
                uuid.uuid4(),
            )
            await seed.run(
                "INSERT INTO search_recents (tenant_id, user_id, object_type, object_id) "
                "VALUES ($1, $2, 'client', $3)",
                tenant,
                person.user_id,
                uuid.uuid4(),
            )
        return tenants

    a, b = asyncio.run(seed_both())
    for table in TABLES:
        assert asyncio.run(_app_count(private_db, a, table)) == 1, table
        assert asyncio.run(_app_count(private_db, b, table)) == 1, table
        assert asyncio.run(_app_count(private_db, uuid.uuid4(), table)) == 0, table


_INSERT = (
    "INSERT INTO search_documents (tenant_id, object_type, object_id, group_key, scope_kind, "
    "client_id, title, tsv, source_updated_at) VALUES ($1, 'probe', $2, 'clients', $3, $4, 'x', "
    "to_tsvector('simple', 'x'), now())"
)


@pytest.mark.parametrize(
    ("scope", "with_client", "constraint"),
    [
        ("client", False, "search_documents_client_scoped"),
        ("engagement", True, "search_documents_engagement_scoped"),
        ("own", False, "search_documents_owner_scoped"),
    ],
)
def test_a_scoped_document_names_its_scope(
    private_db: sc.Database, scope: str, with_client: bool, constraint: str
) -> None:
    seed = Seeder(private_db.superuser_dsn)

    async def insert() -> None:
        tenant = await seed.firm()
        client = uuid.uuid4() if with_client else None
        await seed.run(_INSERT, tenant, uuid.uuid4(), scope, client)

    with pytest.raises(asyncpg.CheckViolationError, match=constraint):
        asyncio.run(insert())


def test_no_column_could_hold_a_tin_amount_or_document_text(private_db: sc.Database) -> None:
    columns = asyncio.run(
        Seeder(private_db.superuser_dsn).rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'search_documents'"
        )
    )
    names = {str(c["column_name"]) for c in columns}
    for banned in ("tin", "tin_last4", "amount", "body", "text_content", "content"):
        assert banned not in names


# --- 0841 (T-05-T25): the adjustments tax layers -------------------------------------------------


def test_0841_lines_carry_their_account_scope(private_db: sc.Database) -> None:
    definition = str(
        _value(
            private_db,
            "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
            "JOIN pg_class t ON t.oid = c.conrelid WHERE t.relname = 'proposed_entry_lines' "
            "AND pg_get_constraintdef(c.oid) LIKE '%account_scope%'",
        )
    )
    assert "book" in definition and "tax_only" in definition
    assert _value(
        private_db,
        "SELECT has_column_privilege('abacus_app', 'proposed_entry_lines', 'account_scope', "
        "'INSERT')",
    )


def test_0841_the_tax_scope_triggers_guard_tjes_and_tax_only_lines(
    private_db: sc.Database,
) -> None:
    for table in ("proposed_entries", "proposed_entry_lines"):
        found = _value(
            private_db,
            "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE c.relname = $1 AND t.tgname = $2",
            table,
            f"{table}_tax_scope",
        )
        assert found == 1, table
    body = str(
        _value(private_db, "SELECT prosrc FROM pg_proc WHERE proname = 'proposed_entry_tax_scope'")
    )
    assert "tax_return" in body and "tax_only" in body


def test_0842_mapping_sets_carry_one_taxonomy_target(private_db: sc.Database) -> None:
    names = {
        str(r["conname"])
        for r in asyncio.run(
            Seeder(private_db.superuser_dsn).rows(
                "SELECT conname FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
                "WHERE t.relname IN ('mapping_sets', 'mapping_set_edits')"
            )
        )
    }
    assert {"mapping_sets_one_taxonomy_target", "mapping_sets_one_per_taxonomy"} <= names
    assert "mapping_set_edits_one_target" in names
    assert "mapping_sets_tenant_id_trial_balance_id_key" not in names
    assert _value(
        private_db,
        "SELECT count(*) FROM pg_trigger WHERE tgname = 'mapping_set_edits_taxonomy'",
    )
