"""The platform console contract stubs, staff side (G-04-T03; SPEC-680 AC-1 to AC-13, AC-47,
AC-55, AC-57, AC-58; SPEC-681 AC-15, AC-17; DEC-5203). Contracts:
`docs/contracts/platform-console.md` (directory, entitlements, provisioning, regions, sessions,
plan requests) and
`docs/contracts/support.md` (support queue, status incidents, publications). Screen: PLT-01.

Every route declares one staff action of the matrix's staff section (DEC-5202), so it
authenticates with the staff token on the staff issuer (`identity.routing.staff_action`); no
firm, portal, agent or break-glass principal reaches one. It then answers 501 naming its task
(G-04-T09 console API, G-04-T10 support, status and publications). The staff role check on the
token's claims and the global `platform.console` read land with G-04-T09: flags on this
repository are per firm (`feature_flag_states` is tenant-scoped), so T09 adds the global read.

**Metadata only** (AC-2): firm display names, tenant codes, counts, module keys, health reason
codes and staff or firm-user display names. No field can hold a client, contact, engagement or
document name; a support session shows its scope kind only (SPEC-681 AC-17). There is no route
that approves, grants or opens a support session for staff (SPEC-681 AC-15).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, Staff, current_staff
from abacus.modules.platform.plan_usage_contract import ModuleKey, PlanRequestKind

StaffDep = Annotated[Staff, Depends(current_staff)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
TenantCode = Annotated[str, Field(pattern=r"^tnt_[a-z0-9-]{2,40}$"), Internal]
Reason = Annotated[str, Field(min_length=20, max_length=500), classified("confidential")]
Health = Literal["healthy", "degraded", "onboarding"]
RegionCode = Literal["us", "eu", "uk"]
ScopeKind = Literal["metadata", "integration_settings", "content"]
SessionStatus = Literal["requested", "active", "declined", "revoked", "ended", "expired"]
PlanRequestStatus = Literal["sent_to_accrued", "applied"]
IncidentSeverity = Literal["degraded", "outage", "maintenance"]
PublicationKind = Literal["help_article", "reference_set"]


class SeatsBelowUsed(DomainConflict):
    """Seats set below the seats in use (AC-8)."""

    code = "seats_below_used"


class RegionNotLive(DomainInvalid):
    """Provisioning in a region whose `platform_regions.status` is not `live` (AC-12)."""

    code = "region_not_live"


class TenantCodeTaken(DomainConflict):
    """Another tenant already holds this tenant code (AC-12)."""

    code = "tenant_code_taken"


class ApproverIsDrafter(DomainConflict):
    """The staff member who drafted a version cannot publish it (AC-52, AC-57; K-02)."""

    code = "approver_is_drafter"


# --- directory and drawer (AC-1 to AC-9) ---------------------------------------------------------


class SeatCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    used: Annotated[int, Field(ge=0), Internal]
    total: Annotated[int, Field(ge=0), Internal]


class TenantRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_code: TenantCode
    display_name: Annotated[str, Internal]  # the firm's display name; never a client's
    region: Annotated[RegionCode, Internal]
    seats: SeatCountOut
    modules: Annotated[list[ModuleKey], Internal]
    health: Annotated[Health, Internal]
    health_reason_code: Annotated[str | None, Internal]
    library_channel_label: Annotated[str, Internal]
    support_state: Annotated[SessionStatus | None, Internal]
    support_state_at: Annotated[datetime | None, Internal]
    synthetic: Annotated[bool, Internal]
    sandbox_of: Annotated[str | None, Internal]  # the parent's tenant code
    plan_requests_open: Annotated[int, Field(ge=0), Internal]
    since: Annotated[date, Internal]


class TenantTilesOut(BaseModel):
    """Tile counts ignore the tile filter (P-36 list envelope; AC-3)."""

    model_config = ConfigDict(frozen=True)

    tenants: Annotated[int, Field(ge=0), Internal]
    healthy: Annotated[int, Field(ge=0), Internal]
    degraded: Annotated[int, Field(ge=0), Internal]
    onboarding: Annotated[int, Field(ge=0), Internal]
    seats_used: Annotated[int, Field(ge=0), Internal]  # sandboxes excluded
    seats_provisioned: Annotated[int, Field(ge=0), Internal]


class TenantsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[TenantRowOut], Internal]
    counts: TenantTilesOut
    next_cursor: Annotated[str | None, Internal] = None


class SessionHistoryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: Annotated[UUID, Internal]
    requested_by: Annotated[str, Internal]  # staff display name
    reason_fingerprint: Annotated[str, Internal]  # the text stays in the firm's trail
    scope_kind: Annotated[ScopeKind, Internal]
    approver_display_name: Annotated[str | None, Internal]
    approver_role: Annotated[Literal["firm_admin", "security_admin"] | None, Internal]
    duration_minutes: Annotated[int, Field(ge=1, le=240), Internal]
    status: Annotated[SessionStatus, Internal]
    started_at: Annotated[datetime | None, Internal]
    closed_at: Annotated[datetime | None, Internal]


class TenantDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    row: TenantRowOut
    renewal_on: Annotated[date, Internal]
    seats_total: Annotated[int, Field(ge=1), Internal]
    included_agent_minutes: Annotated[int, Field(ge=0), Internal]
    region_storage_label: Annotated[str, Internal]  # "Storage Ohio, backup Oregon; inference US"
    policy_principal_available: Annotated[bool, Internal]
    firm_allows_session_requests: Annotated[bool, Internal]
    support_history: Annotated[list[SessionHistoryOut], Internal]
    entitlement_version: Annotated[int, Field(ge=1), Internal]


class EntitlementsPatchIn(BaseModel):
    """PATCH …/entitlements (AC-7, AC-8): staff MFA within 15 minutes and a reason."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Reason
    seats_total: Annotated[int | None, Field(ge=1, le=10_000), Internal] = None
    modules: Annotated[list[ModuleKey] | None, Field(max_length=10), Internal] = None
    renewal_on: Annotated[date | None, Internal] = None
    included_agent_minutes: Annotated[int | None, Field(ge=0, le=10_000_000), Internal] = None
    policy_principal_available: Annotated[bool | None, Internal] = None
    plan_request_id: Annotated[UUID | None, Internal] = None


