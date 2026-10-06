"""AC-13 / AC-20: write-once, content-addressed, encrypted evidence storage against the Versity
gateway (TASK-009 interface contract, "Storage" and "Tooling"; ADR-016, ADR-104).

One bucket with Object Lock for the module; every test uses fresh tenant IDs and content, so tests
never need cleanup between them. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from botocore.exceptions import ClientError
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.crypto import (
    DecryptionError,
    LocalKeyService,
    configure_key_service,
    reset_key_service,
)
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.evidence.storage import ContentTooLarge, IntegrityError, StoredObject
from abacus_tools.local.evidence_bucket import ensure_bucket

MASTER = b"storage-test-master-key-0123456789abcdef"
BUCKET = f"evidence-storage-{uuid.uuid4().hex[:12]}"
STAGING_ENV = {
    "ABACUS_DATABASE_URL": "postgresql+asyncpg://app@db.example.test:5432/abacus",
    "ABACUS_MIGRATIONS_DATABASE_URL": "postgresql+asyncpg://owner@db.example.test:5432/abacus",
    "ABACUS_RELAY_DATABASE_URL": "postgresql+asyncpg://relay@db.example.test:5432/abacus",
    "ABACUS_IDENTITY_DATABASE_URL": "postgresql+asyncpg://identity@db.example.test:5432/abacus",
    "ABACUS_IDENTITY_ISSUER": "https://idp.example.test",
    "ABACUS_IDENTITY_AUDIENCE": "abacus-api",
    "ABACUS_IDENTITY_JWKS": '{"keys": []}',
    "ABACUS_S3_ENDPOINT_URL": "https://s3.example.test",
    "ABACUS_S3_ACCESS_KEY": "access",
    "ABACUS_S3_SECRET_KEY": "secret",
    "ABACUS_EVIDENCE_BUCKET": "evidence-bucket",
    "ABACUS_TEMPORAL_TARGET": "temporal.example.test:7233",
    "ABACUS_TEMPORAL_PAYLOAD_KEY": "test-payload-key-Zq8Xv2Lm9Wd4Rt7Bn3Hs",
    "ABACUS_TEMPORAL_TLS": "true",
    "ABACUS_TEMPORAL_API_KEY": "example-temporal-api-key-public-not-secret",
}


def _empty_and_delete(client: S3Client, bucket: str) -> None:
    listing = client.list_object_versions(Bucket=bucket)
    for entry in [*listing.get("Versions", []), *listing.get("DeleteMarkers", [])]:
        client.delete_object(
            Bucket=bucket,
            Key=entry.get("Key", ""),
            VersionId=entry.get("VersionId", ""),
            BypassGovernanceRetention=True,
        )
    client.delete_bucket(Bucket=bucket)


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=BUCKET, ObjectLockEnabledForBucket=True)
    yield client
    _empty_and_delete(client, BUCKET)


@pytest.fixture
def configured(raw: S3Client) -> Iterator[S3Client]:
    """Storage and the key service point at this module's bucket; both reset in teardown."""
    reset_key_service()
    storage.reset_storage()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, BUCKET)
    yield raw
    storage.reset_storage()
    reset_key_service()


@pytest.fixture
def fresh_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[pytest.MonkeyPatch]:
    for key in list(os.environ):
        if key.startswith("ABACUS_"):
            monkeypatch.delenv(key)
    settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    settings.cache_clear()


def _content(label: str = "evidence") -> bytes:
    return f"{label} {uuid.uuid4()} confidential figures 1,234.56".encode()


def _raw_body(client: S3Client, stored: StoredObject) -> bytes:
    body = client.get_object(Bucket=BUCKET, Key=stored.key, VersionId=stored.version_id)["Body"]
    return body.read()


def _versions_of(client: S3Client, key: str) -> list[str]:
    listing = client.list_object_versions(Bucket=BUCKET, Prefix=key)
    return [v.get("VersionId", "") for v in listing.get("Versions", []) if v.get("Key") == key]


# --- helpers ---------------------------------------------------------------------------------


