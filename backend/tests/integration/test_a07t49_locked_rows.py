"""A-07-T49 (TASK-6817; ADR-078; A-07 F7; SPEC-644): a locked archive and its rows never change.

Row acceptance (the locked-row half): "Tests ... fail if ... a locked row changes." Written apart
from A-07-T10's migration tests: the archive is driven the way the lock drives it (assembling,
the person's decision, the manifest, then `locked` with its seal) and every write after that is
refused by the database itself, whatever the session's role: the archive row, its decision, its
manifest, its binder index and an approved addition's decision.
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
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

_SHA = "a" * 64
_SEAL = "5" * 64


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _locked_world(seed: Seeder) -> dict[str, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    human = ("human", str(person.user_id))
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
    await seed.as_actor(
        tenant,
        human,
        "INSERT INTO report_releases (tenant_id, engagement_id, work_item_id, kind, "
        "report_version_id, report_version_hash, released_by, report_date, gate_snapshot, "
        "gate_snapshot_sha256, final_document_version_id) VALUES ($1, $2, $3, 'original', $4, "
        "$5, $6, '2026-10-09', $7::jsonb, $5, $8)",
        tenant,
        engagement,
        item,
        version,
        _SHA,
        person.user_id,
        json.dumps({"G5": True, "G6": True, "G7": True}),
        uuid.uuid4(),
    )
    release = cast(
        uuid.UUID,
        await seed.value("SELECT id FROM report_releases WHERE work_item_id = $1", item),
    )
    archive = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO archives (tenant_id, engagement_id, work_item_id, release_id, "
            "released_at, release_date, retention_until, status) VALUES ($1, $2, $3, $4, "
            "'2026-10-09T20:00:00Z', '2026-10-09', '2033-10-09', 'assembling') RETURNING id",
            tenant,
            engagement,
            item,
            release,
        ),
    )
    await seed.as_actor(
        tenant,
        human,
        "INSERT INTO archive_binder_indexes (tenant_id, engagement_id, work_item_id, archive_id, "
        "index_version, sections, sha256, built_by_kind) VALUES ($1, $2, $3, $4, 1, '[]'::jsonb, "
        "$5, 'code')",
        tenant,
        engagement,
        item,
        archive,
        _SHA,
    )
    await seed.as_actor(
        tenant,
        human,
        "INSERT INTO archive_lock_decisions (tenant_id, engagement_id, work_item_id, archive_id, "
        "decided_by, assembly_complete_attested, checklist_snapshot, checklist_sha256, "
        "mfa_verified_at) VALUES ($1, $2, $3, $4, $5, true, '[]'::jsonb, $6, now())",
        tenant,
        engagement,
        item,
        archive,
        person.user_id,
        _SHA,
    )
    decision = cast(
        uuid.UUID,
        await seed.value("SELECT id FROM archive_lock_decisions WHERE archive_id = $1", archive),
    )
    manifest = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO archive_manifests (tenant_id, engagement_id, work_item_id, archive_id, "
            "manifest_version, evidence_leaf_count, row_leaf_count, run_record_count, "
            "merkle_root, manifest_sha256, compliance_retain_until) VALUES ($1, $2, $3, $4, 1, "
            "1, 1, 0, $5, $6, '2031-10-09') RETURNING id",
            tenant,
            engagement,
            item,
            archive,
            _SHA,
            _SEAL,
        ),
    )
    await seed.run(
        "UPDATE archives SET status = 'locking', lock_decision_id = $2 WHERE id = $1",
        archive,
        decision,
    )
    await seed.run(
        "UPDATE archives SET status = 'locked', locked_at = now(), locked_by = $2, "
        "manifest_id = $3, seal_sha256 = $4 WHERE id = $1",
        archive,
        person.user_id,
        manifest,
        _SEAL,
    )
    return {
        "tenant": tenant,
        "person": person.user_id,
        "archive": archive,
        "decision": decision,
        "manifest": manifest,
    }


@pytest.fixture(scope="module")
def world(private_db: sc.Database) -> dict[str, uuid.UUID]:
    return asyncio.run(_locked_world(Seeder(private_db.superuser_dsn)))


def _refused(database: sc.Database, sql: str, *args: object) -> None:
    async def attempt() -> None:
        await Seeder(database.superuser_dsn).run(sql, *args)

    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(attempt())


def test_the_world_is_locked_and_sealed(
    private_db: sc.Database, world: dict[str, uuid.UUID]
) -> None:
    async def read() -> object:
        return await Seeder(private_db.superuser_dsn).value(
            "SELECT status || ':' || seal_sha256 FROM archives WHERE id = $1", world["archive"]
        )

    assert asyncio.run(read()) == f"locked:{_SEAL}"


_ARCHIVE_WRITES = (
    "UPDATE archives SET status = 'assembling' WHERE id = $1",
    "UPDATE archives SET seal_sha256 = repeat('6', 64) WHERE id = $1",
    "UPDATE archives SET retention_until = '2040-10-09' WHERE id = $1",
    "UPDATE archives SET retention_until = '2031-10-09' WHERE id = $1",
    "UPDATE archives SET records_object_key = 'elsewhere' WHERE id = $1",
    "UPDATE archives SET locked_by = NULL WHERE id = $1",
    "DELETE FROM archives WHERE id = $1",
)


@pytest.mark.parametrize("sql", _ARCHIVE_WRITES)
def test_a_locked_archive_row_never_changes_nor_goes(
    private_db: sc.Database, world: dict[str, uuid.UUID], sql: str
) -> None:
    _refused(private_db, sql, world["archive"])


@pytest.mark.parametrize(
    ("sql", "key"),
    [
        ("UPDATE archive_lock_decisions SET then_roll_forward = true WHERE id = $1", "decision"),
        ("DELETE FROM archive_lock_decisions WHERE id = $1", "decision"),
        (
            "UPDATE archive_manifests SET manifest_sha256 = repeat('7', 64) WHERE id = $1",
            "manifest",
        ),
        (
            "UPDATE archive_manifests SET compliance_retain_until = '2027-01-01' WHERE id = $1",
            "manifest",
        ),
        ("DELETE FROM archive_manifests WHERE id = $1", "manifest"),
    ],
)
def test_the_lock_decision_and_the_manifest_never_change(
    private_db: sc.Database, world: dict[str, uuid.UUID], sql: str, key: str
) -> None:
    _refused(private_db, sql, world[key])


def test_the_binder_index_never_changes(
    private_db: sc.Database, world: dict[str, uuid.UUID]
) -> None:
    _refused(
        private_db,
        "UPDATE archive_binder_indexes SET sha256 = repeat('8', 64) WHERE archive_id = $1",
        world["archive"],
    )
    _refused(
        private_db, "DELETE FROM archive_binder_indexes WHERE archive_id = $1", world["archive"]
    )
