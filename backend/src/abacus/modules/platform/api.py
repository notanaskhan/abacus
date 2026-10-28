"""Public interface of the platform module; other modules import only this (ADR-008)."""

from abacus.kernel.controls import ControlName, control_active
from abacus.kernel.dispatch import PlatformSchedule
from abacus.kernel.uow import Handler
from abacus.modules.identity.api import AbacusRouter, register_posture_source
from abacus.modules.platform.audit_resolvers import register as register_audit_resolvers
from abacus.modules.platform.audit_slots import (
    AuditEventRef,
    AuditLabel,
    AuditLabeler,
    AuditNotIncluded,
    AuditSource,
    AuditSourceResolver,
    AuditValueResolver,
    AuditValueRow,
    AuditValues,
    audit_labels,
    audit_source,
    audit_values,
    mask_value,
    register_audit_labeler,
    register_audit_source,
    register_audit_value_resolver,
    registered_audit_types,
)
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
from abacus.modules.platform.governance_errors import DeciderMustDiffer
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
    open_incidents,
    propagate_into,
    propagation_log,
    record_incident,
    start_propagation,
)
from abacus.modules.platform.incidents import WORKFLOWS as INCIDENT_WORKFLOWS
from abacus.modules.platform.jobs import ACTIVITIES as JOB_ACTIVITIES
from abacus.modules.platform.jobs import SCHEDULES
from abacus.modules.platform.jobs import WORKFLOWS as JOB_WORKFLOWS
from abacus.modules.platform.pilots import Mode as PilotMode
from abacus.modules.platform.pilots import PilotModeRefused
from abacus.modules.platform.pilots import enrol as enrol_pilot
from abacus.modules.platform.pilots import set_mode as set_pilot_mode
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
from abacus.modules.platform.safeguards import SUBSCRIPTIONS as WISP_SUBSCRIPTIONS
from abacus.modules.platform.safeguards import open_controls as open_pub4557_controls
from abacus.modules.platform.safeguards import register_wisp_document_reader
from abacus.modules.platform.safeguards_routes import controls_platform_router
from abacus.modules.platform.security_center_contract import (
    incident_reads_router,
    safeguards_router,
)
from abacus.modules.platform.service import BudgetInvalid
from abacus.modules.platform.slots import (
    HomeCount,
    HomeCountProvider,
    HomeOfficeCount,
    HomeStatusCount,
    SearchDocument,
    home_count,
    home_count_keys,
    register_home_count,
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
    WispPackFacts,
    WispPackFailure,
    WispPackInput,
)
from abacus.modules.platform.workflows import (
    CANARY_EVERY,
    G04_PLAN_PATCH,
    INCIDENT_REMINDERS_ID,
    SPEND_ANOMALY_ID,
    CanaryWorkflow,
    IncidentClockRemindersWorkflow,
    IncidentPropagationWorkflow,
    SpendAnomalyWorkflow,
    TenantKeyWorkflow,
    TenantProvisioningWorkflow,
    WispPackWorkflow,
    canary_workflow_id,
    incident_propagation_workflow_id,
    provisioning_workflow_id,
    tenant_key_workflow_id,
)

# G-02-T09 (DEC-435): labelers and value resolvers for identity-owned audit targets.
register_audit_resolvers()
# G-02-T14 (AC-30): the posture's open incidents are the register's.
register_posture_source("open_incidents", open_incidents)
# G-02-T20 (AC-30): the posture's open Pub 4557 items are the safeguards record's.
register_posture_source("pub4557_open", open_pub4557_controls)

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    incident_router,  # Q-02-T33: the firm's incident register
    incident_reads_router,  # security-center v1 (G-02-T11 stub; G-02-T18 implements it)
    safeguards_router,  # security-center v1 (G-02-T11 stub; G-02-T20 implements it)
    incident_platform_router,  # Q-02-T33 (RB-27): staff propagation
    controls_platform_router,  # G-02-T20: staff import and publish the Pub 4557 definitions
)

# Q-01-T45: the worker loads this module for tenant provisioning (ADR-156); Q-02-T33 adds the
# incident propagation (time_sensitive); Q-01-T26 the hourly spend-anomaly job (background), on
# its Schedule (`SCHEDULES`, ensured by `abacus_tools.schedules`).
# Q-01-T30: the canary (time_sensitive), on its own Schedule when this environment names one.
WORKFLOWS = {**PROVISIONING_WORKFLOWS, **INCIDENT_WORKFLOWS, **JOB_WORKFLOWS, **CANARY_WORKFLOWS}
# G-02-T20: `wisp_pack.requested` starts the WISP pack's build.
SUBSCRIPTIONS: dict[str, Handler] = {**WISP_SUBSCRIPTIONS}
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
    "INCIDENT_REMINDERS_ID",
    "MODULES",
    "NOTIFY_THRESHOLD",
    "OPERATOR_HANDLE",
    "ROUTERS",
    "SCHEDULES",
    "SPEND_ANOMALY_ID",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "AuditEventRef",
    "AuditLabel",
    "AuditLabeler",
    "AuditNotIncluded",
    "AuditSource",
    "AuditSourceResolver",
    "AuditValueResolver",
    "AuditValueRow",
    "AuditValues",
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
    "DeciderMustDiffer",
    "Entitlement",
    "EntitlementRequired",
    "Heartbeat",
    "HomeCount",
    "HomeCountProvider",
    "HomeOfficeCount",
    "HomeStatusCount",
    "InMemoryTenantKeyOps",
    "IncidentClockRemindersWorkflow",
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
    "PilotMode",
    "PilotModeRefused",
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
    "WispPackFacts",
    "WispPackFailure",
    "WispPackInput",
    "WispPackWorkflow",
    "audit_labels",
    "audit_source",
    "audit_values",
    "canary_boundary",
    "canary_probe",
    "canary_workflow_id",
    "check_entitlement",
    "clock_day",
    "configure_canary_probe",
    "configure_heartbeat",
    "configure_tenant_key_ops",
    "control_active",
    "enrol_pilot",
    "entitlement",
    "expected_route",
    "facts_sha256",
    "finish_propagation",
    "home_count",
    "home_count_keys",
    "incident_clock",
    "incident_propagation_workflow_id",
    "inv2_violations",
    "mask_value",
    "operator_context",
    "propagate_into",
    "propagation_log",
    "provisioning_workflow_id",
    "record_incident",
    "register_audit_labeler",
    "register_audit_source",
    "register_audit_value_resolver",
    "register_home_count",
    "register_search_projection",
    "register_wisp_document_reader",
    "registered_audit_types",
    "require_entitlement",
    "router",
    "schedules",
    "search_document",
    "set_pilot_mode",
    "should_page",
    "start_propagation",
    "start_provisioning",
    "tenant_key_workflow_id",
]