def test_ac13_fingerprint_is_the_sha256_hex_of_the_plaintext() -> None:
    assert storage.fingerprint(b"abc") == hashlib.sha256(b"abc").hexdigest()


def test_ac13_object_key_is_tenant_scoped_and_content_addressed() -> None:
    tenant = uuid.uuid4()
    assert storage.object_key(tenant, "f" * 64) == f"tenants/{tenant}/sha256/{'f' * 64}"


# --- put -------------------------------------------------------------------------------------


async def test_ac13_put_returns_the_content_addressed_object(configured: S3Client) -> None:
    tenant, content = uuid.uuid4(), _content()
    stored = await storage.put(tenant, content)
    digest = hashlib.sha256(content).hexdigest()
    assert stored.key == f"tenants/{tenant}/sha256/{digest}"
    assert stored.fingerprint == digest
    assert stored.size == len(content)
    assert stored.version_id


async def test_ac13_the_stored_bytes_are_sealed_not_plaintext(configured: S3Client) -> None:
    content = _content()
    stored = await storage.put(uuid.uuid4(), content)
    body = _raw_body(configured, stored)
    assert body.startswith(b"ABE1")
    assert content not in body
    assert b"confidential" not in body


async def test_ac13_the_object_is_locked_in_governance_mode_for_the_retention_period(
    configured: S3Client,
) -> None:
    stored = await storage.put(uuid.uuid4(), _content())
    retention = configured.get_object_retention(
        Bucket=BUCKET, Key=stored.key, VersionId=stored.version_id
    )["Retention"]
    assert retention.get("Mode") == "GOVERNANCE"
    until = retention.get("RetainUntilDate")
    assert until is not None
    expected = datetime.now(UTC) + timedelta(days=settings().evidence_retention_days)
    assert abs(until - expected) < timedelta(days=1)


async def test_ac13_retention_follows_the_evidence_retention_days_setting(
    configured: S3Client, fresh_settings: pytest.MonkeyPatch
) -> None:
    fresh_settings.setenv("ABACUS_EVIDENCE_RETENTION_DAYS", "400")
    settings.cache_clear()
    stored = await storage.put(uuid.uuid4(), _content())
    retention = configured.get_object_retention(
        Bucket=BUCKET, Key=stored.key, VersionId=stored.version_id
    )["Retention"]
    until = retention.get("RetainUntilDate")
    assert until is not None
    assert abs(until - (datetime.now(UTC) + timedelta(days=400))) < timedelta(days=1)


async def test_ac13_putting_the_same_content_again_returns_the_same_object(
    configured: S3Client,
) -> None:
    tenant, content = uuid.uuid4(), _content()
    first = await storage.put(tenant, content)
    second = await storage.put(tenant, content)
    assert second.key == first.key
    assert second.version_id == first.version_id
    assert second == first
    assert _versions_of(configured, first.key) == [first.version_id]


async def test_ac13_concurrent_puts_of_the_same_content_create_one_object_version(
    configured: S3Client,
) -> None:
    tenant, content = uuid.uuid4(), _content()
    results = await asyncio.gather(*(storage.put(tenant, content) for _ in range(6)))
    assert len({r.key for r in results}) == 1
    assert len({r.version_id for r in results}) == 1
    assert len(_versions_of(configured, results[0].key)) == 1
    assert await storage.get(tenant, results[0]) == content


async def test_ac13_the_same_content_under_two_tenants_is_two_objects(
    configured: S3Client,
) -> None:
    content = _content()
    first = await storage.put(uuid.uuid4(), content)
    second = await storage.put(uuid.uuid4(), content)
    assert first.fingerprint == second.fingerprint
    assert first.key != second.key


async def test_ac13_a_direct_conditional_put_over_an_existing_key_is_refused(
    configured: S3Client,
) -> None:
    stored = await storage.put(uuid.uuid4(), _content())
    with pytest.raises(ClientError) as raised:
        configured.put_object(
            Bucket=BUCKET, Key=stored.key, Body=b"different bytes", IfNoneMatch="*"
        )
    assert raised.value.response.get("Error", {}).get("Code") == "PreconditionFailed"
    assert _versions_of(configured, stored.key) == [stored.version_id]


