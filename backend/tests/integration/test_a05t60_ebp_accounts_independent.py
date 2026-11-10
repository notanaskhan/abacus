"""A-05-T41 (A-05-T60, TASK-6217; ADR-078): an independent suite for the loans, accounts and
expenses tables.

Written from the A-05-T41 row, not its migration test. Row acceptance: "Upgrade and downgrade
pass on the seed, and SSNs in the balance and SDBA schedules are sealed like the census." Covered:
the eight tables exist with forced RLS and a policy; no column could hold a plaintext SSN (only
the sealed bytes, an HMAC fingerprint and the last four); the app role can't update or delete the
sealed columns.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

TABLES = (
    "ebp_participant_loans",
    "ebp_loan_offsets",
    "ebp_participant_balances",
    "ebp_sdba_holdings",
    "ebp_plan_expenses",
    "ebp_erisa_budget_lines",
    "ebp_compliance_tests",
    "ebp_qualification_facts",
)
SCHEDULES = ("ebp_participant_balances", "ebp_sdba_holdings")


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


@pytest.mark.parametrize("table", TABLES)
def test_no_column_holds_a_plaintext_ssn(db: sc.Database, table: str) -> None:
    plain = _value(
        db,
        "SELECT count(*) FROM information_schema.columns WHERE table_name = $1 "
        "AND column_name ~ '(ssn|tin|social)' "
        "AND column_name NOT IN ('ssn_sealed', 'ssn_fp', 'ssn_last4')",
        table,
    )
    assert plain == 0


@pytest.mark.parametrize("table", SCHEDULES)
def test_the_schedules_seal_the_ssn_like_the_census(db: sc.Database, table: str) -> None:
    types = _value(
        db,
        "SELECT string_agg(column_name || ':' || data_type, ',' ORDER BY column_name) "
        "FROM information_schema.columns WHERE table_name = $1 AND column_name LIKE 'ssn%'",
        table,
    )
    assert types == "ssn_fp:text,ssn_last4:text,ssn_sealed:bytea"
    # The census's own shape: the same three columns (0642).
    census = _value(
        db,
        "SELECT string_agg(column_name, ',' ORDER BY column_name) FROM information_schema.columns "
        "WHERE table_name = 'ebp_participants' AND column_name LIKE 'ssn%'",
    )
    assert census == "ssn_fp,ssn_last4,ssn_sealed"


@pytest.mark.parametrize("table", SCHEDULES)
def test_the_app_role_cannot_rewrite_or_delete_a_sealed_ssn(db: sc.Database, table: str) -> None:
    for column in ("ssn_sealed", "ssn_fp", "ssn_last4"):
        assert (
            _value(
                db, "SELECT has_column_privilege('abacus_app', $1, $2, 'UPDATE')", table, column
            )
            is False
        ), column
    assert _value(db, "SELECT has_table_privilege('abacus_app', $1, 'DELETE')", table) is False
