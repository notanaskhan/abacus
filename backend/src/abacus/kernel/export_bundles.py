"""Sealed export bundles in the exports store (G-02-T17, G-02-T20; ADR-104, DEC-433, DEC-621).

A-01-T19's pattern for every module that hands a person a transient ZIP (the audit-log export,
the WISP pack), so none of them depends on evidence (ADR-008): a bundle is a transient copy (7
days, P-14), kept in the exports bucket without Object Lock, whose lifecycle rule removes it. It
is cut into 64 MiB segments under `exports/<kind>/<tenant>/<bundle_id>/segment-NNNN`, each sealed
with a fresh data key under the tenant's key (`kernel.crypto.seal`) and bound to its kind, bundle
and position, so a segment never opens as another bundle's or in another place. The API streams
the opened ZIP (no presigned link: a presigned object would be ciphertext, ADR-104). No exports
bucket configured fails closed.
"""

from __future__ import annotations

import asyncio
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


class ExportsUnavailable(ServiceUnavailable):
    """No exports bucket is configured: nothing is written anywhere else instead."""


class _Owned(TypedDict, total=False):
    ExpectedBucketOwner: str


@dataclass(frozen=True)
class _Exports:
    client: S3Client
    bucket: str
    owner: str | None = None

    def owned(self) -> _Owned:
        return {} if self.owner is None else {"ExpectedBucketOwner": self.owner}


_exports: list[_Exports | None] = [None]


# Each kind writes under the bucket's one task-role prefix, `exports/` (infra s3-exports), beside
# the engagement exports' `exports/<tenant>/...` (a kind is never a UUID, so they never meet).
BundleKind = Literal["audit-log", "wisp-pack"]


def configure_export_bundles(client: S3Client, bucket: str, owner: str | None = None) -> None:
    """Tests and local runs: point the store at a client and bucket."""
    _exports[0] = _Exports(client, bucket, owner)


def reset_export_bundles() -> None:
    _exports[0] = None
    _from_settings.cache_clear()


@lru_cache(maxsize=1)
def _from_settings() -> _Exports:
    bucket = settings().exports_bucket
    if bucket is None:
        raise ExportsUnavailable
    return _Exports(s3_client(), bucket, settings().exports_bucket_owner)


def _target() -> _Exports:
    found = _exports[0]
    return found if found is not None else _from_settings()


def configured() -> bool:
    """Whether an exports bucket is set (a request is refused up front when not)."""
    return _exports[0] is not None or settings().exports_bucket is not None


def bundle_prefix(kind: BundleKind, tenant_id: UUID, bundle_id: UUID) -> str:
    return f"exports/{kind}/{tenant_id}/{bundle_id}/"


def segment_key(kind: BundleKind, tenant_id: UUID, bundle_id: UUID, n: int) -> str:
    return f"{bundle_prefix(kind, tenant_id, bundle_id)}segment-{n:04d}"


def _binding(kind: BundleKind, bundle_id: UUID, n: int) -> str:
    return f"{kind}:{bundle_id}:{n}"


async def put_bundle(
    kind: BundleKind,
    tenant_id: UUID,
    bundle_id: UUID,
    bundle: IO[bytes],
    *,
    segment_bytes: int = SEGMENT_BYTES,
) -> int:
    """Seal and store `bundle` (from its current position) in segments; their count. A retried
    build writes the same keys again."""
    target = _target()
    n = 0
    while True:
        chunk = bundle.read(segment_bytes)
        if not chunk and n > 0:
            return n
        sealed = await seal(tenant_id, chunk, _binding(kind, bundle_id, n))
        await asyncio.to_thread(
            target.client.put_object,
            Bucket=target.bucket,
            Key=segment_key(kind, tenant_id, bundle_id, n),
            Body=sealed,
            ContentType="application/octet-stream",
            **target.owned(),
        )
        n += 1
        if len(chunk) < segment_bytes:
            return n


async def get_segment(kind: BundleKind, tenant_id: UUID, bundle_id: UUID, n: int) -> bytes:
    """One segment, opened under the bundle's own tenant."""
    target = _target()
    response = await asyncio.to_thread(
        target.client.get_object,
        Bucket=target.bucket,
        Key=segment_key(kind, tenant_id, bundle_id, n),
        **target.owned(),
    )
    sealed = await asyncio.to_thread(response["Body"].read)
    return await open_sealed(tenant_id, sealed, _binding(kind, bundle_id, n))


__all__ = [
    "SEGMENT_BYTES",
    "BundleKind",
    "ExportsUnavailable",
    "bundle_prefix",
    "configure_export_bundles",
    "configured",
    "get_segment",
    "put_bundle",
    "reset_export_bundles",
    "segment_key",
]
