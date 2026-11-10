"""A-05-T48 (Q-03-T206, TASK-6129; ADR-078): an independent suite for the estimates and related
parties tables.

Written from the A-05-T48 row, not its migration test. Row acceptance: "Every A-05 table exists in
production before Dec 24, 2027, and parties in interest hold no copy of late-remittance amounts."
Covered: the five tables exist with forced RLS and a policy; parties in interest carry no money
column (nothing that could hold a remittance amount); prohibited transactions are a read (a view
running as its caller, so RLS applies) over `ebp_late_remittances`, never a table; the app role
cannot write the view.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

TABLES = (
    "accounting_estimates",
    "estimate_components",
    "related_parties",
    "related_party_search_runs",
    "parties_in_interest",
)


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


@pytest.mark.parametrize("table", TABLES)
def test_the_table_exists_with_forced_rls(db: sc.Database, table: str) -> None:
    assert (
        _value(
            db,
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class "
            "WHERE relname = $1 AND relkind IN ('r', 'p')",
            table,
        )
        is True
    )
    policies = _value(db, "SELECT count(*) FROM pg_policy WHERE polrelid = $1::regclass", table)
    assert isinstance(policies, int) and policies >= 1


def test_parties_in_interest_hold_no_money(db: sc.Database) -> None:
    money = _value(
        db,
        "SELECT count(*) FROM information_schema.columns WHERE table_name = 'parties_in_interest' "
        "AND (data_type IN ('numeric', 'money') "
        "OR column_name ~ '(amount|cents|balance|remittance)')",
    )
    assert money == 0


def test_prohibited_transactions_are_a_caller_s_read_over_late_remittances(
    db: sc.Database,
) -> None:
    assert (
        _value(
            db, "SELECT relkind::text FROM pg_class WHERE relname = 'v_prohibited_transactions'"
        )
        == "v"
    )
    options = _value(
        db, "SELECT reloptions::text FROM pg_class WHERE relname = 'v_prohibited_transactions'"
    )
    assert "security_invoker=true" in str(options)
    definition = _value(db, "SELECT pg_get_viewdef('v_prohibited_transactions'::regclass)")
    assert "ebp_late_remittances" in str(definition)
    for privilege in ("INSERT", "UPDATE", "DELETE"):
        assert (
            _value(
                db,
                "SELECT has_table_privilege('abacus_app', 'v_prohibited_transactions', $1)",
                privilege,
            )
            is False
        ), privilege
