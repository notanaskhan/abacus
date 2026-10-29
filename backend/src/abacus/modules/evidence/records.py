"""Records kept in COMPLIANCE mode (Q-02-T24; C-09, ADR-016). PROTECTED.

Some records must outlive any administrator's say-so: audit chain anchors, seal manifests, and
consent and signature evidence. They go to the records bucket under Object Lock COMPLIANCE mode,
which no role can shorten or delete before the retain-until date, unlike the evidence bucket's
GOVERNANCE mode. Each is a plain JSON or byte body under `records/<tenant>/<class>/<sha256>`,
written once (`If-None-Match: *`; the same content again returns the stored version).

`anchor_chain` publishes the firm's newest audit checkpoint hash as an anchor
(`kernel.uow.chain.verify_anchor` checks one later).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import TYPE_CHECKING, Final, Literal
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.storage import StorageError, error_code, s3_client
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.chain import latest_checkpoint

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

RecordClass = Literal["chain_anchor", "seal_manifest", "consent_evidence", "signature_evidence"]
RECORD_CLASSES: Final = frozenset(
    {"chain_anchor", "seal_manifest", "consent_evidence", "signature_evidence"}
)
_RACE: Final = ("PreconditionFailed", "ConditionalRequestConflict")


class RecordsUnavailable(ServiceUnavailable):
    """No records bucket is configured: nothing is written anywhere else instead."""


@dataclass(frozen=True)
class StoredRecord:
    key: str
    version_id: str
    sha256: str
    retain_until: datetime


@dataclass(frozen=True)
class _Records:
    client: S3Client
    bucket: str


_records: _Records | None = None


def configure_records(client: S3Client, bucket: str) -> None:
    """Tests and local runs: point the records writer at a client and bucket."""
    global _records
    _records = _Records(client, bucket)


def reset_records() -> None:
    global _records
    _records = None
    _from_settings.cache_clear()


@lru_cache(maxsize=1)
def _from_settings() -> _Records:
    bucket = settings().records_bucket
    if bucket is None:
        raise RecordsUnavailable
    return _Records(s3_client(), bucket)


def _target() -> _Records:
    return _records if _records is not None else _from_settings()


def record_key(tenant_id: UUID, record_class: RecordClass, digest: str) -> str:
    return f"records/{tenant_id}/{record_class}/{digest}"


async def put_record(
    tenant_id: UUID, record_class: RecordClass, body: bytes, retain_until: datetime
) -> StoredRecord:
    """Write a record in COMPLIANCE mode until `retain_until`; the same body again returns the
    version already there."""
    if record_class not in RECORD_CLASSES:
        raise ValueError(f"unknown record class {record_class!r}")
    target = _target()
    digest = hashlib.sha256(body).hexdigest()
    key = record_key(tenant_id, record_class, digest)
    try:
        written = await asyncio.to_thread(
            target.client.put_object,
            Bucket=target.bucket,
            Key=key,
            Body=body,
            ContentType="application/octet-stream",
            IfNoneMatch="*",
            ObjectLockMode="COMPLIANCE",
            ObjectLockRetainUntilDate=retain_until,
        )
        version = written.get("VersionId")
    except StorageError as exc:
        if error_code(exc) not in _RACE:
            raise
        head = await asyncio.to_thread(target.client.head_object, Bucket=target.bucket, Key=key)
        version = head.get("VersionId")
    if not version or version == "null":
        raise RecordsUnavailable  # the records bucket must have versioning and Object Lock
    return StoredRecord(key, version, digest, retain_until)


async def get_record(tenant_id: UUID, record_class: RecordClass, digest: str) -> bytes | None:
    """A stored record's body, verified against the digest its key names; None when absent
    (N-02-T13: the evidence package reads back what the import or the provider wrote). The
    caller authorised its own action and holds the row that names the digest."""
    if record_class not in RECORD_CLASSES:
        raise ValueError(f"unknown record class {record_class!r}")
    target = _target()
    try:
        got = await asyncio.to_thread(
            target.client.get_object,
            Bucket=target.bucket,
            Key=record_key(tenant_id, record_class, digest),
        )
    except StorageError as exc:
        if error_code(exc) in ("NoSuchKey", "404"):
            return None
        raise
    body = got["Body"].read()
    if hashlib.sha256(body).hexdigest() != digest:
        raise RecordsUnavailable  # a stored record never differs from its digest
    return body


async def anchor_chain(tenant_id: UUID, retain_until: datetime) -> StoredRecord | None:
    """Publish the firm's newest checkpoint as an anchor (C-09); None before its first one. One
    `audit_chain.anchored` event names the checkpoint and the stored version."""
    checkpoint = await latest_checkpoint(tenant_id)
    if checkpoint is None:
        return None
    body = json.dumps(
        {
            "tenant_id": str(tenant_id),
            "checkpoint_no": checkpoint.checkpoint_no,
            "chain_hash": checkpoint.chain_hash.hex(),
            "anchored_at": system_now().isoformat(),
        },
        sort_keys=True,
    ).encode()
    stored = await put_record(tenant_id, "chain_anchor", body, retain_until)
    async with uow(TenantContext(tenant_id, "system", "audit_chain:anchor")) as tx:
        tx.record(
            "audit_chain.anchored",
            target=Target("firm", tenant_id),
            after=Ref(checkpoint=checkpoint.checkpoint_no, record=stored.sha256),
        )
    return stored
