"""A-07-T20 (TASK-6116; ADR-078; I-IMMUTABLE; ADR P-43): independent tests for A-07-T13 and T14.

Written from A-07 F8 and the T13/T14 rows, not from their code. Row acceptance: "Tests fail if a
scoped table lacks the trigger or if any file outside the allowlist sets app.archived_write."

- Every table any module's registry owns that carries `work_item_id` or `engagement_id` and is not
  in the reviewed exemption list has an enabled `archived_guard` trigger (generated from the
  registries, so a new table is covered the day it is registered).
- `tenant_table` guards a brand-new scoped table by itself.
- No file outside the four allowlisted services names `app.archived_write` or calls
  `allow_archived_write` (the ARCHIVE-001 rule over the whole tree, and the rule catches a planted
  offender).
- Property: any sequence of updates, deletes and inserts on a locked work item's rows is refused
  and leaves every row as it was.
- T14's generated route-table test exists and covers mutating routes.
"""

from __future__ import annotations

import ast
import asyncio
import importlib
import pkgutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import abacus.modules
from abacus.kernel.db.archive_guard import EXEMPT
from abacus.kernel.db.migration import tenant_table
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.banned_patterns import RULES, Rule, SourceFile
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

BACKEND = Path(__file__).resolve().parents[2]
ALLOWLIST = {
    "src/abacus/kernel/uow/__init__.py",
    "src/abacus/modules/assurance/archive_additions.py",
    "src/abacus/modules/assurance/post_issuance.py",
    "src/abacus/modules/evidence/retention_extend.py",
    "src/abacus/modules/evidence/destruction.py",
}


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _registry_tables() -> set[str]:
    tables: set[str] = set()
    for module in pkgutil.iter_modules(abacus.modules.__path__):
        try:
            registry = importlib.import_module(f"abacus.modules.{module.name}.registry")
        except ModuleNotFoundError:
            continue
        tables |= set(getattr(registry, "TABLES", frozenset()))
    return tables


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def _rows(database: sc.Database, sql: str, *args: object) -> list[asyncpg.Record]:
    return asyncio.run(Seeder(database.superuser_dsn).rows(sql, *args))


def test_every_scoped_registry_table_carries_the_guard(db: sc.Database) -> None:
    scoped = {
        str(r["table_name"])
        for r in _rows(
            db,
            "SELECT DISTINCT c.table_name FROM information_schema.columns c "
            "JOIN pg_class k ON k.relname = c.table_name AND k.relkind IN ('r', 'p') "
            "WHERE c.table_schema = 'public' "
            "AND c.column_name IN ('work_item_id', 'engagement_id')",
        )
    }
    expected = (scoped & _registry_tables()) - set(EXEMPT)
    guarded = {
        str(r["relname"])
        for r in _rows(
            db,
            "SELECT k.relname FROM pg_trigger t JOIN pg_class k ON k.oid = t.tgrelid "
            "WHERE t.tgname = 'archived_guard' AND t.tgenabled <> 'D'",
        )
    }
    assert expected, "the registries name scoped tables"
    assert expected - guarded == set()


def test_every_exemption_names_a_real_table_with_a_reason() -> None:
    owned = _registry_tables() | set(sc.TABLE_OWNERS)  # the modules' and the platform's tables
    for table, reason in EXEMPT.items():
        assert reason.strip(), table
        assert table in owned or table in {
            "audit_events",
            "audit_event_labels",
            "access_events",
        }, table


class _Collect:
    def __init__(self) -> None:
        self.sql: list[str] = []

    def execute(self, sqltext: str) -> None:
        self.sql.append(sqltext)


def test_a_new_scoped_table_is_guarded_by_tenant_table(db: sc.Database) -> None:
    name = f"t20_probe_{uuid.uuid4().hex[:8]}"
    op = _Collect()
    tenant_table(op, name)

    async def build() -> int:
        conn = await asyncpg.connect(db.superuser_dsn)
        try:
            await conn.execute(
                f"CREATE TABLE {name} (tenant_id uuid NOT NULL, work_item_id uuid NOT NULL)"
            )
            for statement in op.sql:
                await conn.execute(statement)
            return int(
                await conn.fetchval(
                    "SELECT count(*) FROM pg_trigger WHERE tgrelid = $1::regclass "
                    "AND tgname = 'archived_guard'",
                    name,
                )
            )
        finally:
            await conn.execute(f"DROP TABLE IF EXISTS {name}")
            await conn.close()

    assert asyncio.run(build()) == 1


