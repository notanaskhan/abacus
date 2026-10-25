"""Public interface of the platform module; other modules import only this (ADR-008)."""

from abacus.kernel.controls import ControlName, control_active
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
from abacus.modules.platform.incident_activities import INCIDENT_ACTIVITIES
from abacus.modules.platform.incident_routes import platform_router as incident_platform_router
from abacus.modules.platform.incident_routes import router as incident_router
from abacus.modules.platform.incidents import (
    CLOCK_DAYS,
    DPA_NOTICE,
    NOTIFY_THRESHOLD,
    IncidentFactsChanged,
    PropagationStarted,
    facts_sha256,
    finish_propagation,
    incident_clock,
    propagate_into,
    propagation_log,
    start_propagation,
)
from abacus.modules.platform.incidents import WORKFLOWS as INCIDENT_WORKFLOWS
from abacus.modules.platform.jobs import ACTIVITIES as JOB_ACTIVITIES
from abacus.modules.platform.jobs import SCHEDULES
from abacus.modules.platform.jobs import WORKFLOWS as JOB_WORKFLOWS
from abacus.modules.platform.provisioning import (
    OPERATOR_HANDLE,
    apply_retention_defaults_activity,
    emit_tenant_provisioned_activity,
    invite_first_admins_activity,
    operator_context,
    request_tenant_key_activity,
    set_plan_entitlements_activity,
    start_provisioning,
)
from abacus.modules.platform.provisioning import (
    WORKFLOWS as PROVISIONING_WORKFLOWS,
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
    IncidentFactsInput,
    IncidentPropagationInput,
    IncidentPropagationOutcome,
    IncidentPropagationResult,
    IncidentPropagationStep,
    IncidentStepResult,
    ProvisionTenantInput,
    ProvisionTenantResult,
    TenantKeyInput,
)
from abacus.modules.platform.workflows import (
    G04_PLAN_PATCH,
    SPEND_ANOMALY_ID,
    IncidentPropagationWorkflow,
    SpendAnomalyWorkflow,
    TenantKeyWorkflow,
    TenantProvisioningWorkflow,
    incident_propagation_workflow_id,
    provisioning_workflow_id,
    tenant_key_workflow_id,
)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    incident_router,  # Q-02-T33: the firm's incident register
    incident_platform_router,  # Q-02-T33 (RB-27): staff propagation
)

# Q-01-T45: the worker loads this module for tenant provisioning (ADR-156); Q-02-T33 adds the
# incident propagation (time_sensitive); Q-01-T26 the hourly spend-anomaly job (background), on
# its Schedule (`SCHEDULES`, ensured by `abacus_tools.schedules`).
WORKFLOWS = {**PROVISIONING_WORKFLOWS, **INCIDENT_WORKFLOWS, **JOB_WORKFLOWS}
SUBSCRIPTIONS: dict[str, Handler] = {}
ACTIVITIES: tuple[object, ...] = (
    emit_tenant_provisioned_activity,
    set_plan_entitlements_activity,  # Q-01-T45 (0107)
    invite_first_admins_activity,
    request_tenant_key_activity,  # Q-01-T27
    apply_retention_defaults_activity,  # Q-02-T23 (0112)
    *TENANT_KEY_ACTIVITIES,  # the keyops queue's (P-65)
    *INCIDENT_ACTIVITIES,  # Q-02-T33: IncidentPropagation
    *JOB_ACTIVITIES,  # Q-01-T26: SpendAnomaly
)

__all__ = [
    "ACTIVITIES",
    "CLOCK_DAYS",
    "DPA_NOTICE",
    "G04_PLAN_PATCH",
    "MODULES",
    "NOTIFY_THRESHOLD",
    "OPERATOR_HANDLE",
    "ROUTERS",
    "SCHEDULES",
    "SPEND_ANOMALY_ID",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "BudgetInvalid",
    "ControlName",
    "Entitlement",
    "EntitlementRequired",
    "InMemoryTenantKeyOps",
    "IncidentFactsChanged",
    "IncidentFactsInput",
    "IncidentPropagationInput",
    "IncidentPropagationOutcome",
    "IncidentPropagationResult",
    "IncidentPropagationStep",
    "IncidentPropagationWorkflow",
    "IncidentStepResult",
    "Module",
    "PropagationStarted",
    "ProvisionTenantInput",
    "ProvisionTenantResult",
    "SearchDocument",
    "SpendAnomalyWorkflow",
    "TenantKeyInput",
    "TenantKeyWorkflow",
    "TenantProvisioned",
    "TenantProvisioningWorkflow",
    "check_entitlement",
    "configure_tenant_key_ops",
    "control_active",
    "entitlement",
    "facts_sha256",
    "finish_propagation",
    "incident_clock",
    "incident_propagation_workflow_id",
    "operator_context",
    "propagate_into",
    "propagation_log",
    "provisioning_workflow_id",
    "register_search_projection",
    "require_entitlement",
    "router",
    "search_document",
    "start_propagation",
    "start_provisioning",
    "tenant_key_workflow_id",
]
