"""ADM-08 integration settings for the tax engine, the stub (T-01-T02; T-01 §3.7, §4.3).
Contract: `docs/contracts/tax-engine-bridge.md` §3.

A firm's CCH Axcess Tax link runs in file-bridge mode (W2 `cch_axcess_tax.export_file`, no egress
host; T-01-T07): settings with locked cells, the user, office and workflow-status mappings (409
`mapping_conflict` when two statuses map to one engine status) and a format check of the latest
engine file. Each route answers 404 for a client principal, 403 for a principal the matrix
refuses and 404 with `tax.engine_bridge` off; live since T-01-T20 (`engine_settings`).
"""

from __future__ import annotations

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Path
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_ENGINE_BRIDGE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.integrations import engine_settings as svc

Ctx = Annotated[AuthContext, Depends(current_context)]
IntegrationKey = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{2,59}$")]
MappingKind = Literal[
    "return_id_template",
    "client_code_rule",
    "type_letters",
    "user",
    "office",
    "export_rules",
    "workflow_status",
]


class SettingCellOut(BaseModel):
    """One setting; a locked cell shows why (a code), and its control is disabled."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    value: Annotated[str | None, classified("internal")]
    locked: Annotated[bool, classified("internal")]
    lock_reason: Annotated[str | None, classified("internal")]


class MappingRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[MappingKind, classified("internal")]
    source_key: Annotated[str, classified("internal")]
    target_value: Annotated[str, classified("confidential")]
    direction: Annotated[Literal["one_way", "two_way"] | None, classified("internal")]


class EngineSettingsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    mode: Annotated[Literal["file_bridge", "api"], classified("internal")]
    enabled: Annotated[bool, classified("internal")]
    cells: Annotated[list[SettingCellOut], classified("internal")]
    mappings: Annotated[list[MappingRowOut], classified("confidential")]
    version: Annotated[int, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    # T-01-T51 (additive): the return of the firm's last engine sync, for ADM-08's Last sync link
    # to TAX-09 (which authorises the return itself); None before the first sync.
    last_sync_return_id: Annotated[UUID | None, classified("internal")] = None


class EngineSettingsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    cells: Annotated[dict[str, str], classified("internal")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class MappingIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: Annotated[dict[str, str], classified("confidential")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class FormatCheckOut(BaseModel):
    """A format check of the latest engine file: codes, never file content."""

    model_config = ConfigDict(frozen=True)

    ok: Annotated[bool, classified("internal")]
    problems: Annotated[list[str], classified("internal")]
    # T-01-T20 (additive): "Test passed · 3 returns read".
    returns_read: Annotated[int | None, classified("internal")] = None


engine_settings_router = AbacusRouter(prefix="/v1/firm/integrations", tags=["integrations"])


async def _gate(ctx: AuthContext, action: str) -> None:
    """Client 404, the action at the firm (403), then the flag (404)."""
    if ctx.client:
        raise NotFound("integration")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, TAX_ENGINE_BRIDGE):
        raise NotFound(TAX_ENGINE_BRIDGE.name)


def _out(v: svc.SettingsView) -> EngineSettingsOut:
    return EngineSettingsOut(
        key=v.key,
        mode=v.mode,
        enabled=v.enabled,
        cells=[
            SettingCellOut(key=c.key, value=c.value, locked=c.locked, lock_reason=c.lock_reason)
            for c in v.cells
        ],
        mappings=[
            MappingRowOut(
                kind=cast(MappingKind, m.kind),
                source_key=m.source_key,
                target_value=m.target_value,
                direction=cast(Literal["one_way", "two_way"] | None, m.direction),
            )
            for m in v.mappings
        ],
        version=v.version,
        allowed_actions=list(v.allowed_actions),
    )


@engine_settings_router.get(
    "/{key}/settings",
    action="integration.read",
    response_model=EngineSettingsOut,
    errors=(),
)
async def engine_settings_route(key: IntegrationKey, ctx: Ctx) -> EngineSettingsOut:
    """ADM-08 a: the cells with their locks and the mappings."""
    await _gate(ctx, "integration.read")
    out = _out(await svc.settings_view(ctx, key))
    return out.model_copy(update={"last_sync_return_id": await svc.last_engine_sync(ctx.tenant)})


@engine_settings_router.put(
    "/{key}/settings",
    action="integration.configure",
    response_model=EngineSettingsOut,
    errors=(409,),
)
async def put_engine_settings_route(
    key: IntegrationKey, body: EngineSettingsIn, ctx: Ctx
) -> EngineSettingsOut:
    """ADM-08 a: save cells (fresh MFA). 409 `setting_locked`, `stale_version`; 422
    `setting_invalid`."""
    await _gate(ctx, "integration.configure")
    return _out(await svc.save_cells(ctx, key, body.cells, body.seen_version))


@engine_settings_router.put(
    "/{key}/user-mapping",
    action="integration.configure",
    response_model=EngineSettingsOut,
    errors=(409,),
)
async def put_user_mapping_route(
    key: IntegrationKey, body: MappingIn, ctx: Ctx
) -> EngineSettingsOut:
    """ADM-08 b: the user mapping, replaced with the rows sent."""
    await _gate(ctx, "integration.configure")
    return _out(await svc.save_mapping(ctx, key, "user", body.rows, body.seen_version))


@engine_settings_router.put(
    "/{key}/office-mapping",
    action="integration.configure",
    response_model=EngineSettingsOut,
    errors=(409,),
)
async def put_office_mapping_route(
    key: IntegrationKey, body: MappingIn, ctx: Ctx
) -> EngineSettingsOut:
    """ADM-08 b: the office mapping, replaced with the rows sent."""
    await _gate(ctx, "integration.configure")
    return _out(await svc.save_mapping(ctx, key, "office", body.rows, body.seen_version))


@engine_settings_router.put(
    "/{key}/status-mirror",
    action="integration.configure",
    response_model=EngineSettingsOut,
    errors=(409,),
)
async def put_status_mirror_route(
    key: IntegrationKey, body: MappingIn, ctx: Ctx
) -> EngineSettingsOut:
    """Workflow-status mapping (409 `mapping_conflict`)."""
    await _gate(ctx, "integration.configure")
    found = await svc.save_mapping(ctx, key, "workflow_status", body.rows, body.seen_version)
    return _out(found)


@engine_settings_router.post(
    "/{key}/test",
    action="integration.test",
    response_model=FormatCheckOut,
    errors=(),
)
async def test_engine_route(key: IntegrationKey, ctx: Ctx) -> FormatCheckOut:
    """ADM-08 d: a format check of the latest engine file (codes only)."""
    await _gate(ctx, "integration.test")
    found = await svc.format_check(ctx, key)
    return FormatCheckOut(
        ok=found.ok, problems=list(found.problems), returns_read=found.returns_read
    )