# --- provisioning (AC-10 to AC-13) ---------------------------------------------------------------


class FirstAdminIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    email: Annotated[str, Field(min_length=3, max_length=320), classified("confidential")]
    role: Annotated[Literal["firm_admin", "security_admin"], Internal]


class ProvisionTenantIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    legal_name: Annotated[str, Field(min_length=2, max_length=200), Internal]
    display_name: Annotated[str, Field(min_length=2, max_length=120), Internal]
    region: Annotated[RegionCode, Internal]
    modules: Annotated[list[ModuleKey], Field(min_length=1, max_length=10), Internal]
    seats_total: Annotated[int, Field(ge=1, le=10_000), Internal]
    first_admins: Annotated[list[FirstAdminIn], Field(min_length=2, max_length=2), Internal]


class SandboxIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Reason


class ProvisioningOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    workflow_id: Annotated[str, Internal]
    status: Annotated[Literal["running", "completed", "failed"], Internal]
    tenant_code: Annotated[str | None, Internal]
    invites_sent: Annotated[int, Field(ge=0), Internal]


class PlatformRegionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[RegionCode, Internal]
    label: Annotated[str, Internal]
    status: Annotated[Literal["live", "planned"], Internal]
    planned_label: Annotated[str | None, Internal]  # content, never code (AC-5)
    storage_label: Annotated[str | None, Internal]


class PlatformRegionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[PlatformRegionOut], Internal]


# --- sessions and plan requests across tenants ---------------------------------------------------


class PlatformSessionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_code: TenantCode
    firm_display_name: Annotated[str, Internal]
    history: SessionHistoryOut


class PlatformSessionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[PlatformSessionOut], Internal]
    counts: Annotated[dict[str, int], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class PlatformPlanRequestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    tenant_code: TenantCode
    firm_display_name: Annotated[str, Internal]
    kind: Annotated[PlanRequestKind, Internal]
    from_value: Annotated[int | None, Internal]
    to_value: Annotated[int | None, Internal]
    modules_add: Annotated[list[ModuleKey], Internal]
    effective_from: Annotated[date | None, Internal]
    approved_by_display_name: Annotated[str, Internal]
    status: Annotated[PlanRequestStatus, Internal]
    sent_at: Annotated[datetime, Internal]


class PlatformPlanRequestsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[PlatformPlanRequestOut], Internal]
    counts: Annotated[dict[str, int], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class MarkAppliedIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entitlement_version: Annotated[int, Field(ge=1), Internal]


# --- support queue (AC-47) -----------------------------------------------------------------------


class QueueConversationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    tenant_code: TenantCode
    firm_display_name: Annotated[str, Internal]
    owner_display_name: Annotated[str, Internal]
    last_firm_message_at: Annotated[datetime | None, Internal]
    last_staff_message_at: Annotated[datetime | None, Internal]
    unanswered: Annotated[bool, Internal]
    assigned_to: Annotated[str | None, Internal]


class QueueConversationsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[QueueConversationOut], Internal]
    counts: Annotated[dict[str, int], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class QueueMessageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    author_kind: Annotated[Literal["firm_user", "staff"], Internal]
    author_display_name: Annotated[str, Internal]
    body: Annotated[str, classified("confidential")]
    related_article_slug: Annotated[str | None, Internal]
    created_at: Annotated[datetime, Internal]


class QueueConversationDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation: QueueConversationOut
    messages: Annotated[list[QueueMessageOut], Internal]


class StaffReplyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Annotated[str, Field(min_length=1, max_length=4000), classified("confidential")]
    related_article_slug: Annotated[str | None, Field(max_length=120), Internal] = None


# --- status incidents (AC-55) --------------------------------------------------------------------


class StatusIncidentUpdateOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: Annotated[datetime, Internal]
    note: Annotated[str, Field(max_length=280), Internal]
    posted_by: Annotated[str, Internal]


class StatusIncidentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    component_key: Annotated[str, Internal]
    severity: Annotated[IncidentSeverity, Internal]
    title: Annotated[str, Internal]
    public_note: Annotated[str, Field(max_length=280), Internal]
    started_at: Annotated[datetime, Internal]
    resolved_at: Annotated[datetime | None, Internal]
    posted_by: Annotated[str, Internal]
    updates: Annotated[list[StatusIncidentUpdateOut], Internal]


class StatusIncidentsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[StatusIncidentOut], Internal]
    counts: Annotated[dict[str, int], Internal]


