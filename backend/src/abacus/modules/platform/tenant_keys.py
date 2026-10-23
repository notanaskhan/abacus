"""Tenant keys (Q-01-T27; P-65, ADR-035, ADR-104, ADR-156). PROTECTED.

Every firm gets its own symmetric multi-Region KMS key, made by `TenantKeyWorkflow` on the
`keyops` queue. Only the keyops worker serves that queue, and its task role is the only one
allowed `kms:CreateKey`. The steps, each idempotent:
1. `create`: a multi-Region key in `kms_region`, tagged `abacus:env` and `abacus:tenant`, with
   the tenant's alias (`kms_alias_prefix` + tenant id). An existing alias is reused.
2. `replicate`: the key replicated to `kms_replica_region`, with the same alias there.
3. `verify`: a fresh data key wrapped in the primary region is unwrapped by the replica, under
   the tenant's encryption context. Only then is the firm `replica_verified`, so its client
   content can be stored (ADR-156).

The firm's key ARN and status are written in the firm's own context (identity owns `firms`).
Deleting a key or changing its policy isn't here: an SCP reserves those to the key custodian.
Local runs and tests use an in-memory key service, never AWS.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Protocol
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.logging import get_logger
from abacus.kernel.storage import AwsError, error_code, kms_client
from abacus.modules.identity.api import firm_tenancy, record_tenant_key
from abacus.modules.platform.workflow_types import TenantKeyInput

_VERIFY_PURPOSE: Final = "replica_check"
_HANDLE: Final = re.compile(r"[a-z][a-z0-9._-]{0,60}")  # as provisioning's OPERATOR_HANDLE
_log = get_logger(__name__)


class TenantKeyOps(Protocol):
    def create(self, tenant_id: UUID) -> str: ...

    def replicate(self, tenant_id: UUID, key_arn: str) -> str: ...

    def verify(self, tenant_id: UUID, key_arn: str, replica_arn: str) -> bool: ...


def _arn(meta: Mapping[str, object]) -> str:
    found = meta.get("Arn")
    if not isinstance(found, str):
        raise ApplicationError("KmsAnsweredBadly", type="KmsAnsweredBadly")
    return found


def _context(tenant_id: UUID) -> dict[str, str]:
    return {"abacus:tenant": str(tenant_id), "abacus:purpose": _VERIFY_PURPOSE}


class KmsTenantKeyOps:
    """AWS KMS, through the kernel's clients (STORE-001). Blocking calls: run them in a thread."""

    def __init__(self) -> None:
        s = settings()
        self._primary = kms_client(region=s.kms_region)
        self._replica = kms_client(region=s.kms_replica_region)
        self._replica_region = s.kms_replica_region
        self._alias_prefix = s.kms_alias_prefix
        self._env = s.environment

    def _alias(self, tenant_id: UUID) -> str:
        return f"{self._alias_prefix}{tenant_id}"

    def _tags(self, tenant_id: UUID) -> list[dict[str, str]]:
        return [
            {"TagKey": "abacus:env", "TagValue": self._env},
            {"TagKey": "abacus:tenant", "TagValue": str(tenant_id)},
        ]

    def create(self, tenant_id: UUID) -> str:
        try:
            return _arn(self._primary.describe_key(KeyId=self._alias(tenant_id))["KeyMetadata"])
        except AwsError as exc:
            if error_code(exc) != "NotFoundException":
                raise
        made = self._primary.create_key(
            Description=f"abacus tenant {tenant_id}",
            KeyUsage="ENCRYPT_DECRYPT",
            KeySpec="SYMMETRIC_DEFAULT",
            MultiRegion=True,
            Tags=self._tags(tenant_id),  # type: ignore[arg-type]  # boto3's TypedDict list
        )["KeyMetadata"]
        self._primary.create_alias(AliasName=self._alias(tenant_id), TargetKeyId=made["KeyId"])
        return _arn(made)

    def replicate(self, tenant_id: UUID, key_arn: str) -> str:
        try:
            return _arn(self._replica.describe_key(KeyId=self._alias(tenant_id))["KeyMetadata"])
        except AwsError as exc:
            if error_code(exc) != "NotFoundException":
                raise
        try:
            replica = self._primary.replicate_key(
                KeyId=key_arn,
                ReplicaRegion=self._replica_region,
                Tags=self._tags(tenant_id),  # type: ignore[arg-type]  # boto3's TypedDict list
            )["ReplicaKeyMetadata"]
            replica_arn = _arn(replica)
            replica_id = replica.get("KeyId") or replica_arn
        except AwsError as exc:
            if error_code(exc) != "AlreadyExistsException":
                raise
            replica_arn = key_arn.replace(
                f":kms:{settings().kms_region}:", f":kms:{self._replica_region}:", 1
            )
            replica_id = replica_arn
        self._replica.create_alias(AliasName=self._alias(tenant_id), TargetKeyId=replica_id)
        return replica_arn

    def verify(self, tenant_id: UUID, key_arn: str, replica_arn: str) -> bool:
        probe = os.urandom(32)
        sealed = self._primary.encrypt(
            KeyId=key_arn, Plaintext=probe, EncryptionContext=_context(tenant_id)
        )["CiphertextBlob"]
        opened = self._replica.decrypt(
            CiphertextBlob=sealed, KeyId=replica_arn, EncryptionContext=_context(tenant_id)
        )["Plaintext"]
        return opened == probe


