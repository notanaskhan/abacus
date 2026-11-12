"""S38: 0830 (T-05-T20, the tax workbook and the preparer memo) and 0831 (T-05-T22, partner
TINs) go down to 0821 and back up with forced row-level security; the app role never deletes;
insert-only rows are never updated (the trigger refuses even a superuser); inserts are
column-granted; a formula cell carries its formula; adopting and approving a memo are a person's
events; a partner TIN is sealed, never plain.

Row acceptance (T-05-T20): "The cell store accepts formula cells only through record_value, and
memo versions refuse UPDATE and DELETE."
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0821"
TABLES = (
    "preparer_memos",
    "preparer_memo_versions",
    "preparer_memo_events",
    "planning_opportunities",
    "partner_tin_reveals",
)
INSERT_ONLY = ("preparer_memo_versions", "preparer_memo_events", "partner_tin_reveals")


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


def test_0830_and_0831_go_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    assert not _column(private_db, "workpaper_cells", "formula")
    assert not _column(private_db, "workpaper_versions", "engine_manifest")
    assert not _column(private_db, "partners", "tin_sealed")
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        assert forced, table
    for table, column in (
        ("workpaper_cells", "formula"),
        ("workpaper_cells", "formula_inputs"),
        ("workpaper_cells", "engine_name"),
        ("workpaper_cells", "engine_version"),
        ("workpaper_versions", "engine_manifest"),
        ("workpaper_versions", "inputs_hash"),
        ("partners", "tin_sealed"),
        ("partners", "tin_last4"),
        ("partners", "tin_kind"),
    ):
        assert _column(private_db, table, column), (table, column)


@pytest.mark.parametrize("table", TABLES)
def test_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_an_insert_only_row_is_never_updated(private_db: sc.Database, table: str) -> None:
    assert not _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'UPDATE')"
    )
    assert _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'INSERT')"
    )
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'INSERT')")


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_memo_versions_and_events_refuse_update_and_delete_even_for_a_superuser(
    private_db: sc.Database, table: str
) -> None:
    triggers = _value(
        private_db,
        "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "WHERE c.relname = $1 AND t.tgname = $2 AND t.tgenabled <> 'D'",
        table,
        f"{table}_immutable",
    )
    assert triggers == 1
    events = asyncio.run(
        Seeder(private_db.superuser_dsn).rows(
            "SELECT event_manipulation, action_timing FROM information_schema.triggers "
            "WHERE event_object_table = $1 AND trigger_name = $2",
            table,
            f"{table}_immutable",
        )
    )
    assert {(e["event_manipulation"], e["action_timing"]) for e in events} == {
        ("UPDATE", "BEFORE"),
        ("DELETE", "BEFORE"),
    }
    # The trigger raises for every row, whoever runs the statement (the function body).
    function = (
        "partner_tin_reveals_immutable"
        if table == "partner_tin_reveals"
        else "preparer_memo_rows_immutable"
    )
    body = str(_value(private_db, "SELECT prosrc FROM pg_proc WHERE proname = $1", function))
    assert "RAISE EXCEPTION" in body and "insert-only" in body


def test_a_formula_cell_must_carry_its_formula(private_db: sc.Database) -> None:
    definition = str(
        _value(
            private_db,
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'workpaper_cells_formula_source'",
        )
    )
    assert "formula" in definition and "IS NOT NULL" in definition
    # The cells stay insert-only (0072): every value goes through `review.api.record_value`.
    assert not _value(
        private_db, "SELECT has_any_column_privilege('abacus_app', 'workpaper_cells', 'UPDATE')"
    )
    assert _value(
        private_db,
        "SELECT has_column_privilege('abacus_app', 'workpaper_cells', 'formula', 'INSERT')",
    )


def test_tax_workbook_is_a_workpaper_kind(private_db: sc.Database) -> None:
    definition = str(
        _value(
            private_db,
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'workpapers_kind_check'",
        )
    )
    assert "tax_workbook" in definition and "ebp_plan" in definition


def test_adopting_and_approving_a_memo_are_a_persons_events(private_db: sc.Database) -> None:
    definition = " ".join(
        str(d)
        for d in asyncio.run(
            Seeder(private_db.superuser_dsn).rows(
                "SELECT pg_get_constraintdef(c.oid) AS d FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid WHERE t.relname = 'preparer_memo_events'"
            )
        )
    )
    assert "adopted" in definition and "approved" in definition and "human" in definition


def test_planning_opportunities_are_open_only_in_t05(private_db: sc.Database) -> None:
    definition = " ".join(
        str(d)
        for d in asyncio.run(
            Seeder(private_db.superuser_dsn).rows(
                "SELECT pg_get_constraintdef(c.oid) AS d FROM pg_constraint c "
                "JOIN pg_class t ON t.oid = c.conrelid WHERE t.relname = 'planning_opportunities'"
            )
        )
    )
    assert "'open'" in definition and "raised" not in definition


def test_a_partner_tin_is_sealed_never_plain(private_db: sc.Database) -> None:
    """0831: the TIN is an envelope plus its last four and kind, all three or none."""
    kinds = _value(
        private_db,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'partners' AND column_name = 'tin_sealed'",
    )
    assert kinds == "bytea"
    plain = _value(
        private_db,
        "SELECT count(*) FROM information_schema.columns WHERE table_name = 'partners' "
        "AND column_name IN ('tin', 'ein', 'ssn', 'itin')",
    )
    assert plain == 0
    together = str(
        _value(
            private_db,
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname = 'partners_tin_together'",
        )
    )
    assert "tin_sealed IS NULL" in together and "tin_kind IS NULL" in together
