"""Write-once, content-addressed, encrypted evidence storage (ADR-016, ADR-104). PROTECTED.
TASK-009 design §1.

    stored = await put(tenant_id, content)        # key: tenants/<tenant>/sha256/<fingerprint>
    content = await get(tenant_id, stored)         # exactly that version, decrypted and verified

The fingerprint is the SHA-256 of the plaintext. Objects are sealed before they leave the process
(`kernel.crypto`), stored under Object Lock (governance mode) and never overwritten
(`If-None-Match: *`). Storing the same content twice returns the existing object.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING
from uuid import UUID

from botocore.exceptions import ClientError

from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.storage import s3_client

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client


class IntegrityError(Exception):
    """Stored content doesn't match its recorded fingerprint, key or version."""


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


async def _existing_version(target: _Target, key: str) -> str | None:
    try:
        head = await asyncio.to_thread(target.client.head_object, Bucket=target.bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            return None
        raise
    return head.get("VersionId") or "null"


async def put(tenant_id: UUID, content: bytes) -> StoredObject:
    target = _storage()
    digest = fingerprint(content)
    key = object_key(tenant_id, digest)
    existing = await _existing_version(target, key)
    if existing is not None:
        return StoredObject(key, existing, digest, len(content))
    sealed = await seal(tenant_id, content, digest)
    retain_until = datetime.now(UTC) + timedelta(days=settings().evidence_retention_days)
    try:
        response = await asyncio.to_thread(
            target.client.put_object,
            Bucket=target.bucket,
            Key=key,
            Body=sealed,
            ContentType="application/octet-stream",
            IfNoneMatch="*",
            ObjectLockMode="GOVERNANCE",
            ObjectLockRetainUntilDate=retain_until,
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "PreconditionFailed":
            raise
        # Another writer stored the same content first: same key, same plaintext.
        raced = await _existing_version(target, key)
        if raced is None:
            raise IntegrityError("object vanished after a conditional-write conflict") from None
        return StoredObject(key, raced, digest, len(content))
    return StoredObject(key, response.get("VersionId") or "null", digest, len(content))


async def get(tenant_id: UUID, stored: StoredObject) -> bytes:
    if stored.key != object_key(tenant_id, stored.fingerprint):
        raise IntegrityError("storage key does not match tenant and fingerprint")
    target = _storage()
    response = await asyncio.to_thread(
        target.client.get_object,
        Bucket=target.bucket,
        Key=stored.key,
        VersionId=stored.version_id,
    )
    sealed = await asyncio.to_thread(response["Body"].read)
    content = await open_sealed(tenant_id, sealed, stored.fingerprint)
    if fingerprint(content) != stored.fingerprint or len(content) != stored.size:
        raise IntegrityError("stored content does not match its fingerprint")
    return content
