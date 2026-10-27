"""Engagement export bundles in the exports store (A-01-T19; A-01 §4.1; SPEC-344 §11; DEC-433).
PROTECTED.

A bundle is a transient copy (7 days, P-14: not a record), so it lives in its own bucket without
Object Lock, whose lifecycle rule (Q-01) removes it. It is cut into 64 MiB segments under
`exports/<tenant>/<export_id>/segment-NNNN`; each segment is sealed with a fresh data key under
the tenant's key (`kernel.crypto.seal`, the evidence envelope; no new format) and bound to its
export and position, so a segment never opens as another export's or in another place. The API
streams the decrypted ZIP from these segments (A-01-T22; ADR-104: no presigned link).

A firm export's archive (Q-02-T43, `kind="firm_export"`) is stored the same way under
`exports/<tenant>/firm-<export_id>/`, bound as `firm_export:<export_id>:<n>`, so neither kind's
segment opens as the other's.

Writing the same export again overwrites its segments (a retried build is the same bytes).
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import IO, TYPE_CHECKING, Final, Literal, TypedDict
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.storage import s3_client

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

SEGMENT_BYTES: Final = 64 * 1024 * 1024
_SEGMENT: Final = re.compile(r"segment-[0-9]{4,}")
# Which export the segments belong to: an engagement's binder (A-01) or the firm's (Q-02-T43).
StoredKind = Literal["engagement_export", "firm_export"]
ENGAGEMENT: Final = "engagement_export"


class ExportsUnavailable(ServiceUnavailable):
    """No exports bucket is configured: nothing is written anywhere else instead."""


class _Owned(TypedDict, total=False):
    ExpectedBucketOwner: str


@dataclass(frozen=True)
class _Exports:
    client: S3Client
    bucket: str
    owner: str | None = None  # `exports_bucket_owner`: sent as ExpectedBucketOwner (DEC-454)

    def owned(self) -> _Owned:
        return {} if self.owner is None else {"ExpectedBucketOwner": self.owner}


_exports: _Exports | None = None


def configure_exports(client: S3Client, bucket: str, owner: str | None = None) -> None:
    """Tests and local runs: point the exports store at a client and bucket."""
    global _exports
    _exports = _Exports(client, bucket, owner)


def reset_exports() -> None:
    global _exports
    _exports = None
    _from_settings.cache_clear()


@lru_cache(maxsize=1)
def _from_settings() -> _Exports:
    bucket = settings().exports_bucket
    if bucket is None:
        raise ExportsUnavailable
    return _Exports(s3_client(), bucket, settings().exports_bucket_owner)


def _target() -> _Exports:
    return _exports if _exports is not None else _from_settings()


def export_prefix(tenant_id: UUID, export_id: UUID, *, kind: StoredKind = ENGAGEMENT) -> str:
    if kind == "firm_export":
        return f"exports/{tenant_id}/firm-{export_id}/"
    return f"exports/{tenant_id}/{export_id}/"


def segment_key(tenant_id: UUID, export_id: UUID, n: int, *, kind: StoredKind = ENGAGEMENT) -> str:
    return f"{export_prefix(tenant_id, export_id, kind=kind)}segment-{n:04d}"


def _binding(export_id: UUID, n: int, kind: StoredKind) -> str:
    return f"{kind}:{export_id}:{n}"


async def put_segments(
    tenant_id: UUID,
    export_id: UUID,
    bundle: IO[bytes],
    *,
    segment_bytes: int = SEGMENT_BYTES,
    kind: StoredKind = ENGAGEMENT,
    progress: Callable[[int], None] | None = None,
) -> int:
    """Seal and store `bundle` (read from its current position) in segments; their count. A
    retry that cuts fewer segments removes the earlier attempt's higher ones."""
    target = _target()
    n = 0
    while True:
        chunk = bundle.read(segment_bytes)
        if not chunk and n > 0:
            await _drop_from(target, tenant_id, export_id, n, kind)
            return n
        sealed = await seal(tenant_id, chunk, _binding(export_id, n, kind))
        await asyncio.to_thread(
            target.client.put_object,
            Bucket=target.bucket,
            Key=segment_key(tenant_id, export_id, n, kind=kind),
            Body=sealed,
            ContentType="application/octet-stream",
            **target.owned(),
        )
        n += 1
        if progress is not None:  # a long store reports each segment (the firm export's heartbeat)
            progress(n)
        if len(chunk) < segment_bytes:
            await _drop_from(target, tenant_id, export_id, n, kind)
            return n


