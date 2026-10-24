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

Detached-key mode (ADR-162 §5; P-06-T18), for client-channel uploads only:

    stored, key = await put_detached(tenant_id, version_id, content)   # tenants/<t>/v/<version>
    derived = await put(tenant_id, preview_png, under=version_id)      # tenants/<t>/vd/<v>/<fp>

The object is never shared by deduplication; it is sealed with envelope v2 under a data key of
its own whose wrapped form the caller keeps in `evidence_object_keys`, and the version's derived
records (extractions, previews, word layers) are sealed under the same key, so destroying that one
row erases them all. `get` finds the key through `object_keys.key_for`; a destroyed key reads as
`KeyDestroyed`.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.crypto import (
    DecryptionError,
    DetachedKey,
    open_detached,
    open_sealed,
    seal,
    seal_detached,
    seal_under,
)
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


class KeyDestroyed(IntegrityError):
    """A detached-key object whose key was destroyed (a crypto-erased withdrawal): it can no
    longer be opened by anyone (ADR-162 §5)."""


_DETACHED_PATH = re.compile(
    r"tenants/(?P<tenant>[0-9a-f-]{36})/"
    r"(?:v/(?P<version>[0-9a-f-]{36})|vd/(?P<owner>[0-9a-f-]{36})/(?P<derived>[0-9a-f]{64}))"
)


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


def detached_path(tenant_id: UUID, version_id: UUID) -> str:
    return f"tenants/{tenant_id}/v/{version_id}"


def derived_path(tenant_id: UUID, version_id: UUID, content_fingerprint: str) -> str:
    # A sibling tree, not under the object's own key: an object key is never also a "folder".
    return f"tenants/{tenant_id}/vd/{version_id}/{content_fingerprint}"


def is_detached(key: str) -> bool:
    return _DETACHED_PATH.fullmatch(key) is not None


def _binding(version_id: UUID, content_fingerprint: str, *, derived: bool) -> str:
    return f"{'d' if derived else 'o'}:{version_id}:{content_fingerprint}"


async def _key_of(tenant_id: UUID, version_id: UUID) -> DetachedKey:
    from abacus.modules.evidence.object_keys import key_for  # the key rows (a session)

    found = await key_for(tenant_id, version_id)
    if found is None:
        raise KeyDestroyed("the object's key was destroyed or never stored")
    return found


def _retain_until(at_least: datetime | None = None) -> datetime:
    """The default period from now (`evidence_retention_days`), or a record class's later date
    (Q-02-T24): an object is never locked for less than either."""
    default = system_now() + timedelta(days=settings().evidence_retention_days)
    return default if at_least is None or at_least < default else at_least


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


Opener = Callable[[bytes], Awaitable[bytes]]


async def _verified(
    target: _Target, tenant_id: UUID, key: str, digest: str, opener: Opener | None = None
) -> str | None:
    """The newest version under `key` that opens for this tenant and matches `digest`."""

    async def by_envelope(sealed: bytes) -> bytes:
        return await open_sealed(tenant_id, sealed, digest)

    open_one = opener or by_envelope
    for version_id in await _versions(target, key):
        try:
            content = await open_one(await _read(target, key, version_id))
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


async def _extend_retention(
    target: _Target, key: str, version_id: str, at_least: datetime | None = None
) -> None:
    """A reused version is locked for the full period from now (or a record class's later date).
    Governance mode only extends. Concurrent reusers each ask for "now + period", so a slower one
    may ask for slightly less than a faster one already set; the store refuses that as a
    shortening, which is fine."""
    required = _retain_until(at_least)
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


