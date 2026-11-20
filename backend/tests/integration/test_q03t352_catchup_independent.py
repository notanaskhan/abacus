"""Q-03-T352 (TASK-8762; ADR-078 catch-up lane 2028 Q3, part 2): independent AC tests for the red
and amber schema rows of A-09, W-01 and C-01 that no suite of their epic checks, written from each
row's acceptance and the migration's stated contract (its docstring), not from the DDL:

- **C-01-T09** (amber, `closes_v1`): forced RLS on every new table; publishing a plan version is a
  named human's (`published_actor_kind = 'human'`); published versions are frozen against the app.
- **C-01-T11** (amber, `closes_v2` and `requests_cas`): every new table tenant-RLS; insert-only
  tables refuse UPDATE and DELETE for `abacus_app`; human-only decision rows carry the actor_kind
  CHECK.
- **W-01-T04** (red, C20 v2 Connect): insert-only tables refuse UPDATE and DELETE for `abacus_app`;
  the new tenant tables force RLS.
- **A-09-T12** (amber, `assurance_group`): a PM on an Analytical-only component is refused; a
  deliverable review by a non-human actor is refused.

They read Postgres's own catalogue (privileges, RLS flags, CHECK definitions) on the migrated
database, so they need no seeded rows and fail on a seeded vulnerable build: a granted UPDATE, an
RLS policy left unforced or a dropped CHECK each turns one of them red.

ac-test-author: ayushkbhatia
"""

from __future__ import annotations

import asyncpg
import pytest

from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

APP = "abacus_app"

CLOSES_V1 = (
    "close_plans",
    "close_plan_versions",
    "close_plan_rows",
    "close_request_templates",
    "close_templates",
    "close_procedures",
)
CLOSES_V2 = (
    "reconciliations",
    "reconciling_items",
    "reconciling_item_resolutions",
    "statement_lines",
    "reconciliation_matches",
    "arrangements",
    "arrangement_versions",
    "close_schedule_results",
    "analytic_sets",
    "analytic_lines",
    "analytic_explanations",
    "close_entry_recordings",
    "transaction_questions",
    "transaction_question_events",
)
# "insert-only" in the migrations' own words.
INSERT_ONLY = (
    "close_templates",  # C-01-T09
    "arrangement_versions",  # C-01-T11
    "transaction_question_events",  # C-01-T11
    "integration_events",  # W-01-T04
)
CONNECT_TENANT = (
    "user_integrations",
    "integration_oauth_states",
    "integration_events",
    "integration_interest",
)
GROUP = (
    "components",
    "component_auditors",
    "component_instructions",
    "component_instruction_versions",
    "component_milestones",
    "component_deliverables",
)


def _dsn(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _fetch(db: MigratedDatabase, sql: str, *args: object) -> list[asyncpg.Record]:
    conn = await asyncpg.connect(_dsn(db.owner_url))
    try:
        return list(await conn.fetch(sql, *args))
    finally:
        await conn.close()


async def _rls(db: MigratedDatabase, table: str) -> tuple[bool, bool]:
    rows = await _fetch(
        db,
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid = to_regclass($1)",
        f"public.{table}",
    )
    assert rows, f"{table} exists"
    return bool(rows[0][0]), bool(rows[0][1])


async def _can(db: MigratedDatabase, table: str, privilege: str) -> bool:
    rows = await _fetch(
        db, "SELECT has_table_privilege($1, $2, $3)", APP, f"public.{table}", privilege
    )
    return bool(rows[0][0])


async def _checks(db: MigratedDatabase, table: str) -> list[str]:
    rows = await _fetch(
        db,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conrelid = to_regclass($1) AND contype = 'c'",
        f"public.{table}",
    )
    return [str(r[0]) for r in rows]


@pytest.mark.parametrize("table", CLOSES_V1 + CLOSES_V2 + CONNECT_TENANT + GROUP)
async def test_ac1_every_new_tenant_table_forces_rls(
    migrated_db: MigratedDatabase, table: str
) -> None:
    enabled, forced = await _rls(migrated_db, table)
    assert enabled and forced, f"{table}: RLS enabled and forced"


@pytest.mark.parametrize("table", INSERT_ONLY)
async def test_ac2_insert_only_tables_refuse_update_and_delete_for_the_app(
    migrated_db: MigratedDatabase, table: str
) -> None:
    assert not await _can(migrated_db, table, "UPDATE"), f"{table}: no UPDATE for {APP}"
    assert not await _can(migrated_db, table, "DELETE"), f"{table}: no DELETE for {APP}"


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("close_plan_versions", "published_actor_kind"),  # C-01-T09: publishing is a person's
        ("reconciling_item_resolutions", "actor_kind"),  # C-01-T11: a resolution is a person's
        ("analytic_explanations", "accepted_actor_kind"),  # C-01-T11: only a person accepts
    ],
)
async def test_ac3_human_only_decision_rows_carry_the_actor_kind_check(
    migrated_db: MigratedDatabase, table: str, column: str
) -> None:
    defs = [d for d in await _checks(migrated_db, table) if column in d]
    assert defs, f"{table}.{column} has a CHECK"
    assert any("'human'" in d for d in defs), f"{table}.{column} CHECK names 'human'"


async def test_ac4_no_table_of_the_closes_engine_is_deletable_by_the_app(
    migrated_db: MigratedDatabase,
) -> None:
    # The close engine's records are versions and events (ADR-004): the app never deletes them.
    deletable = [t for t in CLOSES_V1 + CLOSES_V2 if await _can(migrated_db, t, "DELETE")]
    assert deletable == []


async def test_ac5_a_published_plan_version_is_frozen_by_a_trigger(
    migrated_db: MigratedDatabase,
) -> None:
    # C-01-T09: "a published plan version refuses UPDATE for abacus_app". The app holds column
    # grants for drafting, so the freeze is a row trigger on the table, not a missing privilege.
    rows = await _fetch(
        migrated_db,
        "SELECT count(*) FROM pg_trigger "
        "WHERE tgrelid = to_regclass('public.close_plan_versions') "
        "AND NOT tgisinternal AND (tgtype & 16) = 16",  # BEFORE/AFTER UPDATE triggers
    )
    assert int(rows[0][0]) >= 1


async def test_ac6_an_analytical_only_component_has_no_pm(migrated_db: MigratedDatabase) -> None:
    # A-09-T12: "a PM on an Analytical-only component is refused".
    defs = await _checks(migrated_db, "components")
    assert any("analytical_only" in d for d in defs), "a CHECK names analytical_only"


async def test_ac7_a_deliverable_review_is_a_persons_only(migrated_db: MigratedDatabase) -> None:
    # A-09-T12: "a deliverable review by a non-human actor is refused".
    defs = await _checks(migrated_db, "component_deliverables")
    assert any("'human'" in d for d in defs), "a CHECK names 'human' on the review"
