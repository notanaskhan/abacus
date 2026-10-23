"""The AWS SDK's door: the S3 client factory (ADR-016) and the KMS and SES ones (ADR-104, P-55).
PROTECTED. TASK-009 design §3; Q-01-T08, Q-01-T09.

The only place that constructs a boto3 client or names a botocore error (STORE-001). boto3 is
synchronous: callers run its methods in `asyncio.to_thread`. Locally and in tests the S3 endpoint
is the Versity gateway; in AWS it is S3. KMS and SES clients use the default credential chain (the
task role in AWS) and exist only where the settings select their adapters; there is no local KMS
or SES.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from abacus.kernel.config import settings

if TYPE_CHECKING:
    from types_boto3_kms import KMSClient
    from types_boto3_s3 import S3Client
    from types_boto3_sesv2 import SESV2Client
    from types_boto3_sqs import SQSClient


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


def _service_config() -> Config:
    # Short timeouts: a caller is a person's request or a probe, and an error fails closed.
    return Config(
        retries={"mode": "standard", "max_attempts": 3}, connect_timeout=3, read_timeout=10
    )


def kms_client(*, region: str | None = None) -> KMSClient:
    """A KMS client for `region` (the settings' `kms_region`), on the default credential chain."""
    return boto3.client(  # pyright: ignore[reportUnknownMemberType] -- see s3_client
        "kms", region_name=region or settings().kms_region, config=_service_config()
    )


def sesv2_client(*, region: str | None = None) -> SESV2Client:
    """An SES v2 client for `region` (the settings' `ses_region`), on the default credentials."""
    return boto3.client(  # pyright: ignore[reportUnknownMemberType] -- see s3_client
        "sesv2", region_name=region or settings().ses_region, config=_service_config()
    )


def sqs_client(*, region: str | None = None) -> SQSClient:
    """An SQS client for `region` (the settings' `ses_region`): SES delivery events (Q-01-T46)."""
    return boto3.client(  # pyright: ignore[reportUnknownMemberType] -- see s3_client
        "sqs", region_name=region or settings().ses_region, config=_service_config()
    )


def error_code(exc: BaseException) -> str | None:
    """The S3 error code of a storage exception, or None if it isn't one. Callers outside this
    module classify storage errors through this, never through botocore (STORE-001)."""
    if isinstance(exc, ClientError):
        code = exc.response.get("Error", {}).get("Code")
        return str(code) if code is not None else None
    return None


StorageError = ClientError
# Anything the SDK can raise: an error response, or no credentials, no route, a timeout.
AwsError = (ClientError, BotoCoreError)