async def _write(
    target: _Target, key: str, sealed: bytes, *, conditional: bool, at_least: datetime | None
) -> str | None:
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
                ObjectLockRetainUntilDate=_retain_until(at_least),
            )
        else:
            response = await asyncio.to_thread(
                target.client.put_object,
                Bucket=target.bucket,
                Key=key,
                Body=sealed,
                ContentType="application/octet-stream",
                ObjectLockMode="GOVERNANCE",
                ObjectLockRetainUntilDate=_retain_until(at_least),
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


async def put(
    tenant_id: UUID,
    content: bytes,
    *,
    retain_until: datetime | None = None,
    under: UUID | None = None,
) -> StoredObject:
    """Store `content`; `retain_until` is its record class's policy expiry, when known
    (Q-02-T24, provisional at upload): the lock is never shorter than it or the default.
    `under` names a detached-key version this content is derived from (ADR-162 §6): it is then
    stored beside that version and sealed under its key."""
    if len(content) > MAX_CONTENT_BYTES:
        raise ContentTooLarge(f"content over {MAX_CONTENT_BYTES} bytes")
    target = _storage()
    digest = fingerprint(content)
    opener: Opener | None = None
    if under is not None:
        detached = await _key_of(tenant_id, under)
        key = derived_path(tenant_id, under, digest)
        binding = _binding(under, digest, derived=True)

        async def sealer() -> bytes:
            return await seal_under(tenant_id, content, binding, detached)

        async def open_derived(sealed: bytes) -> bytes:
            return await open_detached(tenant_id, sealed, binding, detached)

        opener = open_derived
    else:
        key = object_key(tenant_id, digest)

        async def sealer() -> bytes:
            return await seal(tenant_id, content, digest)

    for _ in range(3):
        if await _versions(target, key):
            existing = await _verified(target, tenant_id, key, digest, opener)
            if existing is not None:
                await _extend_retention(target, key, existing, retain_until)
                return StoredObject(key, existing, digest, len(content))
            # Only invalid versions under this key: add a valid one beside them.
            sealed = await sealer()
            fresh = await _write(target, key, sealed, conditional=False, at_least=retain_until)
            if fresh is None:  # unreachable: unconditional writes don't race
                raise IntegrityError("unconditional write reported a conflict")
            return StoredObject(key, fresh, digest, len(content))
        sealed = await sealer()
        written = await _write(target, key, sealed, conditional=True, at_least=retain_until)
        if written is not None:
            return StoredObject(key, written, digest, len(content))
        # Lost a race to another writer of the same key: loop and verify what it wrote.
    raise IntegrityError("could not store or verify content after repeated conflicts")


async def put_detached(
    tenant_id: UUID, version_id: UUID, content: bytes, *, retain_until: datetime | None = None
) -> tuple[StoredObject, DetachedKey]:
    """Store a client-channel upload in detached-key mode (ADR-162 §5) under its own version's
    key, never shared: the caller records the returned key in `evidence_object_keys` in the unit
    of work that inserts the version. Call it before that unit of work, like `put`."""
    if len(content) > MAX_CONTENT_BYTES:
        raise ContentTooLarge(f"content over {MAX_CONTENT_BYTES} bytes")
    target = _storage()
    digest = fingerprint(content)
    key = detached_path(tenant_id, version_id)
    sealed, detached = await seal_detached(
        tenant_id, content, _binding(version_id, digest, derived=False)
    )
    written = await _write(target, key, sealed, conditional=True, at_least=retain_until)
    if written is None:  # a fresh version id never collides; refuse rather than share
        raise IntegrityError("a detached-key object already exists for this version")
    return StoredObject(key, written, digest, len(content)), detached


async def extend_retention(stored: StoredObject, until: datetime) -> None:
    """Lock a stored version until at least `until` (an anchor event moved its policy expiry,
    Q-02-T24). Governance mode only ever extends."""
    await _extend_retention(_storage(), stored.key, stored.version_id, until)


async def set_legal_hold(stored: StoredObject, *, on: bool) -> None:
    """Set or clear the S3 object legal hold on exactly this version (Q-02-T29). Idempotent; a
    held version can't be deleted whatever its retention date. Reference counting across holds is
    `holds.py`'s: this only does what it is told."""
    target = _storage()
    await asyncio.to_thread(
        target.client.put_object_legal_hold,
        Bucket=target.bucket,
        Key=stored.key,
        VersionId=stored.version_id,
        LegalHold={"Status": "ON" if on else "OFF"},
    )


async def legal_hold_on(stored: StoredObject) -> bool:
    """Whether the S3 object legal hold is on for this version (the nightly reconciliation and
    tests read it; the hold check reads the database)."""
    target = _storage()
    try:
        found = await asyncio.to_thread(
            target.client.get_object_legal_hold,
            Bucket=target.bucket,
            Key=stored.key,
            VersionId=stored.version_id,
        )
    except StorageError as exc:
        if error_code(exc) in ("NoSuchObjectLockConfiguration", "ObjectLockConfigurationNotFound"):
            return False
        raise
    return found.get("LegalHold", {}).get("Status") == "ON"


async def get(tenant_id: UUID, stored: StoredObject) -> bytes:
    detached = _DETACHED_PATH.fullmatch(stored.key)
    if detached is not None:
        if detached["tenant"] != str(tenant_id) or (
            detached["derived"] is not None and detached["derived"] != stored.fingerprint
        ):
            raise IntegrityError("storage key does not match tenant and fingerprint")
    elif stored.key != object_key(tenant_id, stored.fingerprint):
        raise IntegrityError("storage key does not match tenant and fingerprint")
    target = _storage()
    try:
        sealed = await _read(target, stored.key, stored.version_id)
    except StorageError as exc:
        if error_code(exc) in _MISSING:
            raise IntegrityError("recorded object version is missing") from None
        raise
    if detached is None:
        content = await open_sealed(tenant_id, sealed, stored.fingerprint)
    else:
        version_id = UUID(detached["version"] or detached["owner"])
        key = await _key_of(tenant_id, version_id)
        binding = _binding(version_id, stored.fingerprint, derived=detached["derived"] is not None)
        content = await open_detached(tenant_id, sealed, binding, key)
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