async def _drop_from(
    target: _Exports, tenant_id: UUID, export_id: UUID, n: int, kind: StoredKind
) -> None:
    """Delete this export's segments numbered `n` and above (a previous attempt's tail)."""
    prefix = export_prefix(tenant_id, export_id, kind=kind)
    keep = {segment_key(tenant_id, export_id, k, kind=kind) for k in range(n)}
    token = ""
    while True:
        if token:
            listed = await asyncio.to_thread(
                target.client.list_objects_v2,
                Bucket=target.bucket,
                Prefix=prefix,
                ContinuationToken=token,
                **target.owned(),
            )
        else:
            listed = await asyncio.to_thread(
                target.client.list_objects_v2,
                Bucket=target.bucket,
                Prefix=prefix,
                **target.owned(),
            )
        keys = [o.get("Key", "") for o in listed.get("Contents", [])]
        for key in keys:
            if key and key not in keep:
                await asyncio.to_thread(
                    target.client.delete_object, Bucket=target.bucket, Key=key, **target.owned()
                )
        token = listed.get("NextContinuationToken", "")
        if not listed.get("IsTruncated") or not token:
            return


async def delete_segments(
    tenant_id: UUID, export_id: UUID, *, kind: StoredKind = ENGAGEMENT
) -> int:
    """A-01-T22: remove one expired or voided export's segments; how many were deleted. Only keys
    under that export's own prefix in its tenant, and only segment keys: nothing else in the
    bucket is touched. Idempotent (a second call deletes nothing)."""
    target = _target()
    prefix = export_prefix(tenant_id, export_id, kind=kind)
    deleted = 0
    token = ""
    while True:
        if token:
            listed = await asyncio.to_thread(
                target.client.list_objects_v2,
                Bucket=target.bucket,
                Prefix=prefix,
                ContinuationToken=token,
                **target.owned(),
            )
        else:
            listed = await asyncio.to_thread(
                target.client.list_objects_v2,
                Bucket=target.bucket,
                Prefix=prefix,
                **target.owned(),
            )
        for entry in listed.get("Contents", []):
            key = entry.get("Key", "")
            if not key.startswith(prefix) or not _SEGMENT.fullmatch(key[len(prefix) :]):
                continue
            await asyncio.to_thread(
                target.client.delete_object, Bucket=target.bucket, Key=key, **target.owned()
            )
            deleted += 1
        token = listed.get("NextContinuationToken", "")
        if not listed.get("IsTruncated") or not token:
            return deleted


async def get_segment(
    tenant_id: UUID, export_id: UUID, n: int, *, kind: StoredKind = ENGAGEMENT
) -> bytes:
    """One segment, opened: for the downloads (A-01-T22, Q-02-T43) and the tests."""
    target = _target()
    response = await asyncio.to_thread(
        target.client.get_object,
        Bucket=target.bucket,
        Key=segment_key(tenant_id, export_id, n, kind=kind),
        **target.owned(),
    )
    sealed = await asyncio.to_thread(response["Body"].read)
    return await open_sealed(tenant_id, sealed, _binding(export_id, n, kind))


__all__ = [
    "SEGMENT_BYTES",
    "ExportsUnavailable",
    "StoredKind",
    "configure_exports",
    "delete_segments",
    "export_prefix",
    "get_segment",
    "put_segments",
    "reset_exports",
    "segment_key",
]
