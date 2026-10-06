"""Write-once, content-addressed, encrypted object storage (ADR-016, ADR-104). PROTECTED.
TASK-009 design §1, revision 1.

    stored = await put(tenant_id, content)        # key: tenants/<tenant>/sha256/<fingerprint>
    content = await get(tenant_id, stored)         # exactly that version, decrypted and verified

The fingerprint is the SHA-256 of the plaintext. Objects are sealed before they leave the process
(`kernel.crypto`), stored under Object Lock (governance mode) and written with `If-None-Match: *`.

Storing content that is already there reuses it, but only a version that verifies: an existing
object is fetched, opened and fingerprinted before its version is trusted. A key holding no valid
version (a corrupt or foreign object written by someone with bucket access) gets a fresh, valid
version alongside it; the bad ones stay locked but are never referenced. Reused versions have
their retention extended to the full period from now.

Call `put` before opening a unit of work: it is network I/O and must not hold a transaction.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.crypto import DecryptionError, open_sealed, seal
from abacus.kernel.storage import StorageError, error_code, s3_client

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

MAX_CONTENT_BYTES = 50 * 1024 * 1024  # a trial balance is kilobytes; uploads arrive later
_MISSING = ("404", "NoSuchKey", "NotFound", "NoSuchVersion")
_RACE = ("PreconditionFailed", "ConditionalRequestConflict")
_RETENTION_SLACK = timedelta(minutes=5)  # concurrent reusers' "now" differ by seconds


class IntegrityError(Exception):
    """Stored content doesn't match its recorded fingerprint, key or version."""


class ContentTooLarge(ValueError):
    """Content over MAX_CONTENT_BYTES."""


@dataclass(frozen=True)
class StoredObject:
    key: str
    version_id: str
    fingerprint: str
    size: int


@dataclass(frozen=True)
class _Target:
    client: S3Client
    bucket: str


_target: _Target | None = None


def configure_storage(client: S3Client, bucket: str) -> None:
    """Tests and local runs: point evidence storage at a client and bucket."""
    global _target
    _target = _Target(client, bucket)


def reset_storage() -> None:
    """Back to the storage built from settings (test teardown)."""
    global _target
    _target = None
    _from_settings.cache_clear()


@lru_cache(maxsize=1)
def _from_settings() -> _Target:
    bucket = settings().evidence_bucket
    if bucket is None:  # settings validation makes this unreachable outside local and test
        raise RuntimeError("evidence_bucket is not configured")
    return _Target(s3_client(), bucket)


def _storage() -> _Target:
    return _target if _target is not None else _from_settings()


def fingerprint(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def object_key(tenant_id: UUID, content_fingerprint: str) -> str:
    return f"tenants/{tenant_id}/sha256/{content_fingerprint}"


def _retain_until() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings().evidence_retention_days)


async def _versions(target: _Target, key: str) -> list[str]:
    """Version IDs stored under exactly this key, newest first."""
    listing = await asyncio.to_thread(
        target.client.list_object_versions, Bucket=target.bucket, Prefix=key
    )
    versions = [v for v in listing.get("Versions", []) if v.get("Key") == key]
    versions.sort(key=lambda v: v.get("LastModified") or datetime.min.replace(tzinfo=UTC))
    return [str(version_id) for v in reversed(versions) if (version_id := v.get("VersionId"))]


async def _read(target: _Target, key: str, version_id: str) -> bytes:
    response = await asyncio.to_thread(
        target.client.get_object, Bucket=target.bucket, Key=key, VersionId=version_id
    )
    return await asyncio.to_thread(response["Body"].read)


async def _verified(target: _Target, tenant_id: UUID, key: str, digest: str) -> str | None:
    """The newest version under `key` that opens for this tenant and matches `digest`."""
    for version_id in await _versions(target, key):
        try:
            content = await open_sealed(tenant_id, await _read(target, key, version_id), digest)
        except DecryptionError:
            continue
        if fingerprint(content) == digest:
            return version_id
    return None


async def _retained_until(target: _Target, key: str, version_id: str) -> datetime | None:
    current = await asyncio.to_thread(
        target.client.get_object_retention, Bucket=target.bucket, Key=key, VersionId=version_id
    )
    return current.get("Retention", {}).get("RetainUntilDate")