class StatusIncidentIn(BaseModel):
    """A note never names a firm or client (lint plus runbook templates)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    component_key: Annotated[str, Field(min_length=1, max_length=80), Internal]
    severity: Annotated[IncidentSeverity, Internal]
    title: Annotated[str, Field(min_length=3, max_length=120), Internal]
    public_note: Annotated[str, Field(min_length=3, max_length=280), Internal]


class StatusIncidentUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    note: Annotated[str, Field(min_length=3, max_length=280), Internal]


# --- publications (AC-57, AC-58) -----------------------------------------------------------------


class ConsolePublicationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    kind: Annotated[PublicationKind, Internal]
    key: Annotated[str, Internal]  # article slug or reference-set key
    version: Annotated[int, Field(ge=1), Internal]
    drafted_by: Annotated[str, Internal]
    effective_from: Annotated[date | None, Internal]
    rows_added: Annotated[int, Field(ge=0), Internal]
    rows_changed: Annotated[int, Field(ge=0), Internal]
    rows_removed: Annotated[int, Field(ge=0), Internal]
    status: Annotated[Literal["draft", "published", "withdrawn"], Internal]
    can_publish: Annotated[bool, Internal]  # false for the drafter ("You drafted this version")


class ConsolePublicationsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ConsolePublicationOut], Internal]
    counts: Annotated[dict[str, int], Internal]


class ConsolePublishIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Reason


# --- routes --------------------------------------------------------------------------------------

router = AbacusRouter(prefix="/v1/platform", tags=["platform console"])
_CONSOLE = "G-04-T09"
_SUPPORT = "G-04-T10"


@router.get("/tenants", action="platform_tenant.read", response_model=TenantsOut)
async def console_tenants(
    staff: StaffDep,
    region: Annotated[RegionCode | None, Query()] = None,
    health: Annotated[Health | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    tile: Annotated[Health | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> TenantsOut:
    """PLT-01 a (AC-1 to AC-4): the directory, metadata only (G-04-T09)."""
    from abacus.modules.platform import console

    del cursor
    return await console.tenants(staff, region=region, health=health, q=q, tile=tile)


@router.get(
    "/tenants/{tenant_code}",
    action="platform_tenant.read",
    response_model=TenantDetailOut,
)
async def console_tenant(tenant_code: str, staff: StaffDep) -> TenantDetailOut:
    from abacus.modules.platform import console

    return await console.tenant(staff, tenant_code)


@router.patch(
    "/tenants/{tenant_code}/entitlements",
    action="platform_entitlements.update",
    response_model=TenantDetailOut,
    errors=(409,),
)
async def console_patch_entitlements(
    tenant_code: str, body: EntitlementsPatchIn, staff: StaffDep
) -> TenantDetailOut:
    """AC-7, AC-8: staff MFA within 15 minutes and a reason; the firm's trail names the staff
    member (G-04-T09)."""
    from abacus.modules.platform import console

    return await console.patch_entitlements(staff, tenant_code, body)


@router.post(
    "/tenants",
    action="platform_tenant.provision",
    response_model=ProvisioningOut,
    status_code=202,
    errors=(409, 501),
)
async def console_provision(body: ProvisionTenantIn, _key: IdempotencyKey) -> ProvisioningOut:
    raise NotImplementedYet(_CONSOLE)


@router.post(
    "/tenants/{tenant_code}/sandbox",
    action="platform_tenant.provision",
    response_model=ProvisioningOut,
    status_code=202,
    errors=(409, 501),
)
async def console_sandbox(
    tenant_code: str, body: SandboxIn, _key: IdempotencyKey
) -> ProvisioningOut:
    raise NotImplementedYet(_CONSOLE)


@router.get(
    "/provisioning/{workflow_id}",
    action="platform_tenant.read",
    response_model=ProvisioningOut,
    errors=(501,),
)
async def console_provisioning(workflow_id: str) -> ProvisioningOut:
    raise NotImplementedYet(_CONSOLE)


@router.get("/regions", action="platform_tenant.read", response_model=PlatformRegionsOut)
async def console_regions(staff: StaffDep) -> PlatformRegionsOut:
    from abacus.modules.platform import console

    return await console.regions(staff)


@router.get(
    "/support-sessions",
    action="platform_tenant.read",
    response_model=PlatformSessionsOut,
)
async def console_support_sessions(
    staff: StaffDep,
    status: Annotated[SessionStatus | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> PlatformSessionsOut:
    from abacus.modules.platform import console

    del cursor
    return await console.support_sessions(staff, status)


@router.get(
    "/plan-requests",
    action="platform_tenant.read",
    response_model=PlatformPlanRequestsOut,
)
async def console_plan_requests(
    staff: StaffDep,
    status: Annotated[PlanRequestStatus | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> PlatformPlanRequestsOut:
    from abacus.modules.platform import console

    del cursor
    return await console.plan_requests(staff, status)


@router.post(
    "/plan-requests/{request_id}/mark-applied",
    action="platform_entitlements.update",
    response_model=PlatformPlanRequestOut,
    errors=(409,),
)
async def console_mark_applied(
    request_id: UUID, body: MarkAppliedIn, staff: StaffDep
) -> PlatformPlanRequestOut:
    from abacus.modules.platform import console

    return await console.mark_applied(staff, request_id, body.entitlement_version)


@router.get(
    "/support/conversations",
    action="platform_support.reply",
    response_model=QueueConversationsOut,
)
async def console_queue(
    staff: StaffDep,
    unanswered: Annotated[bool | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> QueueConversationsOut:
    """PLT-01 Support (AC-47): every firm's open threads (G-04-T10)."""
    from abacus.modules.platform import support

    del cursor
    found = await support.conversations(staff)
    if unanswered is None:
        return found
    return found.model_copy(
        update={"items": [i for i in found.items if i.unanswered == unanswered]}
    )