def _archive_rule() -> Rule:
    return next(r for r in RULES if isinstance(r, Rule) and r.id == "ARCHIVE-001")


def _source(rel: str, text: str) -> SourceFile:
    return SourceFile(rel, None, ast.parse(text), {})


def test_no_file_outside_the_allowlist_names_the_setting() -> None:
    rule = _archive_rule()
    offenders: list[str] = []
    for path in (BACKEND / "src" / "abacus").rglob("*.py"):
        rel = path.relative_to(BACKEND).as_posix()
        if rel in ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8")
        if "archived_write" not in text:
            continue
        found = list(rule.check(_source(rel, text)))
        if found:
            offenders.append(rel)
    assert offenders == []


def test_the_rule_catches_a_planted_offender() -> None:
    rule = _archive_rule()
    planted = (
        "async def f(tx):\n"
        "    await tx.session.execute(\"SELECT set_config('app.archived_write', 'x', true)\")\n"
        "    await tx.allow_archived_write('post_issuance')\n"
    )
    rel = "src/abacus/modules/assurance/new_thing.py"
    assert rule.applies_to(rel)
    assert len(list(rule.check(_source(rel, planted)))) == 2
    assert {p for p in ALLOWLIST if not rule.applies_to(p)} == ALLOWLIST


async def _locked_rows(dsn: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    seeder = Seeder(dsn)
    tenant_id = await seeder.firm()
    who = await seeder.person(tenant_id)
    engagement_id = await seeder.engagement(tenant_id, await seeder.entity(tenant_id), who.user_id)
    work_item = await seeder.value(
        "SELECT id FROM work_items WHERE engagement_id = $1", engagement_id
    )
    assert isinstance(work_item, uuid.UUID)
    estimate = await seeder.value(
        "INSERT INTO accounting_estimates (tenant_id, engagement_id, work_item_id, name, "
        "created_by_kind) VALUES ($1, $2, $3, 'Inventory reserve', 'human') RETURNING id",
        tenant_id,
        engagement_id,
        work_item,
    )
    assert isinstance(estimate, uuid.UUID)
    await seeder.run(
        "UPDATE work_items SET archive_locked_at = now(), status = 'archived', "
        "archived_at = now() WHERE id = $1",
        work_item,
    )
    return tenant_id, engagement_id, work_item, estimate


_STATEMENTS = st.sampled_from(
    [
        "UPDATE accounting_estimates SET name = 'Changed' WHERE id = $4",
        "UPDATE accounting_estimates SET balance = 1 WHERE id = $4",
        "DELETE FROM accounting_estimates WHERE id = $4",
        "INSERT INTO accounting_estimates (tenant_id, engagement_id, work_item_id, name, "
        "created_by_kind) VALUES ($1, $2, $3, 'New', 'human')",
    ]
)


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(sequence=st.lists(_STATEMENTS, min_size=1, max_size=4))
def test_no_sequence_of_writes_moves_a_locked_row(db: sc.Database, sequence: list[str]) -> None:
    tenant_id, engagement_id, work_item, estimate = asyncio.run(_locked_rows(db.superuser_dsn))

    async def attempt() -> None:
        conn = await asyncpg.connect(db.superuser_dsn)
        try:
            await conn.execute("SELECT set_config('app.tenant_id', $1, false)", str(tenant_id))
            for statement in sequence:
                args = [tenant_id, engagement_id, work_item, estimate]
                used = [a for i, a in enumerate(args, 1) if f"${i}" in statement]
                sql = statement
                for new, old in enumerate(
                    [i for i in range(1, 5) if f"${i}" in statement], start=1
                ):
                    sql = sql.replace(f"${old}", f"${new}")
                with pytest.raises(asyncpg.PostgresError, match="archived"):
                    await conn.execute(sql, *used)
        finally:
            await conn.close()

    asyncio.run(attempt())
    row = _rows(db, "SELECT name, balance FROM accounting_estimates WHERE id = $1", estimate)
    assert [(r["name"], r["balance"]) for r in row] == [("Inventory reserve", None)]
    assert (
        _value(
            db,
            "SELECT count(*) FROM accounting_estimates WHERE work_item_id = $1",
            work_item,
        )
        == 1
    )


def test_t14_s_route_table_test_covers_mutating_routes() -> None:
    generated = BACKEND / "tests" / "security" / "test_a07t14_archived_exempt.py"
    text = generated.read_text(encoding="utf-8")
    assert "409" in text and "archived" in text
    assert "POST" in text or "post" in text
