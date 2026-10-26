"""Engagement export bundles in the exports store (A-01-T19; A-01 §4.1; SPEC-344 §11; DEC-433).
PROTECTED.

A bundle is a transient copy (7 days, P-14: not a record), so it lives in its own bucket without
Object Lock, whose lifecycle rule (Q-01) removes it. It is cut into 64 MiB segments under
`exports/<tenant>/<export_id>/segment-NNNN`; each segment is sealed with a fresh data key under
the tenant's key (`kernel.crypto.seal`, the evidence envelope; no new format) and bound to its
export and position, so a segment never opens as another export's or in another place. The API
streams the decrypted ZIP from these segments (A-01-T22; ADR-104: no presigned link).

Writing the same export again overwrites its segments (a retried build is the same bytes).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import IO, TYPE_CHECKING, Final
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.storage import s3_client

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

SEGMENT_BYTES: Final = 64 * 1024 * 1024


class ExportsUnavailable(ServiceUnavailable):
    """No exports bucket is configured: nothing is written anywhere else instead."""


@dataclass(frozen=True)
class _Exports:
    client: S3Client
    bucket: str


_exports: _Exports | None = None


def configure_exports(client: S3Client, bucket: str) -> None:
    """Tests and local runs: point the exports store at a client and bucket."""
    global _exports
    _exports = _Exports(client, bucket)


def reset_exports() -> None:
    global _exports
    _exports = None
    _from_settings.cache_clear()


@lru_cache(maxsize=1)
def _from_settings() -> _Exports:
    bucket = settings().exports_bucket
    if bucket is None:
        raise ExportsUnavailable
    return _Exports(s3_client(), bucket)


def _target() -> _Exports:
    return _exports if _exports is not None else _from_settings()


def export_prefix(tenant_id: UUID, export_id: UUID) -> str:
    return f"exports/{tenant_id}/{export_id}/"


def segment_key(tenant_id: UUID, export_id: UUID, n: int) -> str:
    return f"{export_prefix(tenant_id, export_id)}segment-{n:04d}"


def _binding(export_id: UUID, n: int) -> str:
    return f"engagement_export:{export_id}:{n}"


async def put_segments(
    tenant_id: UUID, export_id: UUID, bundle: IO[bytes], *, segment_bytes: int = SEGMENT_BYTES
) -> int:
    """Seal and store `bundle` (read from its current position) in segments; their count. A
    retry that cuts fewer segments removes the earlier attempt's higher ones."""
    target = _target()
    n = 0
    while True:
        chunk = bundle.read(segment_bytes)
        if not chunk and n > 0:
            await _drop_from(target, tenant_id, export_id, n)
            return n
        sealed = await seal(tenant_id, chunk, _binding(export_id, n))
        await asyncio.to_thread(
            target.client.put_object,
            Bucket=target.bucket,
            Key=segment_key(tenant_id, export_id, n),
            Body=sealed,
            ContentType="application/octet-stream",
        )
        n += 1
        if len(chunk) < segment_bytes:
            await _drop_from(target, tenant_id, export_id, n)
            return n


async def _drop_from(target: _Exports, tenant_id: UUID, export_id: UUID, n: int) -> None:
    """Delete this export's segments numbered `n` and above (a previous attempt's tail)."""
    prefix = export_prefix(tenant_id, export_id)
    keep = {segment_key(tenant_id, export_id, k) for k in range(n)}
    token = ""
    while True:
        if token:
            listed = await asyncio.to_thread(
                target.client.list_objects_v2,
                Bucket=target.bucket,
                Prefix=prefix,
                ContinuationToken=token,
            )
        else:
            listed = await asyncio.to_thread(
                target.client.list_objects_v2, Bucket=target.bucket, Prefix=prefix
            )
        keys = [o.get("Key", "") for o in listed.get("Contents", [])]
        for key in keys:
            if key and key not in keep:
                await asyncio.to_thread(target.client.delete_object, Bucket=target.bucket, Key=key)
        token = listed.get("NextContinuationToken", "")
        if not listed.get("IsTruncated") or not token:
            return


async def get_segment(tenant_id: UUID, export_id: UUID, n: int) -> bytes:
    """One segment, opened: for the download (A-01-T22) and the tests."""
    target = _target()
    response = await asyncio.to_thread(
        target.client.get_object, Bucket=target.bucket, Key=segment_key(tenant_id, export_id, n)
    )
    sealed = await asyncio.to_thread(response["Body"].read)
    return await open_sealed(tenant_id, sealed, _binding(export_id, n))


__all__ = [
    "SEGMENT_BYTES",
    "ExportsUnavailable",
    "configure_exports",
    "export_prefix",
    "get_segment",
    "put_segments",
    "reset_exports",
    "segment_key",
]
