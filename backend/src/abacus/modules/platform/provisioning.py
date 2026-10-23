"""Tenant provisioning: the workflow's start and its activities (Q-01-T45; ADR-156, P-65).
PROTECTED.

`provision_firm(...)` (migration 0086; EXECUTE to `abacus_ops` only) creates the firm and records
the idempotency key; `abacus_tools.tenants provision` calls it and then `start_provisioning`. The
workflow's steps run in the new firm's context as the operator (`system`, `operator:<handle>`,
INV-5), so every audit row names who provisioned it. The workflow input is never proof that the
firm exists: each activity reads the firm under its row-level security first.
"""

from __future__ import annotations

import re
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError, WorkflowAlreadyStartedError

from abacus.kernel.db import TenantContext
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import firm_tenancy, invite_first_admins
from abacus.modules.platform.events import TenantProvisioned
from abacus.modules.platform.workflow_types import ProvisionTenantInput, TenantKeyInput
from abacus.modules.platform.workflows import (
    TenantKeyWorkflow,
    TenantProvisioningWorkflow,
    provisioning_workflow_id,
    tenant_key_workflow_id,
)

# An operator handle (`--operator`): a short name, never an email address (contract 3.5).
OPERATOR_HANDLE: Final = re.compile(r"[a-z][a-z0-9._-]{0,60}")
_log = get_logger(__name__)
WORKFLOWS: dict[type, WorkClass] = {
    TenantProvisioningWorkflow: "background",
    TenantKeyWorkflow: "keyops",  # Q-01-T27 (P-65): only the keyops worker serves it
}
register_work_classes(WORKFLOWS)


def operator_context(tenant_id: UUID, operator: str) -> TenantContext:
    """The firm's context as the named operator (INV-5): audit rows carry `operator:<handle>`."""
    if not OPERATOR_HANDLE.fullmatch(operator):
        raise ValueError("an operator handle is a lower-case name (as `make flag`)")
    return TenantContext(tenant_id, "system", f"operator:{operator}")


async def start_provisioning(given: ProvisionTenantInput) -> bool:
    """Start `TenantProvisioningWorkflow` for a firm `provision_firm` created. False when a run
    for the firm is open or has completed (the same idempotency key starts no second workflow);
    a failed run may be started again."""
    operator_context(UUID(given.tenant_id), given.operator)  # refuses a bad handle up front
    try:
        await dispatch(
            TenantProvisioningWorkflow,
            given,
            id=provisioning_workflow_id(given.tenant_id),
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        )
    except WorkflowAlreadyStartedError:
        return False
    return True


async def emit_tenant_provisioned(given: ProvisionTenantInput) -> str:
    """Record `tenant.provisioned` in the firm's audit trail and outbox, as the operator. Returns
    the firm's key status (ADR-156: `none` until TenantKeyWorkflow lands with Q-01-T27)."""
    tenant_id = UUID(given.tenant_id)
    ctx = operator_context(tenant_id, given.operator)
    facts = await firm_tenancy(ctx)
    if facts is None:
        raise ApplicationError("FirmNotFound", type="FirmNotFound", non_retryable=True)
    async with uow(ctx) as tx:
        tx.record("tenant.provisioned", target=Target("firm", tenant_id))
        tx.emit(
            TenantProvisioned(
                tenant_id=tenant_id,
                plan=given.plan,
                synthetic=facts.synthetic,
                operator=given.operator,
            )
        )
    _log.info("tenant.provisioned", tenant_id=tenant_id, key_status=facts.kms_key_status)
    return facts.kms_key_status


@activity.defn(name="platform.emit_tenant_provisioned")
async def emit_tenant_provisioned_activity(given: ProvisionTenantInput) -> str:
    return await emit_tenant_provisioned(given)


async def set_plan_entitlements(given: ProvisionTenantInput) -> int:
    """The firm's entitlements from its plan (`apply_plan_entitlements`, migration 0107), as the
    operator. Only for a newly provisioned firm with none yet: a retry writes nothing more."""
    tenant_id = UUID(given.tenant_id)
    ctx = operator_context(tenant_id, given.operator)
    if await firm_tenancy(ctx) is None:
        raise ApplicationError("FirmNotFound", type="FirmNotFound", non_retryable=True)
    async with uow(ctx) as tx:
        rows = cast(
            int,
            (
                await tx.session.execute(
                    text("SELECT apply_plan_entitlements(:tenant, :plan, :operator)"),
                    {"tenant": tenant_id, "plan": given.plan, "operator": ctx.actor_id},
                )
            ).scalar_one(),
        )
        tx.record(
            "tenant.entitlements_changed", target=Target("firm", tenant_id), after=Ref(rows=rows)
        )
    return rows


@activity.defn(name="platform.set_plan_entitlements")
async def set_plan_entitlements_activity(given: ProvisionTenantInput) -> int:
    return await set_plan_entitlements(given)


async def invite_admins(given: ProvisionTenantInput) -> int:
    """The firm's first administrators, invited as the operator (identity, migration 0107)."""
    tenant_id = UUID(given.tenant_id)
    ctx = operator_context(tenant_id, given.operator)
    if await firm_tenancy(ctx) is None:
        raise ApplicationError("FirmNotFound", type="FirmNotFound", non_retryable=True)
    return len(await invite_first_admins(ctx, given.admins))


@activity.defn(name="platform.invite_first_admins")
async def invite_first_admins_activity(given: ProvisionTenantInput) -> int:
    return await invite_admins(given)


async def apply_retention_defaults(given: ProvisionTenantInput) -> int:
    """The firm's default retention policies (`retention_apply_defaults`, migration 0112), as the
    operator; rows a retry or an earlier back-fill already wrote are kept."""
    tenant_id = UUID(given.tenant_id)
    ctx = operator_context(tenant_id, given.operator)
    if await firm_tenancy(ctx) is None:
        raise ApplicationError("FirmNotFound", type="FirmNotFound", non_retryable=True)
    async with uow(ctx) as tx:
        rows = int(
            (await tx.session.execute(text("SELECT retention_apply_defaults()"))).scalar_one()
        )
        # Every run is recorded, a retry's `rows=0` too: the unit of work always writes its event.
        tx.record(
            "retention_policy.defaults_applied",
            target=Target("firm", tenant_id),
            after=Ref(rows=rows),
        )
    return rows


@activity.defn(name="platform.apply_retention_defaults")
async def apply_retention_defaults_activity(given: ProvisionTenantInput) -> int:
    return await apply_retention_defaults(given)


async def request_tenant_key(given: ProvisionTenantInput) -> bool:
    """Start the firm's `TenantKeyWorkflow` on the keyops queue (Q-01-T27); False when a run
    for it already exists (a retried activity, or a provision run again)."""
    tenant_id = UUID(given.tenant_id)
    if await firm_tenancy(operator_context(tenant_id, given.operator)) is None:
        raise ApplicationError("FirmNotFound", type="FirmNotFound", non_retryable=True)
    try:
        await dispatch(
            TenantKeyWorkflow,
            TenantKeyInput(given.tenant_id, given.operator),
            id=tenant_key_workflow_id(given.tenant_id),
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.FAIL,
        )
    except WorkflowAlreadyStartedError:
        return False
    return True


@activity.defn(name="platform.request_tenant_key")
async def request_tenant_key_activity(given: ProvisionTenantInput) -> bool:
    return await request_tenant_key(given)
