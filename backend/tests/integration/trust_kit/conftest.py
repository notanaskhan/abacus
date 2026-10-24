"""Wiring for the trust kit tests (P-03-T05, T06): engines on the test database and evidence
storage on a bucket of this package's own, reset around each test."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage

from .support import BUCKET, MASTER, Migrated, Seeder


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture(scope="module")
def bucket_client(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client
    listing = client.list_object_versions(Bucket=BUCKET)
    for entry in [*listing.get("Versions", []), *listing.get("DeleteMarkers", [])]:
        client.delete_object(
            Bucket=BUCKET,
            Key=entry.get("Key", ""),
            VersionId=entry.get("VersionId", ""),
            BypassGovernanceRetention=True,
        )
    client.delete_bucket(Bucket=BUCKET)


@pytest.fixture(autouse=True)
def evidence_storage(bucket_client: S3Client) -> Iterator[S3Client]:
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(bucket_client, BUCKET)
    yield bucket_client
    storage.reset_storage()
    reset_key_service()
