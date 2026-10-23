"""Public interface of the platform module; other modules import only this (ADR-008)."""

from abacus.kernel.uow import Handler
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.platform.entitlements import (
    MODULES,
    Entitlement,
    EntitlementRequired,
    Module,
    check_entitlement,
    entitlement,
    require_entitlement,
)
from abacus.modules.platform.events import TenantProvisioned
from abacus.modules.platform.provisioning import (
    OPERATOR_HANDLE,
    WORKFLOWS,
    emit_tenant_provisioned_activity,
    invite_first_admins_activity,
    operator_context,
    request_tenant_key_activity,
    set_plan_entitlements_activity,
    start_provisioning,
)
from abacus.modules.platform.routes import router
from abacus.modules.platform.service import BudgetInvalid
from abacus.modules.platform.slots import (
    SearchDocument,
    register_search_projection,
    search_document,
)
from abacus.modules.platform.tenant_keys import (
    TENANT_KEY_ACTIVITIES,
    InMemoryTenantKeyOps,
    configure_tenant_key_ops,
)
from abacus.modules.platform.workflow_types import (
    ProvisionTenantInput,
    ProvisionTenantResult,
    TenantKeyInput,
)
from abacus.modules.platform.workflows import (
    G04_PLAN_PATCH,
    TenantKeyWorkflow,
    TenantProvisioningWorkflow,
    provisioning_workflow_id,
    tenant_key_workflow_id,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (router,)

# Q-01-T45: the worker loads this module for tenant provisioning (ADR-156).
SUBSCRIPTIONS: dict[str, Handler] = {}
ACTIVITIES: tuple[object, ...] = (
    emit_tenant_provisioned_activity,
    set_plan_entitlements_activity,  # Q-01-T45 (0107)
    invite_first_admins_activity,
    request_tenant_key_activity,  # Q-01-T27
    *TENANT_KEY_ACTIVITIES,  # the keyops queue's (P-65)
)

__all__ = [
    "ACTIVITIES",
    "G04_PLAN_PATCH",
    "MODULES",
    "OPERATOR_HANDLE",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "BudgetInvalid",
    "Entitlement",
    "EntitlementRequired",
    "InMemoryTenantKeyOps",
    "Module",
    "ProvisionTenantInput",
    "ProvisionTenantResult",
    "SearchDocument",
    "TenantKeyInput",
    "TenantKeyWorkflow",
    "TenantProvisioned",
    "TenantProvisioningWorkflow",
    "check_entitlement",
    "configure_tenant_key_ops",
    "entitlement",
    "operator_context",
    "provisioning_workflow_id",
    "register_search_projection",
    "require_entitlement",
    "router",
    "search_document",
    "start_provisioning",
    "tenant_key_workflow_id",
]