@dataclass
class InMemoryTenantKeyOps:
    """Local runs and tests: keys that exist only in this process."""

    keys: dict[UUID, str] = field(default_factory=dict[UUID, str])
    replicas: dict[UUID, str] = field(default_factory=dict[UUID, str])
    broken_replica: set[UUID] = field(default_factory=set[UUID])

    def create(self, tenant_id: UUID) -> str:
        return self.keys.setdefault(
            tenant_id, f"arn:aws:kms:us-east-2:000000000000:key/mrk-{tenant_id.hex}"
        )

    def replicate(self, tenant_id: UUID, key_arn: str) -> str:
        return self.replicas.setdefault(tenant_id, key_arn.replace("us-east-2", "us-west-2"))

    def verify(self, tenant_id: UUID, key_arn: str, replica_arn: str) -> bool:
        return tenant_id not in self.broken_replica and self.replicas.get(tenant_id) == replica_arn


_ops: TenantKeyOps | None = None


def configure_tenant_key_ops(ops: TenantKeyOps | None) -> None:
    """Tests: another key service (None goes back to the environment's)."""
    global _ops
    _ops = ops


def tenant_key_ops() -> TenantKeyOps:
    global _ops
    if _ops is None:
        _ops = (
            InMemoryTenantKeyOps()
            if settings().environment in ("local", "test")
            else KmsTenantKeyOps()
        )
    return _ops


def _operator(tenant_id: UUID, operator: str) -> TenantContext:
    """The firm's context as the provisioning operator (INV-5: every step names them)."""
    if not _HANDLE.fullmatch(operator):
        raise ApplicationError("BadOperator", type="BadOperator", non_retryable=True)
    return TenantContext(tenant_id, "system", f"operator:{operator}")


async def _firm(tenant_id: UUID, operator: str) -> TenantContext:
    ctx = _operator(tenant_id, operator)
    if await firm_tenancy(ctx) is None:
        raise ApplicationError("FirmNotFound", type="FirmNotFound", non_retryable=True)
    return ctx


async def create_tenant_key(given: TenantKeyInput) -> str:
    tenant_id = UUID(given.tenant_id)
    ctx = await _firm(tenant_id, given.operator)
    arn = await asyncio.to_thread(tenant_key_ops().create, tenant_id)
    await record_tenant_key(ctx, arn=arn, status="active")
    return arn


async def replicate_tenant_key(given: TenantKeyInput, key_arn: str) -> str:
    return await asyncio.to_thread(tenant_key_ops().replicate, UUID(given.tenant_id), key_arn)


async def verify_tenant_key(given: TenantKeyInput, key_arn: str, replica_arn: str) -> str:
    tenant_id = UUID(given.tenant_id)
    ctx = await _firm(tenant_id, given.operator)
    if not await asyncio.to_thread(tenant_key_ops().verify, tenant_id, key_arn, replica_arn):
        # Retried by the workflow; the firm stays `active`, so it stores no client content yet.
        raise ApplicationError("ReplicaNotVerified", type="ReplicaNotVerified")
    await record_tenant_key(ctx, arn=key_arn, status="replica_verified")
    _log.info("tenant_key.replica_verified", tenant_id=tenant_id)
    return "replica_verified"


@activity.defn(name="keyops.create_tenant_key")
async def create_tenant_key_activity(given: TenantKeyInput) -> str:
    return await create_tenant_key(given)


@activity.defn(name="keyops.replicate_tenant_key")
async def replicate_tenant_key_activity(given: TenantKeyInput, key_arn: str) -> str:
    return await replicate_tenant_key(given, key_arn)


@activity.defn(name="keyops.verify_tenant_key")
async def verify_tenant_key_activity(given: TenantKeyInput, key_arn: str, replica_arn: str) -> str:
    return await verify_tenant_key(given, key_arn, replica_arn)


TENANT_KEY_ACTIVITIES: Final = (
    create_tenant_key_activity,
    replicate_tenant_key_activity,
    verify_tenant_key_activity,
)