@router.get(
    "/support/conversations/{conversation_id}",
    action="platform_support.reply",
    response_model=QueueConversationDetailOut,
)
async def console_queue_conversation(
    conversation_id: UUID, staff: StaffDep
) -> QueueConversationDetailOut:
    from abacus.modules.platform import support

    return await support.detail(staff, conversation_id)


@router.post(
    "/support/conversations/{conversation_id}/messages",
    action="platform_support.reply",
    response_model=QueueMessageOut,
    status_code=201,
)
async def console_queue_reply(
    conversation_id: UUID, body: StaffReplyIn, _key: IdempotencyKey, staff: StaffDep
) -> QueueMessageOut:
    from abacus.modules.platform import support

    return await support.reply(staff, conversation_id, body.body, body.related_article_slug)


@router.get(
    "/status/incidents",
    action="platform_status.manage",
    response_model=StatusIncidentsOut,
    errors=(501,),
)
async def console_incidents(
    open_only: Annotated[bool, Query(alias="open")] = True,
) -> StatusIncidentsOut:
    raise NotImplementedYet(_SUPPORT)


@router.post(
    "/status/incidents",
    action="platform_status.manage",
    response_model=StatusIncidentOut,
    status_code=201,
    errors=(501,),
)
async def console_post_incident(body: StatusIncidentIn, _key: IdempotencyKey) -> StatusIncidentOut:
    raise NotImplementedYet(_SUPPORT)


@router.post(
    "/status/incidents/{incident_id}/updates",
    action="platform_status.manage",
    response_model=StatusIncidentOut,
    errors=(409, 501),
)
async def console_update_incident(
    incident_id: UUID, body: StatusIncidentUpdateIn
) -> StatusIncidentOut:
    raise NotImplementedYet(_SUPPORT)


@router.post(
    "/status/incidents/{incident_id}/resolve",
    action="platform_status.manage",
    response_model=StatusIncidentOut,
    errors=(409, 501),
)
async def console_resolve_incident(
    incident_id: UUID, body: StatusIncidentUpdateIn
) -> StatusIncidentOut:
    raise NotImplementedYet(_SUPPORT)


@router.get(
    "/publications",
    action="platform_content.read",
    response_model=ConsolePublicationsOut,
    errors=(501,),
)
async def console_publications(
    status: Annotated[Literal["draft", "published", "withdrawn"], Query()] = "draft",
) -> ConsolePublicationsOut:
    raise NotImplementedYet(_SUPPORT)


@router.post(
    "/publications/{kind}/{publication_id}/publish",
    action="platform_content.publish",
    response_model=ConsolePublicationOut,
    errors=(409, 501),
)
async def console_publish(
    kind: PublicationKind, publication_id: UUID, body: ConsolePublishIn
) -> ConsolePublicationOut:
    raise NotImplementedYet(_SUPPORT)


@router.post(
    "/publications/{kind}/{publication_id}/withdraw",
    action="platform_content.publish",
    response_model=ConsolePublicationOut,
    errors=(409, 501),
)
async def console_withdraw(
    kind: PublicationKind, publication_id: UUID, body: ConsolePublishIn
) -> ConsolePublicationOut:
    raise NotImplementedYet(_SUPPORT)
