"""K-01-T02 (TASK-1306): migration 0180 on a firm that already has methodology versions.

"up/down/up passes, every legacy version reads published with approval_basis legacy_import"
(K-01-T02 acceptance): versions imported before 0180 are backfilled as published on their own
authority, effective from their creation date, labelled `v<n>`, with the template's newest
version as its default and one `legacy_backfilled` event each; down and up again leaves a
schema that passes the schema check.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0172"  # the revision before the methodology re-own (0180)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _revision(database: sc.Database) -> str:
    seed = Seeder(database.superuser_dsn)
    return str(asyncio.run(seed.value("SELECT version_num FROM alembic_version")))


async def _legacy(seed: Seeder) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """A firm with one template and two versions, imported before 0180."""
    tenant = await seed.firm()
    person = await seed.person(tenant)
    template = uuid.uuid4()
    await seed.run(
        "INSERT INTO methodology_templates (id, tenant_id, name, created_by, engagement_types) "
        "VALUES ($1, $2, 'BH EBP', $3, '{ebp_audit}')",
        template,
        tenant,
        person.user_id,
    )
    versions: list[uuid.UUID] = []
    for number in (1, 2):
        version = uuid.uuid4()
        await seed.run(
            "INSERT INTO methodology_versions (id, tenant_id, template_id, version, "
            "source_fingerprint, imported_by) VALUES ($1, $2, $3, $4, $5, $6)",
            version,
            tenant,
            template,
            number,
            "f" * 64,
            person.user_id,
        )
        versions.append(version)
    return tenant, versions


def test_ac_legacy_versions_read_published_and_the_migration_goes_down_and_up(
    private_db: sc.Database,
) -> None:
    seed = Seeder(private_db.superuser_dsn)
    head = _revision(private_db)
    migrate(private_db.owner_url, BEFORE, down=True)
    assert asyncio.run(seed.value("SELECT to_regclass('methodology_version_states') IS NULL"))
    tenant, (v1, v2) = asyncio.run(_legacy(seed))

    migrate(private_db.owner_url, "head")
    assert _revision(private_db) == head
    states = asyncio.run(
        seed.rows(
            "SELECT s.version_id, s.status, s.approval_basis, s.default_for_new_engagements, "
            "s.effective_from = v.created_at::date AS dated, s.engagement_types, v.label, "
            "v.origin FROM methodology_version_states s JOIN methodology_versions v "
            "ON v.tenant_id = s.tenant_id AND v.id = s.version_id WHERE s.tenant_id = $1",
            tenant,
        )
    )
    by_version = {r["version_id"]: r for r in states}
    assert set(by_version) == {v1, v2}
    for row in states:
        assert (row["status"], row["approval_basis"], row["dated"], row["origin"]) == (
            "published",
            "legacy_import",
            True,
            "legacy",
        )
        assert row["engagement_types"] == ["ebp_audit"]
    assert (by_version[v1]["label"], by_version[v2]["label"]) == ("v1", "v2")
    assert by_version[v1]["default_for_new_engagements"] is False
    assert by_version[v2]["default_for_new_engagements"] is True
    events = asyncio.run(
        seed.rows(
            "SELECT version_id, kind, actor_kind FROM methodology_version_events "
            "WHERE tenant_id = $1",
            tenant,
        )
    )
    assert sorted((r["version_id"], r["kind"], r["actor_kind"]) for r in events) == sorted(
        [(v1, "legacy_backfilled", "system"), (v2, "legacy_backfilled", "system")]
    )
    forced = asyncio.run(
        seed.value(
            "SELECT bool_and(relforcerowsecurity) FROM pg_class "
            "WHERE relname IN ('methodology_templates', 'methodology_versions')"
        )
    )
    assert forced is True  # forced again after the backfill

    migrate(private_db.owner_url, BEFORE, down=True)
    assert asyncio.run(seed.value("SELECT to_regclass('standards_sets') IS NULL"))
    migrate(private_db.owner_url, "head")
    assert _revision(private_db) == head
    assert sc.check(private_db.owner_url, private_db.app_url) == []
