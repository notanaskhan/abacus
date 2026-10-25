"""Public interface of the platform module; other modules import only this (ADR-008)."""

from abacus.kernel.controls import ControlName, control_active
from abacus.kernel.dispatch import PlatformSchedule
from abacus.kernel.uow import Handler
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.platform.canary import (
    CANARY_ACTIVITIES,
    CanaryFlag,
    CanaryNotSynthetic,
    CanaryProbe,
    CanaryScreen,
    CanaryStepFailed,
    Heartbeat,
    RecordingHeartbeat,
    canary_probe,
    canary_schedules,
    configure_canary_probe,
    configure_heartbeat,
    expected_route,
    inv2_violations,
    should_page,
)
from abacus.modules.platform.canary import WORKFLOWS as CANARY_WORKFLOWS
from abacus.modules.platform.canary import boundary as canary_boundary
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
    IncidentFacts,
    IncidentFactsChanged,
    IncidentView,
    PropagationStarted,
    clock_day,
    facts_sha256,
    finish_propagation,
    incident_clock,
    propagate_into,
    propagation_log,
    record_incident,
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
    CanaryInput,
    CanaryOutcome,
    CanaryPlan,
    CanaryResult,
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
    CANARY_EVERY,
    G04_PLAN_PATCH,
    SPEND_ANOMALY_ID,
    CanaryWorkflow,
    IncidentPropagationWorkflow,
    SpendAnomalyWorkflow,
    TenantKeyWorkflow,
    TenantProvisioningWorkflow,
    canary_workflow_id,
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
# Q-01-T30: the canary (time_sensitive), on its own Schedule when this environment names one.
WORKFLOWS = {**PROVISIONING_WORKFLOWS, **INCIDENT_WORKFLOWS, **JOB_WORKFLOWS, **CANARY_WORKFLOWS}
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
    *CANARY_ACTIVITIES,  # Q-01-T30: the canary's steps and report
)


def schedules() -> tuple[PlatformSchedule, ...]:
    """The platform's Schedules (`abacus_tools.schedules ensure`): its jobs, and the canary when
    `canary_tenant_id` is set."""
    return (*SCHEDULES, *canary_schedules())


__all__ = [
    "ACTIVITIES",
    "CANARY_ACTIVITIES",
    "CANARY_EVERY",
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
    "CanaryFlag",
    "CanaryInput",
    "CanaryNotSynthetic",
    "CanaryOutcome",
    "CanaryPlan",
    "CanaryProbe",
    "CanaryResult",
    "CanaryScreen",
    "CanaryStepFailed",
    "CanaryWorkflow",
    "ControlName",
    "Entitlement",
    "EntitlementRequired",
    "Heartbeat",
    "InMemoryTenantKeyOps",
    "IncidentFacts",
    "IncidentFactsChanged",
    "IncidentFactsInput",
    "IncidentPropagationInput",
    "IncidentPropagationOutcome",
    "IncidentPropagationResult",
    "IncidentPropagationStep",
    "IncidentPropagationWorkflow",
    "IncidentStepResult",
    "IncidentView",
    "Module",
    "PropagationStarted",
    "ProvisionTenantInput",
    "ProvisionTenantResult",
    "RecordingHeartbeat",
    "SearchDocument",
    "SpendAnomalyWorkflow",
    "TenantKeyInput",
    "TenantKeyWorkflow",
    "TenantProvisioned",
    "TenantProvisioningWorkflow",
    "canary_boundary",
    "canary_probe",
    "canary_workflow_id",
    "check_entitlement",
    "clock_day",
    "configure_canary_probe",
    "configure_heartbeat",
    "configure_tenant_key_ops",
    "control_active",
    "entitlement",
    "expected_route",
    "facts_sha256",
    "finish_propagation",
    "incident_clock",
    "incident_propagation_workflow_id",
    "inv2_violations",
    "operator_context",
    "propagate_into",
    "propagation_log",
    "provisioning_workflow_id",
    "record_incident",
    "register_search_projection",
    "require_entitlement",
    "router",
    "schedules",
    "search_document",
    "should_page",
    "start_propagation",
    "start_provisioning",
    "tenant_key_workflow_id",
]