async def _extend_retention(target: _Target, key: str, version_id: str) -> None:
    """A reused version is locked for the full period from now. Governance mode only extends.
    Concurrent reusers each ask for "now + period", so a slower one may ask for slightly less than
    a faster one already set; the store refuses that as a shortening, which is fine."""
    required = _retain_until()
    until = await _retained_until(target, key, version_id)
    if until is not None and until >= required:
        return
    try:
        await asyncio.to_thread(
            target.client.put_object_retention,
            Bucket=target.bucket,
            Key=key,
            VersionId=version_id,
            Retention={"Mode": "GOVERNANCE", "RetainUntilDate": required},
        )
    except StorageError as exc:
        if error_code(exc) != "AccessDenied":
            raise
        until = await _retained_until(target, key, version_id)
        if until is None or until < required - _RETENTION_SLACK:
            raise


async def _write(target: _Target, key: str, sealed: bytes, *, conditional: bool) -> str | None:
    """A new version; None if a conditional write lost a race."""
    try:
        if conditional:
            response = await asyncio.to_thread(
                target.client.put_object,
                Bucket=target.bucket,
                Key=key,
                Body=sealed,
                ContentType="application/octet-stream",
                IfNoneMatch="*",
                ObjectLockMode="GOVERNANCE",
                ObjectLockRetainUntilDate=_retain_until(),
            )
        else:
            response = await asyncio.to_thread(
                target.client.put_object,
                Bucket=target.bucket,
                Key=key,
                Body=sealed,
                ContentType="application/octet-stream",
                ObjectLockMode="GOVERNANCE",
                ObjectLockRetainUntilDate=_retain_until(),
            )
    except StorageError as exc:
        if conditional and error_code(exc) in _RACE:
            return None
        raise
    version_id = response.get("VersionId")
    if not version_id or version_id == "null":
        # Without versioning a pinned read means nothing: refuse rather than record it.
        raise IntegrityError("the evidence bucket must have versioning and Object Lock")
    return version_id


async def put(tenant_id: UUID, content: bytes) -> StoredObject:
    if len(content) > MAX_CONTENT_BYTES:
        raise ContentTooLarge(f"content over {MAX_CONTENT_BYTES} bytes")
    target = _storage()
    digest = fingerprint(content)
    key = object_key(tenant_id, digest)
    for _ in range(3):
        if await _versions(target, key):
            existing = await _verified(target, tenant_id, key, digest)
            if existing is not None:
                await _extend_retention(target, key, existing)
                return StoredObject(key, existing, digest, len(content))
            # Only invalid versions under this key: add a valid one beside them.
            sealed = await seal(tenant_id, content, digest)
            fresh = await _write(target, key, sealed, conditional=False)
            if fresh is None:  # unreachable: unconditional writes don't race
                raise IntegrityError("unconditional write reported a conflict")
            return StoredObject(key, fresh, digest, len(content))
        sealed = await seal(tenant_id, content, digest)
        written = await _write(target, key, sealed, conditional=True)
        if written is not None:
            return StoredObject(key, written, digest, len(content))
        # Lost a race to another writer of the same key: loop and verify what it wrote.
    raise IntegrityError("could not store or verify content after repeated conflicts")


async def get(tenant_id: UUID, stored: StoredObject) -> bytes:
    if stored.key != object_key(tenant_id, stored.fingerprint):
        raise IntegrityError("storage key does not match tenant and fingerprint")
    target = _storage()
    try:
        sealed = await _read(target, stored.key, stored.version_id)
    except StorageError as exc:
        if error_code(exc) in _MISSING:
            raise IntegrityError("recorded object version is missing") from None
        raise
    content = await open_sealed(tenant_id, sealed, stored.fingerprint)
    if fingerprint(content) != stored.fingerprint or len(content) != stored.size:
        raise IntegrityError("stored content does not match its fingerprint")
    return content


async def check_ready() -> None:
    """Startup check (workers, TASK-010b): the bucket is reachable and write-once."""
    target = _storage()
    lock = await asyncio.to_thread(
        target.client.get_object_lock_configuration, Bucket=target.bucket
    )
    if lock.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") != "Enabled":
        raise RuntimeError("the evidence bucket must have Object Lock enabled")
