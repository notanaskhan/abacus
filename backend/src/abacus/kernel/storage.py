"""The S3 client factory (ADR-016). PROTECTED. TASK-009 design §3.

The only place that constructs a boto3 client (STORE-001). boto3 is synchronous: callers run its
methods in `asyncio.to_thread`. Locally and in tests the endpoint is the Versity gateway; in AWS it
is S3 (TASK-014).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from abacus.kernel.config import settings

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client


def s3_client(
    *,
    endpoint_url: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    region: str | None = None,
) -> S3Client:
    """A client from settings; arguments override them (tests point at their own gateway)."""
    s = settings()
    key = access_key or (s.s3_access_key.get_secret_value() if s.s3_access_key else None)
    secret = secret_key or (s.s3_secret_key.get_secret_value() if s.s3_secret_key else None)
    # boto3-stubs overloads name every AWS service; only the s3 stub package is installed.
    return boto3.client(  # pyright: ignore[reportUnknownMemberType] -- see comment above
        "s3",
        endpoint_url=endpoint_url or s.s3_endpoint_url,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name=region or s.s3_region,
        config=Config(
            s3={"addressing_style": "path"},
            retries={"mode": "standard", "max_attempts": 3},
            connect_timeout=5,
            read_timeout=30,
            max_pool_connections=20,
        ),
    )


def error_code(exc: BaseException) -> str | None:
    """The S3 error code of a storage exception, or None if it isn't one. Callers outside this
    module classify storage errors through this, never through botocore (STORE-001)."""
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code")
        return str(code) if code is not None else None
    return None


StorageError = ClientError
