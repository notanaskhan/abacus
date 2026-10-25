"""Q-01-T38 (Q-01 F9): the restore drill's verification on a real copy. A private Postgres is the
source; a "restore" is a template copy of it on the same server (what a point-in-time restore of
a quiet instance holds), and the S3 gateway bucket stands in for the replica bucket. A clean copy
passes; a planted fingerprint mismatch, a sequence gap and a missing row each fail by name; the
sample is 1% with a floor of 50; the report records the restore-to-verified time against the
5-minute RPO and carries no content."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import uow
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import NewItem, Provenance, add_version, stage_content
from abacus_tools import drill
from abacus_tools.drill import DrillReport, Side, sample_size, verify, with_host
from abacus_tools.quality.schema_check import Database, provisioned_database

from .agent_tests.support import Seeder
from .trust_kit.support import Seeder as Planter

MASTER = b"drill-test-master-key-0123456789abcdef01"
BUCKET = f"drill-{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="module")
def source() -> Iterator[Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


@pytest.fixture(scope="module")
def bucket_client(s3_settings: dict[str, str]) -> S3Client:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    return client


@pytest.fixture(autouse=True)
def evidence_storage(bucket_client: S3Client) -> Iterator[S3Client]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket_client, BUCKET)
    yield bucket_client
    storage.reset_storage()
    reset_key_service()


@dataclass(frozen=True)
class Seeded:
    tenant_id: uuid.UUID
    versions: tuple[uuid.UUID, ...]


async def _seed(database: Database, client: S3Client) -> Seeded:
    """A firm with three uploaded versions (and their audit events), stored for real."""
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(client, BUCKET)
    seed = Seeder(database.superuser_dsn)
    tenant = await seed.firm()
    # As `provision_firm` records every firm it creates (the drill's list of firms).
    await seed.run(
        "INSERT INTO firm_provisioning_requests (idempotency_key, tenant_id, operator) "
        "VALUES ($1, $2, 'drill-test')",
        f"drill-{tenant}",
        tenant,
    )
    staff = await seed.person(tenant)
    engagement = await seed.engagement(tenant, await seed.entity(tenant), staff.user_id)
    await dispose_engine()
    configure_engine(database.app_url)
    system = TenantContext(tenant, "system", "evidence.upload_processing")
    versions: list[uuid.UUID] = []
    for n in range(3):
        stored = await stage_content(tenant, f"drill statement {n} {uuid.uuid4()}".encode())
        async with uow(system) as tx:
            ref = await add_version(
                tx,
                engagement_id=engagement,
                item=NewItem(f"Drill {n}"),
                stored=stored,
                media_type="text/plain",
                provenance=Provenance(source="upload", method="uploaded"),
            )
        versions.append(ref.id)
    await dispose_engine()
    return Seeded(tenant, tuple(versions))


@pytest.fixture(scope="module")
def seeded(source: Database, bucket_client: S3Client) -> Seeded:
    return asyncio.run(_seed(source, bucket_client))


async def _restore(database: Database) -> Database:
    """A template copy of the source under a new name: the restored instance."""
    name = f"restored_{uuid.uuid4().hex[:8]}"
    await dispose_engine()
    admin = Seeder(database.superuser_dsn.rsplit("/", 1)[0] + "/postgres")
    await admin.run(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = 'abacus' AND pid <> pg_backend_pid()"
    )
    await admin.run(f'CREATE DATABASE "{name}" TEMPLATE abacus')

    def renamed(url: str) -> str:
        return url.rsplit("/", 1)[0] + f"/{name}"

    return Database(
        renamed(database.owner_url),
        renamed(database.app_url),
        renamed(database.relay_url),
        renamed(database.identity_url),
        renamed(database.superuser_dsn),
    )


async def _plant(restored: Database, sql: str, *args: object) -> None:
    """A change no role may make (triggers off): what a broken restore would hold."""
    await Planter(restored.superuser_dsn).run_untriggered(sql, *args)


def _side(database: Database) -> Side:
    return Side(database.owner_url, database.app_url)


@pytest.fixture
async def restored(source: Database, seeded: Seeded) -> AsyncIterator[Database]:
    yield await _restore(source)
    await dispose_engine()


async def _verify(
    source: Database,
    restored: Database,
    *,
    restore_started_at: datetime | None = None,
    rpo_lag_seconds: float | None = None,
) -> DrillReport:
    return await verify(
        env="staging",
        source=_side(source),
        restored=_side(restored),
        restore_point=datetime.now(UTC) + timedelta(minutes=1),
        settle=timedelta(0),
        restore_started_at=restore_started_at,
        rpo_lag_seconds=rpo_lag_seconds,
    )


async def test_a_clean_restore_passes(
    source: Database, restored: Database, seeded: Seeded
) -> None:
    started = datetime.now(UTC) - timedelta(minutes=12)
    report = await _verify(source, restored, restore_started_at=started, rpo_lag_seconds=212.0)
    assert report.passed, report.as_json()
    assert report.tenants == 1
    assert "audit_events" in report.tables_checked and "evidence_versions" in report.tables_checked
    assert (
        report.evidence_population >= 3 and report.evidence_sampled == report.evidence_population
    )
    assert report.seal_checks == ["audit_chain"]
    assert report.rpo_ok is True
    assert report.restore_to_verified_seconds is not None
    assert report.restore_to_verified_seconds >= 12 * 60


async def test_a_planted_fingerprint_mismatch_fails_the_drill(
    source: Database, restored: Database, seeded: Seeded, bucket_client: S3Client
) -> None:
    target = seeded.versions[0]
    key = str(
        await Seeder(restored.superuser_dsn).value(
            "SELECT storage_key FROM evidence_versions WHERE id = $1", target
        )
    )
    other = bucket_client.put_object(Bucket=BUCKET, Key=key, Body=b"not the sealed statement")
    await _plant(
        restored,
        "UPDATE evidence_versions SET storage_version_id = $1 WHERE id = $2",
        other["VersionId"],
        target,
    )
    report = await _verify(source, restored)
    assert not report.passed
    assert [m.evidence_version_id for m in report.evidence_mismatches] == [str(target)]
    assert report.evidence_mismatches[0].tenant_id == str(seeded.tenant_id)
    assert report.sequence_gaps == [] and report.count_mismatches == []


async def test_a_planted_sequence_gap_fails_the_drill(
    source: Database, restored: Database, seeded: Seeded
) -> None:
    seqs = [
        int(r[0])
        for r in await Seeder(restored.superuser_dsn).rows(
            "SELECT seq FROM audit_events WHERE tenant_id = $1 ORDER BY seq", seeded.tenant_id
        )
    ]
    assert len(seqs) >= 3
    gone = seqs[1]
    await _plant(restored, "DELETE FROM audit_events WHERE seq = $1", gone)
    report = await _verify(source, restored)
    assert not report.passed
    gap = next(g for g in report.sequence_gaps if g.tenant_id == str(seeded.tenant_id))
    assert (gap.first_missing_seq, gap.missing) == (gone, 1)
    counted = [m for m in report.count_mismatches if m.table == "audit_events"]
    assert [(m.tenant_id, m.source - m.restored) for m in counted] == [(str(seeded.tenant_id), 1)]


async def test_a_missing_row_in_an_insert_only_table_fails_the_drill(
    source: Database, restored: Database, seeded: Seeded
) -> None:
    await _plant(restored, "DELETE FROM evidence_versions WHERE id = $1", seeded.versions[2])
    report = await _verify(source, restored)
    assert not report.passed
    assert any(
        m.table == "evidence_versions" and m.tenant_id == str(seeded.tenant_id)
        for m in report.count_mismatches
    )


async def test_an_rpo_lag_over_five_minutes_fails_the_drill(
    source: Database, restored: Database
) -> None:
    report = await _verify(source, restored, rpo_lag_seconds=301.0)
    assert (report.rpo_ok, report.passed) == (False, False)


def test_the_sample_is_one_percent_with_a_floor_of_fifty() -> None:
    assert [sample_size(n) for n in (0, 3, 50, 51, 4_999, 5_000, 5_001, 12_345)] == [
        0,
        3,
        50,
        50,
        50,
        50,
        51,
        124,
    ]


def test_the_restored_urls_keep_credentials_and_swap_the_host() -> None:
    assert (
        with_host("postgresql+asyncpg://abacus_owner:pw@db.example.test:5432/abacus", "drill.test")
        == "postgresql+asyncpg://abacus_owner:pw@drill.test:5432/abacus"
    )


def test_the_report_carries_codes_counts_and_identifiers_only() -> None:
    report = DrillReport("production", "2026-12-08T03:14:00+00:00", "2026-12-08T03:09:00+00:00")
    report.evidence_mismatches.append(
        drill.EvidenceMismatch(str(uuid.uuid4()), str(uuid.uuid4()), "IntegrityError")
    )
    assert '"passed": false' in report.as_json()
    assert set(drill.EvidenceMismatch.__dataclass_fields__) == {
        "tenant_id",
        "evidence_version_id",
        "reason",
    }
