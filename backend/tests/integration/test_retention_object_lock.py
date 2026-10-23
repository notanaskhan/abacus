"""Q-02-T24 against S3-compatible Object Lock and Postgres (Q-02 AC-32): every stored object's
retain-until is at or after its policy expiry, an anchor event extends it, and chain anchors land
in COMPLIANCE mode, where no one can delete them early. The records bucket is never emptied in
teardown: COMPLIANCE refuses, and the container is thrown away."""

from __future__ import annotations

import json
import secrets
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.storage import s3_client
from abacus.kernel.uow import Target, uow
from abacus.kernel.uow.chain import seal_checkpoint, verify_anchor
from abacus.modules.evidence import records, storage
from abacus.modules.evidence.retention import (
    extend_retention_for,
    import_set,
    publish_set,
    retain_until_for,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

EVIDENCE = "retention-evidence"
RECORDS = "retention-records"
MASTER = bytes(range(32))


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    for bucket in (EVIDENCE, RECORDS):
        client.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
async def wired(migrated_db: MigratedDatabase, raw: S3Client) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    records.configure_records(raw, RECORDS)
    yield
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    await dispose_engine()
    settings.cache_clear()


def _retention(client: S3Client, bucket: str, key: str, version: str) -> tuple[str, datetime]:
    found = client.get_object_retention(Bucket=bucket, Key=key, VersionId=version)["Retention"]
    until = found.get("RetainUntilDate")
    assert until is not None
    return str(found.get("Mode")), until


async def _client_document_floor(years: str) -> None:
    version = 1_000 + secrets.randbelow(9_000_000)
    await import_set(
        "floors",
        version,
        [
            {
                "record_type": "client_document",
                "service_line": "any",
                "legal_floor_years": years,
                "anchor": "report_release",
                "authority": "Probe authority",
            }
        ],
        "staff-a",
    )
    await publish_set("floors", version, "staff-b")


async def test_ac32_an_object_is_locked_until_its_policy_expiry(
    migrated_db: MigratedDatabase, raw: S3Client
) -> None:
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    await _client_document_floor("12")
    now = datetime.now(UTC)
    until = await retain_until_for(
        TenantContext(tenant, "system", "probe"), "client_document", "tax", now
    )
    assert until is not None
    assert abs(
        until - (now + timedelta(days=float(Decimal("12") * Decimal("365.25"))))
    ) < timedelta(minutes=1)
    stored = await storage.put(tenant, b"a brokerage statement", retain_until=until)
    mode, locked = _retention(raw, EVIDENCE, stored.key, stored.version_id)
    assert mode == "GOVERNANCE" and locked >= until - timedelta(seconds=1)


async def test_ac32_an_anchor_event_extends_the_lock(
    migrated_db: MigratedDatabase, raw: S3Client
) -> None:
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    await _client_document_floor("12")
    stored = await storage.put(tenant, b"a K-1 package")
    _mode, before = _retention(raw, EVIDENCE, stored.key, stored.version_id)
    released = datetime.now(UTC) + timedelta(days=200)  # the report release, later
    n = await extend_retention_for(
        TenantContext(tenant, "system", "probe"),
        [(stored.key, stored.version_id)],
        "client_document",
        "audit",
        released,
    )
    assert n == 1
    _mode, after = _retention(raw, EVIDENCE, stored.key, stored.version_id)
    assert after > before and after >= released + timedelta(days=12 * 365)


async def test_ac32_a_chain_anchor_lands_in_compliance_mode_and_verifies(
    migrated_db: MigratedDatabase, raw: S3Client
) -> None:
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    for _ in range(3):
        async with uow(TenantContext(tenant, "system", "probe")) as tx:
            tx.record("probe.recorded", target=Target("probe", uuid.uuid4()))
    checkpoint = await seal_checkpoint(tenant, settle_seconds=0)
    assert checkpoint is not None
    anchored = await records.anchor_chain(tenant, datetime.now(UTC) + timedelta(days=1))
    assert anchored is not None
    mode, _until = _retention(raw, RECORDS, anchored.key, anchored.version_id)
    assert mode == "COMPLIANCE"
    body = json.loads(
        raw.get_object(Bucket=RECORDS, Key=anchored.key, VersionId=anchored.version_id)[
            "Body"
        ].read()
    )
    assert body["checkpoint_no"] == checkpoint.checkpoint_no
    assert await verify_anchor(tenant, body["checkpoint_no"], bytes.fromhex(body["chain_hash"]))
    with pytest.raises(ClientError):
        raw.delete_object(
            Bucket=RECORDS,
            Key=anchored.key,
            VersionId=anchored.version_id,
            BypassGovernanceRetention=True,  # COMPLIANCE ignores it
        )


async def test_ac32_no_records_bucket_fails_closed() -> None:
    records.reset_records()
    with pytest.raises(records.RecordsUnavailable):
        await records.put_record(uuid.uuid4(), "seal_manifest", b"{}", datetime.now(UTC))
