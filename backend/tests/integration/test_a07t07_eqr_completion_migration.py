"""A-07-T07 (TASK-3251; DEC-2232): migration 0664 `a07_eqr_completion` (SPEC-644 AC-7).

Row acceptance: "Up/down/up passes, a concurrence written by an agent or system actor is refused
by the database, and every new table has forced RLS." Also: a not-applicable checklist row needs
a basis, a legal letter is not applicable exactly when it holds a basis, `filed` needs the
evidence, subsequent events are insert-only, and 0077's record-mode concurrence still inserts.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from typing import cast

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

TABLES = (
    "eqr_reviews",
    "eqr_checklist_items",
    "eqr_digest_cards",
    "completion_items",
    "subsequent_event_procedures",
    "subsequent_events",
    "legal_letters",
    "going_concern_evaluations",
    "filings",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_ac7_0664_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0663", down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    assert not _value(
        private_db,
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'eqr_concurrences' AND column_name = 'eqr_review_id')",
    )
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        assert _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        ), table


@pytest.mark.parametrize("table", TABLES)
def test_ac7_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


async def _review(seed: Seeder) -> dict[str, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    client = await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'", engagement
        )
        or await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'assurance', 'Plan 2025', $5) "
            "RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            person.user_id,
        ),
    )
    review = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO eqr_reviews (tenant_id, engagement_id, work_item_id, eqr_user_id) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            tenant,
            engagement,
            item,
            person.user_id,
        ),
    )
    return {
        "tenant": tenant,
        "engagement": engagement,
        "item": item,
        "review": review,
        "person": person.user_id,
    }


_CONCUR = (
    "INSERT INTO eqr_concurrences (tenant_id, engagement_id, work_item_id, eqr_review_id, "
    "digest_hash, not_involved, concurred_by, actor_kind, concurrence_date, "
    "checklist_snapshot_sha256, notes_cleared_count, mfa_verified_at) VALUES ($1, $2, $3, $4, "
    "repeat('a', 64), true, $5, $6, '2026-10-05', repeat('a', 64), 2, now())"
)


@pytest.mark.parametrize("kind", ["agent", "system"])
def test_ac7_a_concurrence_by_an_agent_or_system_actor_is_refused(
    private_db: sc.Database, kind: str
) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _review(seed)
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(
                ids["tenant"],
                (kind, str(ids["person"])),
                _CONCUR,
                ids["tenant"],
                ids["engagement"],
                ids["item"],
                ids["review"],
                ids["person"],
                kind,
            )

    asyncio.run(scenario())


def test_ac7_a_persons_concurrence_holds_once_per_review(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _review(seed)
        args = (ids["tenant"], ids["engagement"], ids["item"], ids["review"], ids["person"])
        actor = ("human", str(ids["person"]))
        await seed.as_actor(ids["tenant"], actor, _CONCUR, *args, "human")
        with pytest.raises(asyncpg.UniqueViolationError):
            await seed.as_actor(ids["tenant"], actor, _CONCUR, *args, "human")
        # A row claiming `human` from an agent's transaction is refused by the CHECK, which binds
        # the row's actor kind to the session's (`app.actor_kind`).
        agent = ("agent", str(uuid.uuid4()))
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(ids["tenant"], agent, _CONCUR, *args, "human")

    asyncio.run(scenario())


def test_ac7_record_mode_concurrences_still_insert(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _review(seed)
        await seed.run(
            "INSERT INTO eqr_concurrences (tenant_id, engagement_id, digest_hash, not_involved, "
            "concurred_by, actor_kind) VALUES ($1, $2, repeat('a', 64), true, $3, 'human')",
            ids["tenant"],
            ids["engagement"],
            ids["person"],
        )

    asyncio.run(scenario())


def test_ac7_row_rules_hold(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _review(seed)
        scope = (ids["tenant"], ids["engagement"], ids["item"])
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO completion_items (tenant_id, engagement_id, work_item_id, item_key, "
                "position, status, derived) VALUES ($1, $2, $3, 'legal_letters', 1, "
                "'not_applicable', false)",
                *scope,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO legal_letters (tenant_id, engagement_id, work_item_id, "
                "not_applicable) VALUES ($1, $2, $3, true)",
                *scope,
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO filings (tenant_id, engagement_id, work_item_id, form, filer_name, "
                "status, filed_on) VALUES ($1, $2, $3, 'form_5500', 'Northwind', 'filed', "
                "'2026-10-14')",
                *scope,
            )
        actor = ("human", str(ids["person"]))
        await seed.as_actor(
            ids["tenant"],
            actor,
            "INSERT INTO subsequent_events (tenant_id, engagement_id, work_item_id, "
            "description_sealed, recognition, recorded_by) VALUES ($1, $2, $3, '\\x00', "
            "'nonrecognized', $4)",
            *scope,
            ids["person"],
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run(
                "UPDATE subsequent_events SET recognition = 'recognized' WHERE work_item_id = $1",
                ids["item"],
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(
                ids["tenant"],
                ("agent", str(ids["person"])),
                "INSERT INTO subsequent_events (tenant_id, engagement_id, work_item_id, "
                "description_sealed, recognition, recorded_by) VALUES ($1, $2, $3, '\\x00', "
                "'recognized', $4)",
                *scope,
                ids["person"],
            )

    asyncio.run(scenario())
