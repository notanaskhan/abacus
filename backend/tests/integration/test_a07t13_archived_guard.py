"""A-07-T13 (TASK-5117; A-07 F8; ADR P-43; AUD-25): migration 0686 `archived_guard`.

Row acceptance: "On a locked work item every write to a guarded table raises archived, an
audit_events insert still succeeds, and the GUC can be set only from the four allowlisted service
functions."
"""

from __future__ import annotations

import ast
import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus.kernel.db.archive_guard import ALLOWED_KINDS, ARCHIVED_WRITE_KINDS, EXEMPT
from abacus.kernel.db.migration import tenant_table
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.banned_patterns import RULES, Rule, SourceFile
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Person, Seeder


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _locked(seeder: Seeder) -> tuple[Person, uuid.UUID, uuid.UUID]:
    tenant_id = await seeder.firm()
    who = await seeder.person(tenant_id)
    entity_id = await seeder.entity(tenant_id)
    engagement_id = await seeder.engagement(tenant_id, entity_id, who.user_id)
    work_item = await seeder.value(  # the engagement's own assurance item
        "SELECT id FROM work_items WHERE engagement_id = $1", engagement_id
    )
    assert isinstance(work_item, uuid.UUID)
    await seeder.run(
        "UPDATE work_items SET archive_locked_at = now(), status = 'archived', "
        "archived_at = now() WHERE id = $1",
        work_item,
    )
    return who, engagement_id, work_item


def test_a_write_to_a_guarded_table_raises_archived(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, engagement_id, work_item = asyncio.run(_locked(seeder))

    # The guard reads the work item under RLS, so it needs the firm's GUC, as every app write has.
    with pytest.raises(asyncpg.PostgresError, match="archived") as raised:
        asyncio.run(
            seeder.as_actor(
                who.tenant_id,
                ("human", str(who.user_id)),
                "INSERT INTO accounting_estimates (tenant_id, engagement_id, work_item_id, name, "
                "created_by_kind) VALUES ($1, $2, $3, 'Fair value', 'human')",
                who.tenant_id,
                engagement_id,
                work_item,
            )
        )
    assert raised.value.sqlstate == "AB409"


def test_a_locked_work_item_is_frozen(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, _, work_item = asyncio.run(_locked(seeder))
    with pytest.raises(asyncpg.PostgresError, match="archived"):
        asyncio.run(seeder.run("UPDATE work_items SET name = 'x' WHERE id = $1", work_item))


def test_the_kind_lets_only_its_tables_through(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, engagement_id, work_item = asyncio.run(_locked(seeder))

    # A kind this table doesn't name lets nothing through.
    with pytest.raises(asyncpg.PostgresError, match="archived"):
        asyncio.run(
            seeder.as_actor(
                who.tenant_id,
                ("human", str(who.user_id)),
                "INSERT INTO accounting_estimates (tenant_id, engagement_id, work_item_id, "
                "name, created_by_kind) VALUES ($1, $2, $3, 'x', 'human')",
                who.tenant_id,
                engagement_id,
                work_item,
                archived_write="archive_addition",
            )
        )


def test_the_trail_goes_on(private_db: sc.Database) -> None:
    triggers = asyncio.run(
        Seeder(private_db.superuser_dsn).rows(
            "SELECT tgrelid::regclass::text AS t FROM pg_trigger WHERE tgname = 'archived_guard'"
        )
    )
    guarded = {r["t"] for r in triggers}
    assert "audit_events" not in guarded
    assert "access_events" not in guarded
    assert not guarded & set(EXEMPT)
    assert {"evidence_versions", "proposed_entries", "sign_offs", "workpapers"} <= guarded


def test_every_exemption_has_a_reason() -> None:
    assert all(reason.strip() for reason in EXEMPT.values())
    assert {k for kinds in ALLOWED_KINDS.values() for k in kinds} == ARCHIVED_WRITE_KINDS


def test_a_new_table_gets_the_guard(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)

    async def _probe() -> object:
        statements: list[str] = []

        class Recorder:
            def execute(self, sqltext: str) -> object:
                statements.append(sqltext)
                return None

        tenant_table(Recorder(), "guard_probe")
        async with seeder.held() as conn:
            await conn.execute(
                "CREATE TABLE guard_probe (tenant_id uuid NOT NULL, work_item_id uuid NULL)"
            )
            try:
                for statement in statements:
                    await conn.execute(statement)
                return await conn.fetchval(
                    "SELECT count(*) FROM pg_trigger WHERE tgname = 'archived_guard' "
                    "AND tgrelid = 'guard_probe'::regclass"
                )
            finally:
                await conn.execute("DROP TABLE guard_probe")

    assert asyncio.run(_probe()) == 1


@pytest.mark.parametrize(
    ("code", "found"),
    [
        ("async def f(tx):\n    await tx.allow_archived_write('archive_addition')\n", True),
        ("q = \"SELECT set_config('app.archived_write', 'x', true)\"\n", True),
        ("async def f(tx):\n    await tx.record('x')\n", False),
    ],
)
def test_archive_001(code: str, found: bool) -> None:
    rule = next(r for r in RULES if isinstance(r, Rule) and r.id == "ARCHIVE-001")
    src = SourceFile(
        rel="src/abacus/modules/agents/x.py",
        module="abacus.modules.agents.x",
        tree=ast.parse(code),
        comments={},
    )
    assert bool(list(rule.check(src))) is found


def test_down_then_up(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, "0685", down=True)
    assert asyncio.run(seeder.value("SELECT to_regprocedure('archived_guard()')")) is None
    migrate(private_db.owner_url, "head")
    assert asyncio.run(seeder.value("SELECT to_regprocedure('archived_guard()')")) is not None
