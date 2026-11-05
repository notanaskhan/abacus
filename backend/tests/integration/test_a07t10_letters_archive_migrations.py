"""A-07-T10 (TASK-3304): AC tests for migrations 0664, 0668 and 0669, from the acceptance text.

Row acceptance: "Tests pass and fail when any insert-only or human-only trigger is removed." So
each table's trigger is named and checked as well as exercised. Covers forced RLS, the insert-only
triggers, the human-only CHECKs bound to the app.actor GUCs, one original release per work item,
the 60-day documentation completion date and the five-year retention floor.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator
from typing import cast

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

M1 = ("eqr_reviews", "eqr_checklist_items", "eqr_digest_cards", "completion_items",
      "subsequent_event_procedures", "subsequent_events", "legal_letters",
      "going_concern_evaluations", "filings")  # fmt: skip
M2 = ("representation_letters", "representation_letter_versions",
      "representation_letter_approvals", "governance_communications",
      "governance_communication_versions", "governance_communication_sends",
      "governance_recipients", "governance_acknowledgements", "audit_reports",
      "audit_report_versions", "report_releases")  # fmt: skip
M3 = ("archive_binder_indexes", "archive_lock_decisions", "archive_manifests",
      "archive_additions", "archive_addition_decisions")  # fmt: skip
TRIGGERED = (
    "subsequent_events", "representation_letter_versions", "representation_letter_approvals",
    "governance_communication_versions", "governance_communication_sends",
    "governance_acknowledgements", "audit_report_versions", "report_releases", *M3,
)  # fmt: skip
_SHA = "a" * 64


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_ac_the_migrations_go_down_and_up(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0667", down=True)
    for table in (*M2, *M3):
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    assert _value(
        private_db,
        "SELECT NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE "
        "table_name = 'archives' AND column_name = 'documentation_completion_date')",
    )
    migrate(private_db.owner_url, "head")


@pytest.mark.parametrize("table", [*M1, *M2, *M3, "archives"])
def test_ac_forced_rls_on_every_table(private_db: sc.Database, table: str) -> None:
    assert _value(
        private_db,
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
        table,
    )


@pytest.mark.parametrize("table", TRIGGERED)
def test_ac_each_insert_only_table_keeps_its_trigger(private_db: sc.Database, table: str) -> None:
    assert _value(
        private_db,
        "SELECT count(*) = 2 FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "JOIN pg_proc p ON p.oid = t.tgfoid WHERE c.relname = $1 AND NOT t.tgisinternal "
        "AND p.proname = 'a07_rows_immutable'",
        table,
    ), table
    assert not _value(
        private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')"
    ), table


async def _world(seed: Seeder) -> dict[str, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'", engagement
        ),
    )
    report = await seed.value(
        "INSERT INTO audit_reports (tenant_id, engagement_id, work_item_id, report_kind) "
        "VALUES ($1, $2, $3, 'audit') RETURNING id",
        tenant,
        engagement,
        item,
    )
    version = await seed.value(
        "INSERT INTO audit_report_versions (tenant_id, engagement_id, work_item_id, report_id, "
        "version_no, content_hash, created_by) VALUES ($1, $2, $3, $4, 1, $5, $6) RETURNING id",
        tenant,
        engagement,
        item,
        report,
        _SHA,
        person.user_id,
    )
    return {
        "tenant": tenant,
        "engagement": engagement,
        "item": item,
        "person": person.user_id,
        "report": cast(uuid.UUID, report),
        "version": cast(uuid.UUID, version),
        "document": uuid.uuid4(),
    }


_RELEASE = (
    "INSERT INTO report_releases (tenant_id, engagement_id, work_item_id, kind, reissue_of_id, "
    "report_version_id, report_version_hash, released_by, report_date, gate_snapshot, "
    "gate_snapshot_sha256, final_document_version_id) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, "
    "'2026-10-09', $9::jsonb, $10, $11)"
)


def _release_args(ids: dict[str, uuid.UUID], kind: str, of: uuid.UUID | None) -> tuple[object, ...]:
    return (
        ids["tenant"], ids["engagement"], ids["item"], kind, of, ids["version"], _SHA,
        ids["person"], json.dumps({"g8": True}), _SHA, ids["document"],
    )  # fmt: skip


async def _released(seed: Seeder, ids: dict[str, uuid.UUID]) -> uuid.UUID:
    human = ("human", str(ids["person"]))
    await seed.as_actor(ids["tenant"], human, _RELEASE, *_release_args(ids, "original", None))
    return cast(
        uuid.UUID,
        await seed.value("SELECT id FROM report_releases WHERE work_item_id = $1", ids["item"]),
    )


def test_ac_one_original_release_per_work_item(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _world(seed)
        first = await _released(seed, ids)
        human = ("human", str(ids["person"]))
        with pytest.raises(asyncpg.UniqueViolationError):
            await seed.as_actor(
                ids["tenant"], human, _RELEASE, *_release_args(ids, "original", None)
            )
        await seed.as_actor(ids["tenant"], human, _RELEASE, *_release_args(ids, "reissue", first))

    asyncio.run(scenario())


def test_ac_an_agent_cannot_release_and_a_release_never_changes(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _world(seed)
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(
                ids["tenant"],
                ("agent", str(ids["person"])),
                _RELEASE,
                *_release_args(ids, "original", None),
            )
        release = await _released(seed, ids)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run("UPDATE report_releases SET city = 'Denver' WHERE id = $1", release)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run("DELETE FROM report_releases WHERE id = $1", release)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run(
                "UPDATE audit_report_versions SET city = 'Denver' WHERE id = $1", ids["version"]
            )

    asyncio.run(scenario())


async def _archive(seed: Seeder, ids: dict[str, uuid.UUID], release: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO archives (tenant_id, engagement_id, work_item_id, release_id, "
            "released_at, release_date, retention_until, status) VALUES ($1, $2, $3, $4, "
            "'2026-10-09T20:00:00Z', '2026-10-09', '2031-10-09', 'assembling') RETURNING id",
            ids["tenant"],
            ids["engagement"],
            ids["item"],
            release,
        ),
    )


_LOCK = (
    "INSERT INTO archive_lock_decisions (tenant_id, engagement_id, work_item_id, archive_id, "
    "decided_by, assembly_complete_attested, checklist_snapshot, checklist_sha256, "
    "mfa_verified_at) VALUES ($1, $2, $3, $4, $5, $6, '[]'::jsonb, $7, now())"
)


def test_ac_the_documentation_date_and_the_lock_decision(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _world(seed)
        release = await _released(seed, ids)
        archive = await _archive(seed, ids, release)
        date = await seed.value(
            "SELECT documentation_completion_date::text FROM archives WHERE id = $1", archive
        )
        assert date == "2026-12-08"
        args = (ids["tenant"], ids["engagement"], ids["item"], archive, ids["person"])
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(
                ids["tenant"], ("agent", str(ids["person"])), _LOCK, *args, True, _SHA
            )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(
                ids["tenant"], ("human", str(ids["person"])), _LOCK, *args, False, _SHA
            )
        await seed.as_actor(ids["tenant"], ("human", str(ids["person"])), _LOCK, *args, True, _SHA)

    asyncio.run(scenario())


def test_ac_an_addition_approval_is_a_persons(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _world(seed)
        archive = await _archive(seed, ids, await _released(seed, ids))
        evidence_item = await seed.value(
            "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
            "created_by_id) VALUES ($1, $2, 'Omitted procedure memo.pdf', 'human', 'seed') "
            "RETURNING id",
            ids["tenant"],
            ids["engagement"],
        )
        version = await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, repeat('e', 64), "
            "'tenants/' || $1::uuid::text || '/sha256/' || repeat('e', 64), 'v1', 10, "
            "'application/pdf', 'client_upload', 'uploaded') RETURNING id",
            ids["tenant"],
            ids["engagement"],
            evidence_item,
        )
        addition = await seed.value(
            "INSERT INTO archive_additions (tenant_id, engagement_id, work_item_id, archive_id, "
            "description_sealed, reason_code, evidence_version_id, content_sha256, added_by) "
            "VALUES ($1, $2, $3, $4, '\\x00', 'other', $5, $6, $7) RETURNING id",
            ids["tenant"],
            ids["engagement"],
            ids["item"],
            archive,
            version,
            _SHA,
            ids["person"],
        )
        decide = (
            "INSERT INTO archive_addition_decisions (tenant_id, engagement_id, work_item_id, "
            "addition_id, decision, decided_by, mfa_verified_at) VALUES ($1, $2, $3, $4, "
            "'approved', $5, now())"
        )
        args = (ids["tenant"], ids["engagement"], ids["item"], addition, ids["person"])
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(ids["tenant"], ("system", "worker"), decide, *args)
        await seed.as_actor(ids["tenant"], ("human", str(ids["person"])), decide, *args)

    asyncio.run(scenario())


def test_ac_the_retention_floor_and_a_v1_row_stays_frozen(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _world(seed)
        release = await _released(seed, ids)
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO archives (tenant_id, engagement_id, work_item_id, release_id, "
                "released_at, release_date, retention_until, status) VALUES ($1, $2, $3, $4, "
                "now(), '2026-10-09', '2028-10-09', 'assembling')",
                ids["tenant"],
                ids["engagement"],
                ids["item"],
                release,
            )
        v1 = await seed.value(
            "INSERT INTO archives (tenant_id, engagement_id, seal, leaf_count, manifest, "
            "locked_by, actor_kind) VALUES ($1, $2, $3, 1, '{}'::jsonb, $4, 'human') RETURNING id",
            ids["tenant"],
            ids["engagement"],
            _SHA,
            ids["person"],
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run("UPDATE archives SET retention_until = now()::date WHERE id = $1", v1)

    asyncio.run(scenario())


def test_ac_new_text_columns_are_sealed(private_db: sc.Database) -> None:
    for table, column in (
        ("representation_letter_versions", "edited_paragraphs_sealed"),
        ("governance_communication_versions", "sections_sealed"),
        ("archive_additions", "description_sealed"),
        ("archive_addition_decisions", "reason_sealed"),
    ):
        assert _value(
            private_db,
            "SELECT data_type = 'bytea' FROM information_schema.columns "
            "WHERE table_name = $1 AND column_name = $2",
            table,
            column,
        ), f"{table}.{column}"
