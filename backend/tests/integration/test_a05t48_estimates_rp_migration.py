"""A-05-T48 (TASK-5116; A-05 §4.2 M8; AUD-27): migration 0685 `assurance_estimates_rp`.

Row acceptance: "Every A-05 table exists ... and parties in interest hold no copy of
late-remittance amounts." Also RLS is forced, a screen-out needs its reason and who, an exception
needs a finding, and prohibited transactions read the late remittance.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

TABLES = (
    "accounting_estimates",
    "estimate_components",
    "related_parties",
    "related_party_search_runs",
    "parties_in_interest",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


@pytest.mark.parametrize("table", TABLES)
def test_rls_is_forced(private_db: sc.Database, table: str) -> None:
    assert (
        _value(
            private_db,
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        is True
    )


def test_parties_in_interest_copy_no_late_remittance_amount(private_db: sc.Database) -> None:
    rows = asyncio.run(
        Seeder(private_db.superuser_dsn).rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'parties_in_interest'"
        )
    )
    columns = {r["column_name"] for r in rows}
    assert not columns & {"principal", "lost_earnings", "excise_exposure", "amount"}


def test_prohibited_transactions_read_the_late_remittance(private_db: sc.Database) -> None:
    definition = _value(private_db, "SELECT pg_get_viewdef('v_prohibited_transactions'::regclass)")
    assert isinstance(definition, str)
    assert "ebp_late_remittances" in definition
    options = _value(
        private_db, "SELECT reloptions FROM pg_class WHERE relname = 'v_prohibited_transactions'"
    )
    assert options == ["security_invoker=true"]


@pytest.mark.parametrize(
    ("table", "constraint"),
    [
        ("related_parties", "related_parties_screen_out"),
        ("related_parties", "related_parties_exception_has_finding"),
        ("accounting_estimates", "accounting_estimates_exception_has_finding"),
    ],
)
def test_the_guards_exist(private_db: sc.Database, table: str, constraint: str) -> None:
    assert (
        _value(
            private_db,
            "SELECT count(*) FROM pg_constraint WHERE conname = $1 AND conrelid = $2::regclass",
            constraint,
            table,
        )
        == 1
    )


def test_search_runs_hold_no_name_column(private_db: sc.Database) -> None:
    rows = asyncio.run(
        Seeder(private_db.superuser_dsn).rows(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'related_party_search_runs'"
        )
    )
    assert not {r["column_name"] for r in rows} & {"name", "director", "director_name"}


def test_down_then_up(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0684", down=True)
    assert _value(private_db, "SELECT to_regclass('public.related_parties') IS NOT NULL") is False
    migrate(private_db.owner_url, "head")
    assert _value(private_db, "SELECT to_regclass('public.related_parties') IS NOT NULL") is True
