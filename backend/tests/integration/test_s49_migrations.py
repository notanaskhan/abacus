"""S49: 0950 to 0954 go down to 0948 and back up. 0950 (C-02-T04, adjustments posting), 0951
(C-02-T05, W1 ledger write operations, grants and switches), 0952 (T-06-T10, tax entity depth),
0953 (T-06-T11, TB hand-offs) and 0954 (T-06-T12, relationship depth). Every new table comes back
with forced row-level security; the insert-only tables refuse the app role UPDATE and DELETE and
carry their immutable triggers; the CHECKs the engines and the posting rules rely on exist; the
head is single (0948 → 0954)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0948"
NEW_TABLES = (
    "posting_batches", "posting_results", "closing_date_events", "closing_date_conflicts",
    "ledger_write_operations", "ledger_write_evidence", "connection_write_grants",
    "firm_write_capabilities", "connection_engagement_settings",
    "tax_properties", "fixed_assets", "fixed_asset_versions", "fixed_asset_dispositions",
    "book_tax_items", "basis_schedules", "liability_shares", "state_apportionments",
    "sourcing_positions", "ptet_elections", "ptet_payments", "ptet_partner_credits",
    "nexus_facts",
    "tb_handoffs", "tb_handoff_supersessions", "tb_handoff_account_choices",
    "tb_handoff_schedules", "tb_handoff_tax_items",
    "external_parties", "entity_relationship_events", "relationship_graph_layouts",
)  # fmt: skip
INSERT_ONLY = (
    "posting_results", "closing_date_events", "ledger_write_evidence", "connection_write_grants",
    "firm_write_capabilities", "fixed_asset_versions", "fixed_asset_dispositions",
    "ptet_payments", "tb_handoffs", "tb_handoff_supersessions", "tb_handoff_account_choices",
    "tb_handoff_schedules", "tb_handoff_tax_items", "entity_relationship_events",
)  # fmt: skip
CONSTRAINTS = {
    # 0950: A-09's elimination clause kept verbatim, plus the client-ledger clause.
    ("proposed_entries", "pe_posting_dormant"): (
        "kind = 'elimination'",
        "posting_target = 'client_ledger'",
        "NOT is_attest_client",
        "posting_batch_id IS NOT NULL",
    ),
    ("proposed_entries", "pe_tje_never_batched"): ("'tje'", "posting_batch_id IS NULL"),
    ("fixed_assets", "fixed_assets_crossfoot"): ("accum_eop = (accum_bop + current_year)",),
    ("book_tax_items", "book_tax_items_foot"): ("((col_a + col_b) + col_c) = col_d",),
    ("entity_relationships", "entity_relationships_from_one_of"): ("from_external_party_id",),
}
TRIGGERS = (
    ("connection_write_grants", "connection_write_grants_not_attest"),
    ("posting_batches", "posting_batches_forward"),
    ("posting_batches", "posting_batches_poster"),
    ("entity_relationships", "entity_relationships_ownership_cap"),
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_0950_to_0954_go_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in NEW_TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in NEW_TABLES:
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        assert forced, table


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_insert_only_tables_refuse_update_and_delete(private_db: sc.Database, table: str) -> None:
    for privilege in ("UPDATE", "DELETE"):
        held = _value(
            private_db, f"SELECT has_table_privilege('abacus_app', '{table}', '{privilege}')"
        )
        assert held is False, (table, privilege)
    trigger = _value(
        private_db,
        "SELECT count(*) FROM pg_trigger WHERE tgrelid = $1::regclass AND tgname = $2",
        table,
        f"{table}_immutable",
    )
    assert trigger == 1, table


@pytest.mark.parametrize(("key", "parts"), sorted(CONSTRAINTS.items()), ids=str)
def test_the_checks_hold_their_rules(
    private_db: sc.Database, key: tuple[str, str], parts: tuple[str, ...]
) -> None:
    table, name = key
    definition = str(
        _value(
            private_db,
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = $1::regclass AND conname = $2",
            table,
            name,
        )
    )
    for part in parts:
        assert part in definition, (name, part, definition)


@pytest.mark.parametrize(("table", "name"), TRIGGERS)
def test_the_guard_triggers_exist(private_db: sc.Database, table: str, name: str) -> None:
    found = _value(
        private_db,
        "SELECT count(*) FROM pg_trigger WHERE tgrelid = $1::regclass AND tgname = $2",
        table,
        name,
    )
    assert found == 1


def test_the_head_reaches_0954(private_db: sc.Database) -> None:
    """0954 is on the single head's line (S50's 0960+ build on it)."""
    scripts = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    )
    head = str(_value(private_db, "SELECT version_num FROM alembic_version"))
    assert head == scripts.get_current_head()
    assert {"0950", "0951", "0952", "0953", "0954"} <= {
        r.revision for r in scripts.walk_revisions("base", head)
    }


STAFF_TABLES = ("platform_staff_sessions", "platform_staff_session_cookies")


def test_0969_staff_sessions_go_down_and_up_with_no_app_privileges(
    private_db: sc.Database,
) -> None:
    """G-04-T14 (TASK-8548): the console's staff-session tables are reached only by definers."""
    migrate(private_db.owner_url, "0968", down=True)
    for table in STAFF_TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in STAFF_TABLES:
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            held = _value(
                private_db, f"SELECT has_table_privilege('abacus_app', '{table}', '{privilege}')"
            )
            assert held is False, (table, privilege)
    definers = _value(
        private_db,
        "SELECT count(*) FROM pg_proc WHERE proname LIKE 'platform_staff_session_%' "
        "AND prosecdef AND has_function_privilege('abacus_app', oid, 'EXECUTE')",
    )
    assert definers == 5
