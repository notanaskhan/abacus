"""Create the local evidence bucket with Object Lock (ADR-016). Idempotent.

Run: python -m abacus_tools.local.evidence_bucket
In AWS the bucket is created by Terraform (TASK-014), never by the application.
"""

from __future__ import annotations

import sys

from botocore.exceptions import ClientError

from abacus.kernel.config import settings
from abacus.kernel.storage import s3_client


def ensure_bucket() -> str:
    s = settings()
    if s.environment not in ("local", "test") or s.evidence_bucket is None:
        raise RuntimeError("the local evidence bucket is for local runs and tests only")
    client = s3_client()
    try:
        client.create_bucket(Bucket=s.evidence_bucket, ObjectLockEnabledForBucket=True)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in (
            "BucketAlreadyOwnedByYou",
            "BucketAlreadyExists",
        ):
            raise
    return s.evidence_bucket


def main() -> int:
    print(f"evidence bucket ready: {ensure_bucket()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
