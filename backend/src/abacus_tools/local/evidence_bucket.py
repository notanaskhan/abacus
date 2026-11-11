"""Create the local evidence bucket with Object Lock (ADR-016). Idempotent.

Run: python -m abacus_tools.local.evidence_bucket
In AWS the bucket is created by Terraform (TASK-014), never by the application.
"""

from __future__ import annotations

import sys

from abacus.kernel.config import settings
from abacus.kernel.storage import StorageError, error_code, s3_client


def ensure_bucket() -> str:
    s = settings()
    if s.environment not in ("local", "test") or s.evidence_bucket is None:
        raise RuntimeError("the local evidence bucket is for local runs and tests only")
    return _locked_bucket(s.evidence_bucket)


def ensure_records_bucket() -> str | None:
    """The records bucket, when the local run names one (`make dev`'s LOCAL_ENV): the archive's
    seal manifest is written there in COMPLIANCE mode (S35 follow-up)."""
    s = settings()
    if s.environment not in ("local", "test") or s.records_bucket is None:
        return None
    return _locked_bucket(s.records_bucket)


def _locked_bucket(name: str) -> str:
    client = s3_client()
    try:
        client.create_bucket(Bucket=name, ObjectLockEnabledForBucket=True)
    except StorageError as exc:
        if error_code(exc) != "BucketAlreadyOwnedByYou":
            raise
    # An existing bucket must really be write-once: refuse one without Object Lock.
    try:
        lock = client.get_object_lock_configuration(Bucket=name)
    except StorageError as exc:
        if error_code(exc) == "ObjectLockConfigurationNotFoundError":
            raise RuntimeError(f"bucket {name} exists without Object Lock") from None
        raise
    if lock.get("ObjectLockConfiguration", {}).get("ObjectLockEnabled") != "Enabled":
        raise RuntimeError(f"bucket {name} exists without Object Lock")
    return name


def main() -> int:
    print(f"evidence bucket ready: {ensure_bucket()}")
    records = ensure_records_bucket()
    if records is not None:
        print(f"records bucket ready: {records}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
