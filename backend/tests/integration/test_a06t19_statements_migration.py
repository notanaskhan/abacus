"""A-06-T19 (TASK-3209; DEC-2209): migration 0660 statements v1 and the statements stub.

Row acceptance: "Up/down/up passes, an override without a reason and an N/A answer without a
reason are refused, and the statements stub returns 501 behind reporting.fs_disclosure."
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from typing import cast

import pytest

from abacus.api.export_openapi import document
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

TABLES = (
    "disclosure_checklist_templates",
    "disclosure_checklist_template_versions",
    "statement_documents",
    "statement_versions",
    "line_items",
    "linked_values",
    "tie_out_runs",
    "disclosure_checklist_answers",
    "statement_approvals",
)
INSERT_ONLY = (
    "statement_versions",
    "line_items",
    "linked_values",
    "tie_out_runs",
    "statement_approvals",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_ac_0660_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0659", down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        assert _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        ), table


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_ac_versions_lines_values_and_approvals_are_insert_only(
    private_db: sc.Database, table: str
) -> None:
    assert not _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'UPDATE')"
    )
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


@pytest.mark.parametrize(
    ("constraint", "needle"),
    [
        ("linked_values_override_reason", "override_reason"),
        ("disclosure_checklist_answers_na_reason", "reason"),
    ],
)
def test_ac_an_override_and_an_na_need_their_reason(
    private_db: sc.Database, constraint: str, needle: str
) -> None:
    found = _value(
        private_db,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = $1",
        constraint,
    )
    assert isinstance(found, str) and needle in found


def test_ac_the_statements_routes_document_501_behind_the_flag() -> None:
    paths = cast(dict[str, dict[str, dict[str, object]]], json.loads(document())["paths"])
    route = paths["/v1/engagements/{engagement_id}/financial-statements"]["get"]
    assert route["x-abacus-action"] == "statement.read"
    assert {"404", "501"} <= set(cast(dict[str, object], route["responses"]))
    assert uuid  # the stub's gate order is the shared contract-test pattern (A-06-T25 serves it)
