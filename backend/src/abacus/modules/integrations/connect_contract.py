"""The C20 v2 Connect contract stub (W-01-T03; SPEC-659 AC-1 to AC-35; DEC-5046). Contract: the v2
section of `docs/contracts/c20-integrations.md`; screens WB-10 (catalogue) and WB-11 (detail).

Every route has one matrix action and answers, in order: a portal principal 404 (AC-8); the
action on the firm (fresh MFA where the matrix says so, 403 `mfa_required`); 404 with
`integrations.connect_v1` off; then 501 naming the task that implements it (T07 catalogue, T08
connect and disconnect, T09 import, T15 detail). Nothing here starts a client connection: no route
does (R1, AC-17). Catalogue honesty (AC-4) is the service's; the stub's typed fixtures are the
synthetic tenant's (`abacus_tools…brightwater_hale/connect_catalog.py`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import INTEGRATIONS_CONNECT_V1
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    authorise_own,
    current_context,
)
from abacus.modules.integrations.connect_catalog import catalogue, interest

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Public = classified("public")
Internal = classified("internal")
Key = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{1,49}$")]
CategoryCode = Literal[
    "tax", "practice", "erp", "grc", "docs", "comms", "prod", "crm", "hris", "spend"
]
TileStatus = Literal[
    "available",
    "coming_soon",
    "connecting",
    "connected",
    "needs_attention",
    "needs_reauth",
    "paused",
    "disconnected",
]
Kind = Literal["firm", "personal", "client_authorised", "file_bridge"]
ConnectAction = Literal[
    "integration.connect_firm",
    "integration.disconnect_firm",
    "integration.connect_personal",
    "integration.disconnect_personal",
    "integration.interest",
]


class InvalidState(DomainConflict):
    code = "invalid_state"


class ConnectDeclined(DomainConflict):
    code = "connect_declined"


class PrerequisiteScopeMissing(DomainConflict):
    code = "prerequisite_scope_missing"


class ConfirmNameMismatch(DomainInvalid):
    code = "confirm_name_mismatch"


class FirmAppDisabled(DomainConflict):
    code = "firm_app_disabled"


class IntegrationNotAvailable(DomainConflict):
    code = "integration_not_available"


# --- WB-10 catalogue -----------------------------------------------------------------------------


class ConnectTileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Public]
    name: Annotated[str, Public]
    categories: Annotated[list[CategoryCode], Public]
    icon: Annotated[str, Public]  # the category glyph, never a vendor logo (AC-5)
    tone: Annotated[str, Public]
    description: Annotated[str, Public]
    auth_line: Annotated[str, Public]
    kind: Annotated[Kind, Public]
    status: Annotated[TileStatus, Internal]  # honest, for this firm (AC-4)
    viewer_status: Annotated[TileStatus, Internal]  # personal tiles: the viewer's own install
    connected_by_label: Annotated[str | None, classified("confidential")]
    blocked_reason: Annotated[str | None, Public]
    allowed_actions: Annotated[list[ConnectAction], Public]


class ConnectCountsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    all: Annotated[int, Field(ge=0), Internal]
    connected: Annotated[int, Field(ge=0), Internal]
    available: Annotated[int, Field(ge=0), Internal]
    coming_soon: Annotated[int, Field(ge=0), Internal]


class ConnectCategoryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[CategoryCode, Public]
    label: Annotated[str, Public]
    description: Annotated[str, Public]
    count: Annotated[int, Field(ge=0), Internal]  # catalogue totals at the clock (AC-2)


class ConnectBuildOnAccruedRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[Literal["api_keys", "mcp", "workflow_sync"], Public]
    label: Annotated[str, Public]
    target: Annotated[str, Public]  # ADM-08 live, ADM-09 planned (G-03)
    planned: Annotated[bool, Public]


class ConnectCatalogOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ConnectTileOut], Internal]
    counts: Annotated[ConnectCountsOut, Internal]
    categories: Annotated[list[ConnectCategoryOut], Internal]
    total: Annotated[int, Field(ge=0), Internal]
    build_on_accrued: Annotated[list[ConnectBuildOnAccruedRowOut], Public]


# --- WB-11 detail --------------------------------------------------------------------------------


class ConnectionCardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: Annotated[Literal["token", "firm_app", "file_bridge", "personal"], Internal]
    auth_mode_label: Annotated[str, Public]
    connected_by: Annotated[str | None, classified("confidential")]
    connected_at: Annotated[datetime | None, Internal]
    token_renews_at: Annotated[datetime | None, Internal]  # never in file-bridge mode (AC-23)
    last_sync_at: Annotated[datetime | None, Internal]
    linked_count: Annotated[int | None, Internal]  # "224 (TY2025)"
    linked_label_code: Annotated[str | None, Internal]
    mapping_ref: Annotated[str | None, Internal]  # "2025I:FeldJ:V3" → ADM-08


class ConnectMayDoRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[str, Public]
    gate_label: Annotated[str | None, Public]
    state: Annotated[Literal["allowed", "off_for_firm", "never"], Internal]


class ConnectMayDoOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    read: Annotated[list[ConnectMayDoRowOut], Public]
    write: Annotated[
        list[ConnectMayDoRowOut], Public
    ]  # joined with write-capabilities.yaml (AC-21)
    never: Annotated[list[ConnectMayDoRowOut], Public]


class ConnectIntegrationEventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[str, Internal]
    kind: Annotated[str, Internal]
    at: Annotated[datetime, Internal]
    label: Annotated[str | None, classified("confidential")]  # read time; None when not visible
    ok: Annotated[bool, Internal]


class ConnectHealthOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    summary: Annotated[str, classified("confidential")]
    events: Annotated[list[ConnectIntegrationEventOut], Internal]


class ConnectDependentAgentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Internal]
    name: Annotated[str, Public]


class ConnectDependentsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: Annotated[int, Field(ge=0), Internal]
    paused: Annotated[bool, Internal]  # computed, never stored (AC-15)
    items: Annotated[list[ConnectDependentAgentOut], Internal]


class ConnectConsentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    heading: Annotated[str, Public]
    reads: Annotated[list[str], Public]
    never: Annotated[str, Public]
    version: Annotated[int, Field(ge=1), Public]


class ConnectIntegrationDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Public]
    name: Annotated[str, Public]
    status: Annotated[TileStatus, Internal]
    status_line: Annotated[str | None, classified("confidential")]
    connection: Annotated[ConnectionCardOut, Internal]
    may_do: Annotated[ConnectMayDoOut, Public]
    health: Annotated[ConnectHealthOut, Internal]
    dependents: Annotated[ConnectDependentsOut, Internal]
    who_can_use: Annotated[str, Public]
    managed_by: Annotated[str | None, classified("confidential")]
    consent: Annotated[ConnectConsentOut | None, Public]
    allowed_actions: Annotated[list[ConnectAction], Public]
    version: Annotated[int, Field(ge=1), Internal]


class ConnectIntegrationEventsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ConnectIntegrationEventOut], Internal]
    next_cursor: Annotated[str | None, Internal]


class ConnectClientCompanyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    client_name: Annotated[str, classified("confidential")]
    connected_by_label: Annotated[str, classified("confidential")]  # "Tess Moreno (client)"
    connected_on: Annotated[datetime | None, Internal]
    last_sync_at: Annotated[datetime | None, Internal]
    ok: Annotated[bool, Internal]


class ConnectClientCompaniesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ConnectClientCompanyOut], Internal]
    next_cursor: Annotated[str | None, Internal]


# --- connect, complete, disconnect, interest, import ---------------------------------------------


class ConnectStartOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Annotated[Literal["connecting", "connected"], Internal]
    authorise_url: Annotated[str | None, Internal]  # None for a firm app (connected at once)


class ConnectCompleteIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Annotated[str, Field(min_length=16, max_length=256), classified("restricted")]
    code: Annotated[str, Field(min_length=1, max_length=2048), classified("restricted")]


class ConnectCompleteOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Public]
    status: Annotated[Literal["connected"], Internal]


class ConnectDisconnectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_name: Annotated[str, Field(min_length=1, max_length=80), classified("confidential")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class ConnectDisconnectOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Public]
    status: Annotated[Literal["disconnected"], Internal]
    suspended_client_connections: Annotated[int, Field(ge=0), Internal]


class ConnectInterestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Public]
    recorded: Annotated[bool, Public]


class ConnectCatalogImportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID | None, Internal]  # None on a dry run
    dry_run: Annotated[bool, Internal]
    added: Annotated[list[str], Internal]
    changed: Annotated[list[str], Internal]
    unpublished: Annotated[list[str], Internal]  # catalogue keys the import takes off the tiles
    document_sha256: Annotated[str, Internal]


class ConnectCatalogImportsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ConnectCatalogImportOut], Internal]


# WB-10's "Build on Accrued" rows (its screen contract's Links): ADM-08 live, ADM-09 planned.
BUILD_ON_ACCRUED: Final = [
    ConnectBuildOnAccruedRowOut(
        key="workflow_sync", label="Workflow status sync", target="ADM-08", planned=False
    ),
    ConnectBuildOnAccruedRowOut(
        key="api_keys", label="API keys & webhooks", target="ADM-09", planned=True
    ),
    ConnectBuildOnAccruedRowOut(
        key="mcp", label="MCP for AI assistants", target="ADM-09", planned=True
    ),
]

# --- routes --------------------------------------------------------------------------------------

router = AbacusRouter(prefix="/v1", tags=["connect"])


# W-01-T07: the actions a person takes for themself (the catalogue, their own installs, the OAuth
# callback, Notify me): every staff member holds them, firm role or not (`authorise_own`). Firm
# connect and disconnect, and the client-companies list, are the firm's (`authorise`).
_OWN: Final = frozenset(
    {
        "integration_catalog.read",
        "integration.connect_personal",
        "integration.disconnect_personal",
        "integration.complete_connect",
        "integration.interest",
    }
)


async def _gate(ctx: AuthContext, action: str) -> None:
    if ctx.client:
        raise NotFound("integration")
    if action in _OWN:
        await authorise_own(ctx, action)
    else:
        await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, INTEGRATIONS_CONNECT_V1):
        raise NotFound(INTEGRATIONS_CONNECT_V1.name)


@router.get(
    "/integrations/catalog",
    action="integration_catalog.read",
    response_model=ConnectCatalogOut,
    errors=(501,),
)
async def connect_catalog(
    ctx: Ctx,
    category: Annotated[CategoryCode | None, Query()] = None,
    status: Annotated[Literal["connected", "available", "coming_soon"] | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> ConnectCatalogOut:
    """WB-10: honest tiles, counts and catalogue-total category counts (W-01-T07)."""
    await _gate(ctx, "integration_catalog.read")
    found = await catalogue(ctx, category=category, status=status, q=q)
    return ConnectCatalogOut(
        items=[
            ConnectTileOut(
                key=t.row.key,
                name=t.row.name,
                categories=cast(list[CategoryCode], list(t.row.categories)),
                icon=t.row.icon,
                tone=t.row.tone,
                description=t.row.description,
                auth_line=t.row.auth_line,
                kind=t.kind,
                status=t.status,
                viewer_status=t.viewer_status,
                connected_by_label=t.connected_by_label,
                blocked_reason=t.blocked_reason,
                allowed_actions=cast(list[ConnectAction], list(t.allowed_actions)),
            )
            for t in found.tiles
        ],
        counts=ConnectCountsOut(**found.counts),
        categories=[
            ConnectCategoryOut(
                code=cast(CategoryCode, code), label=label, description=about, count=count
            )
            for code, label, about, count in found.categories
        ],
        total=found.total,
        build_on_accrued=BUILD_ON_ACCRUED,
    )


@router.get(
    "/integrations/{key}",
    action="integration_catalog.read",
    response_model=ConnectIntegrationDetailOut,
    errors=(501,),
)
async def connect_detail(key: Key, ctx: Ctx) -> ConnectIntegrationDetailOut:
    """WB-11: the mode-aware projection."""
    await _gate(ctx, "integration_catalog.read")
    raise NotImplementedYet("W-01-T15")


@router.get(
    "/integrations/{key}/events",
    action="integration_catalog.read",
    response_model=ConnectIntegrationEventsOut,
    errors=(501,),
)
async def connect_events(
    key: Key, ctx: Ctx, cursor: str | None = None
) -> ConnectIntegrationEventsOut:
    await _gate(ctx, "integration_catalog.read")
    raise NotImplementedYet("W-01-T15")


@router.get(
    "/integrations/{key}/client-companies",
    action="integration.read_client_companies",
    response_model=ConnectClientCompaniesOut,
    errors=(501,),
)
async def connect_client_companies(
    key: Key,
    ctx: Ctx,
    q: Annotated[str | None, Query(max_length=80)] = None,
    cursor: str | None = None,
) -> ConnectClientCompaniesOut:
    """WB-11 d through `connections.api`, `visible()` and walls; no hidden counts."""
    await _gate(ctx, "integration.read_client_companies")
    raise NotImplementedYet("W-01-T15")


@router.post(
    "/integrations/{key}/connect",
    action="integration.connect_firm",
    response_model=ConnectStartOut,
    errors=(409, 501),
)
async def connect_firm(key: Key, ctx: Ctx, _key: IdempotencyKey) -> ConnectStartOut:
    """Enable or Reconnect (fresh MFA); a firm app is connected at once."""
    await _gate(ctx, "integration.connect_firm")
    raise NotImplementedYet("W-01-T08")


@router.post(
    "/me/integrations/{key}/connect",
    action="integration.connect_personal",
    response_model=ConnectStartOut,
    errors=(409, 501),
)
async def connect_personal(key: Key, ctx: Ctx, _key: IdempotencyKey) -> ConnectStartOut:
    await _gate(ctx, "integration.connect_personal")
    raise NotImplementedYet("W-01-T08")


@router.post(
    "/integrations/connect/complete",
    action="integration.complete_connect",
    response_model=ConnectCompleteOut,
    errors=(409, 501),
)
async def connect_complete(
    body: ConnectCompleteIn, ctx: Ctx, _key: IdempotencyKey
) -> ConnectCompleteOut:
    """The state is spent in its own unit of work; neither code nor state is ever logged."""
    await _gate(ctx, "integration.complete_connect")
    raise NotImplementedYet("W-01-T08")


@router.post(
    "/integrations/{key}/disconnect",
    action="integration.disconnect_firm",
    response_model=ConnectDisconnectOut,
    errors=(409, 501),
)
async def disconnect_firm(
    key: Key, body: ConnectDisconnectIn, ctx: Ctx, _key: IdempotencyKey
) -> ConnectDisconnectOut:
    """Typed name (422 `confirm_name_mismatch`), `seen_version`, fresh MFA."""
    await _gate(ctx, "integration.disconnect_firm")
    raise NotImplementedYet("W-01-T08")


@router.post(
    "/me/integrations/{key}/disconnect",
    action="integration.disconnect_personal",
    response_model=ConnectDisconnectOut,
    errors=(409, 501),
)
async def disconnect_personal(key: Key, ctx: Ctx, _key: IdempotencyKey) -> ConnectDisconnectOut:
    await _gate(ctx, "integration.disconnect_personal")
    raise NotImplementedYet("W-01-T08")


@router.post(
    "/integrations/{key}/interest",
    action="integration.interest",
    response_model=ConnectInterestOut,
    errors=(409, 501),
)
async def connect_interest(key: Key, ctx: Ctx, _key: IdempotencyKey) -> ConnectInterestOut:
    """Notify me (AC-31): idempotent; `recorded` is true on every answer (W-01-T07)."""
    await _gate(ctx, "integration.interest")
    await interest(ctx, key)
    return ConnectInterestOut(key=key, recorded=True)


@router.post(
    "/platform/integration-catalog/imports",
    action="integration_catalog.import",
    response_model=ConnectCatalogImportOut,
    errors=(409, 501),
)
async def connect_import(
    ctx: Ctx, _key: IdempotencyKey, dry_run: bool = True
) -> ConnectCatalogImportOut:
    """The platform operator's only (no firm principal holds the action; AC-32)."""
    await _gate(ctx, "integration_catalog.import")
    raise NotImplementedYet("W-01-T09")


@router.get(
    "/platform/integration-catalog/imports",
    action="integration_catalog.import",
    response_model=ConnectCatalogImportsOut,
    errors=(501,),
)
async def connect_import_log(ctx: Ctx) -> ConnectCatalogImportsOut:
    await _gate(ctx, "integration_catalog.import")
    raise NotImplementedYet("W-01-T09")