async def test_ac13_deleting_the_object_version_is_refused_by_object_lock(
    configured: S3Client,
) -> None:
    stored = await storage.put(uuid.uuid4(), _content())
    with pytest.raises(ClientError) as raised:
        configured.delete_object(Bucket=BUCKET, Key=stored.key, VersionId=stored.version_id)
    assert raised.value.response.get("Error", {}).get("Code") == "AccessDenied"
    assert _versions_of(configured, stored.key) == [stored.version_id]


# --- get -------------------------------------------------------------------------------------


@pytest.mark.parametrize("size", [0, 1, 4096, 1_500_000])
async def test_ac13_get_returns_the_original_bytes(configured: S3Client, size: int) -> None:
    tenant = uuid.uuid4()
    content = (uuid.uuid4().bytes * (size // 16 + 1))[:size]
    stored = await storage.put(tenant, content)
    assert stored.size == size
    assert await storage.get(tenant, stored) == content


async def test_ac13_get_pins_the_recorded_version(configured: S3Client) -> None:
    tenant, content = uuid.uuid4(), _content()
    stored = await storage.put(tenant, content)
    configured.put_object(Bucket=BUCKET, Key=stored.key, Body=b"a later, unlocked overwrite")
    assert len(_versions_of(configured, stored.key)) == 2
    assert await storage.get(tenant, stored) == content


async def test_ac13_get_for_another_tenant_is_an_integrity_error(configured: S3Client) -> None:
    stored = await storage.put(uuid.uuid4(), _content())
    with pytest.raises(IntegrityError):
        await storage.get(uuid.uuid4(), stored)


async def test_ac13_get_with_a_key_that_does_not_match_tenant_and_fingerprint_is_refused(
    configured: S3Client,
) -> None:
    tenant = uuid.uuid4()
    stored = await storage.put(tenant, _content())
    other = await storage.put(tenant, _content())
    wrong_key = StoredObject(other.key, stored.version_id, stored.fingerprint, stored.size)
    with pytest.raises(IntegrityError):
        await storage.get(tenant, wrong_key)
    wrong_fingerprint = StoredObject(stored.key, stored.version_id, "0" * 64, stored.size)
    with pytest.raises(IntegrityError):
        await storage.get(tenant, wrong_fingerprint)


async def test_ac13_a_tampered_stored_object_is_refused(configured: S3Client) -> None:
    tenant, content = uuid.uuid4(), _content()
    stored = await storage.put(tenant, content)
    sealed = bytearray(_raw_body(configured, stored))
    sealed[-1] ^= 0x01
    forged_key = storage.object_key(tenant, hashlib.sha256(b"forged " + content).hexdigest())
    version = configured.put_object(Bucket=BUCKET, Key=forged_key, Body=bytes(sealed))
    forged = StoredObject(
        forged_key,
        version.get("VersionId", ""),
        hashlib.sha256(b"forged " + content).hexdigest(),
        stored.size,
    )
    with pytest.raises((DecryptionError, IntegrityError)):
        await storage.get(tenant, forged)


async def test_ac13_an_object_stored_under_another_fingerprint_is_refused(
    configured: S3Client,
) -> None:
    tenant, content = uuid.uuid4(), _content()
    stored = await storage.put(tenant, content)
    other_digest = hashlib.sha256(b"someone else's content " + content).hexdigest()
    copy_key = storage.object_key(tenant, other_digest)
    version = configured.put_object(
        Bucket=BUCKET, Key=copy_key, Body=_raw_body(configured, stored)
    )
    swapped = StoredObject(copy_key, version.get("VersionId", ""), other_digest, stored.size)
    with pytest.raises((DecryptionError, IntegrityError)):
        await storage.get(tenant, swapped)


async def test_ac13_an_object_copied_to_another_tenants_key_is_refused(
    configured: S3Client,
) -> None:
    owner, intruder, content = uuid.uuid4(), uuid.uuid4(), _content()
    stored = await storage.put(owner, content)
    copy_key = storage.object_key(intruder, stored.fingerprint)
    version = configured.put_object(
        Bucket=BUCKET, Key=copy_key, Body=_raw_body(configured, stored)
    )
    replayed = StoredObject(
        copy_key, version.get("VersionId", ""), stored.fingerprint, stored.size
    )
    with pytest.raises((DecryptionError, IntegrityError)):
        await storage.get(intruder, replayed)


async def test_ac13_a_wrong_size_in_the_record_is_refused(configured: S3Client) -> None:
    tenant = uuid.uuid4()
    stored = await storage.put(tenant, _content())
    lying = StoredObject(stored.key, stored.version_id, stored.fingerprint, stored.size + 1)
    with pytest.raises(IntegrityError):
        await storage.get(tenant, lying)


# --- revision 1: verified reuse, size cap, missing versions ----------------------------------


async def test_ac13_content_over_50_mib_is_refused_and_nothing_is_stored(
    configured: S3Client,
) -> None:
    tenant = uuid.uuid4()
    content = b"\0" * (50 * 1024 * 1024 + 1)
    with pytest.raises(ContentTooLarge):
        await storage.put(tenant, content)
    key = storage.object_key(tenant, hashlib.sha256(content).hexdigest())
    assert _versions_of(configured, key) == []


async def test_ac13_put_skips_a_garbage_version_and_writes_a_valid_one_beside_it(
    configured: S3Client,
) -> None:
    tenant, content = uuid.uuid4(), _content()
    digest = hashlib.sha256(content).hexdigest()
    key = storage.object_key(tenant, digest)
    poisoned = configured.put_object(Bucket=BUCKET, Key=key, Body=b"ABE1 planted garbage")
    poisoned_id = poisoned.get("VersionId", "")
    stored = await storage.put(tenant, content)
    assert stored.key == key
    assert stored.version_id != poisoned_id
    assert await storage.get(tenant, stored) == content
    assert set(_versions_of(configured, key)) == {poisoned_id, stored.version_id}
    again = await storage.put(tenant, content)
    assert again.version_id == stored.version_id


async def test_ac13_put_does_not_trust_another_tenants_object_at_its_key(
    configured: S3Client,
) -> None:
    owner, victim, content = uuid.uuid4(), uuid.uuid4(), _content()
    theirs = await storage.put(owner, content)
    key = storage.object_key(victim, theirs.fingerprint)
    planted = configured.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=configured.get_object(Bucket=BUCKET, Key=theirs.key, VersionId=theirs.version_id)[
            "Body"
        ].read(),
    )
    stored = await storage.put(victim, content)
    assert stored.version_id != planted.get("VersionId")
    assert await storage.get(victim, stored) == content


async def test_ac13_reusing_an_object_extends_its_retention_to_the_full_period(
    configured: S3Client, fresh_settings: pytest.MonkeyPatch
) -> None:
    tenant, content = uuid.uuid4(), _content()
    fresh_settings.setenv("ABACUS_EVIDENCE_RETENTION_DAYS", "400")
    settings.cache_clear()
    first = await storage.put(tenant, content)
    fresh_settings.setenv("ABACUS_EVIDENCE_RETENTION_DAYS", "800")
    settings.cache_clear()
    second = await storage.put(tenant, content)
    assert second.version_id == first.version_id
    retention = configured.get_object_retention(
        Bucket=BUCKET, Key=first.key, VersionId=first.version_id
    )["Retention"]
    until = retention.get("RetainUntilDate")
    assert until is not None
    assert retention.get("Mode") == "GOVERNANCE"
    assert abs(until - (datetime.now(UTC) + timedelta(days=800))) < timedelta(days=1)


async def test_ac13_get_of_a_missing_version_is_an_integrity_error(
    configured: S3Client,
) -> None:
    tenant, content = uuid.uuid4(), _content()
    digest = hashlib.sha256(content).hexdigest()
    key = storage.object_key(tenant, digest)
    gone = configured.put_object(Bucket=BUCKET, Key=key, Body=b"unlocked, soon deleted")
    gone_id = gone.get("VersionId", "")
    configured.delete_object(Bucket=BUCKET, Key=key, VersionId=gone_id)
    with pytest.raises(IntegrityError):
        await storage.get(tenant, StoredObject(key, gone_id, digest, len(content)))


def test_ac13_the_retention_floor_is_365_days(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.setenv("ABACUS_EVIDENCE_RETENTION_DAYS", "364")
    settings.cache_clear()
    with pytest.raises(ValueError):
        settings()
    fresh_settings.setenv("ABACUS_EVIDENCE_RETENTION_DAYS", "365")
    settings.cache_clear()
    assert settings().evidence_retention_days == 365


# --- the S3 factory --------------------------------------------------------------------------


def test_ac20_s3_client_factory_builds_a_working_client_from_arguments(
    raw: S3Client, s3_settings: dict[str, str]
) -> None:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    names = {b.get("Name") for b in client.list_buckets().get("Buckets", [])}
    assert BUCKET in names


# --- ensure_bucket ---------------------------------------------------------------------------


def _point_settings_at(
    monkeypatch: pytest.MonkeyPatch, s3_settings: dict[str, str], bucket: str
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "test")
    monkeypatch.setenv("ABACUS_S3_ENDPOINT_URL", s3_settings["endpoint_url"])
    monkeypatch.setenv("ABACUS_S3_ACCESS_KEY", s3_settings["access_key"])
    monkeypatch.setenv("ABACUS_S3_SECRET_KEY", s3_settings["secret_key"])
    monkeypatch.setenv("ABACUS_EVIDENCE_BUCKET", bucket)
    settings.cache_clear()


def test_ac20_ensure_bucket_creates_the_configured_bucket_with_object_lock(
    raw: S3Client, s3_settings: dict[str, str], fresh_settings: pytest.MonkeyPatch
) -> None:
    bucket = f"ensure-bucket-{uuid.uuid4().hex[:12]}"
    _point_settings_at(fresh_settings, s3_settings, bucket)
    try:
        assert ensure_bucket() == bucket
        config = raw.get_object_lock_configuration(Bucket=bucket)
        assert config.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") == "Enabled"
    finally:
        raw.delete_bucket(Bucket=bucket)


def test_ac20_ensure_bucket_is_idempotent(
    raw: S3Client, s3_settings: dict[str, str], fresh_settings: pytest.MonkeyPatch
) -> None:
    bucket = f"ensure-twice-{uuid.uuid4().hex[:12]}"
    _point_settings_at(fresh_settings, s3_settings, bucket)
    try:
        assert ensure_bucket() == bucket
        raw.put_object(Bucket=bucket, Key="kept", Body=b"still here")
        assert ensure_bucket() == bucket
        assert raw.get_object(Bucket=bucket, Key="kept")["Body"].read() == b"still here"
        config = raw.get_object_lock_configuration(Bucket=bucket)
        assert config.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") == "Enabled"
    finally:
        _empty_and_delete(raw, bucket)


def test_ac20_ensure_bucket_refuses_an_existing_bucket_without_object_lock(
    raw: S3Client, s3_settings: dict[str, str], fresh_settings: pytest.MonkeyPatch
) -> None:
    bucket = f"no-lock-bucket-{uuid.uuid4().hex[:12]}"
    raw.create_bucket(Bucket=bucket)
    _point_settings_at(fresh_settings, s3_settings, bucket)
    try:
        with pytest.raises(RuntimeError):
            ensure_bucket()
    finally:
        raw.delete_bucket(Bucket=bucket)


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_ensure_bucket_refuses_to_run_outside_local_and_test(
    fresh_settings: pytest.MonkeyPatch, environment: str
) -> None:
    for key, value in STAGING_ENV.items():
        fresh_settings.setenv(key, value)
    fresh_settings.setenv("ABACUS_ENVIRONMENT", environment)
    settings.cache_clear()
    with pytest.raises(RuntimeError):
        ensure_bucket()
