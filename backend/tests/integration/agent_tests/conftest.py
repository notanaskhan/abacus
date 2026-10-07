"""Fixtures for the TASK-011a integration tests: the same wiring as the retrieval tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from types_boto3_s3 import S3Client

from abacus.ai_gateway import FakeModel, configure_provider
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import configure_engine, configure_relay_engine, dispose_engine
from abacus.kernel.storage import s3_client
from abacus.modules.agents.api import install_fake_responses
from abacus.modules.evidence import storage

from .support import Migrated, Seeder, World, make_world

MASTER = b"agents-test-master-key-0123456789abcdef"
BUCKET = f"agents-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def seed(migrated_db: Migrated) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
def fake_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    directory = tmp_path / "fake-connector"
    directory.mkdir()
    monkeypatch.setenv("ABACUS_FAKE_CONNECTOR_DIR", str(directory))
    settings.cache_clear()
    yield directory
    monkeypatch.undo()
    settings.cache_clear()


@pytest.fixture
async def world(seed: Seeder, fake_dir: Path) -> World:
    return await make_world(seed, fake_dir)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch, fake_dir: Path
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
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


@pytest.fixture
def fake_model() -> Iterator[FakeModel]:
    """The configured provider: a `FakeModel` with the screener's stock responder installed."""
    fake = FakeModel()
    install_fake_responses(fake)
    configure_provider(fake)
    yield fake
    configure_provider(None)
