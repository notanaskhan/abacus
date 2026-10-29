"""ADM-08 integration settings for the tax engine, the stub (T-01-T02; T-01 §3.7, §4.3).
Contract: `docs/contracts/tax-engine-bridge.md` §3.

A firm's CCH Axcess Tax link runs in file-bridge mode (W2 `cch_axcess_tax.export_file`, no egress
host; T-01-T07): settings with locked cells, the user, office and workflow-status mappings (409
`mapping_conflict` when two statuses map to one engine status) and a format check of the latest
engine file. Each route answers 404 for a client principal, 403 for a principal the matrix
refuses, 404 with `tax.engine_bridge` off and 501 with it on until T-01-T20.
"""

from __future__ import annotations

from typing import Annotated, Literal, NoReturn

from fastapi import Depends, Path
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_ENGINE_BRIDGE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

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


engine_settings_router = AbacusRouter(prefix="/v1/firm/integrations", tags=["integrations"])


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    if ctx.client:
        raise NotFound("integration")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, TAX_ENGINE_BRIDGE):
        raise NotFound(TAX_ENGINE_BRIDGE.name)
    raise NotImplementedYet


@engine_settings_router.get(
    "/{key}/settings",
    action="integration.read",
    response_model=EngineSettingsOut,
    errors=(501,),
)
async def engine_settings_route(key: IntegrationKey, ctx: Ctx) -> EngineSettingsOut:
    await _stub(ctx, "integration.read")


@engine_settings_router.put(
    "/{key}/settings",
    action="integration.configure",
    response_model=EngineSettingsOut,
    errors=(409, 501),
)
async def put_engine_settings_route(
    key: IntegrationKey, body: EngineSettingsIn, ctx: Ctx
) -> EngineSettingsOut:
    await _stub(ctx, "integration.configure")


@engine_settings_router.put(
    "/{key}/user-mapping",
    action="integration.configure",
    response_model=EngineSettingsOut,
    errors=(409, 501),
)
async def put_user_mapping_route(
    key: IntegrationKey, body: MappingIn, ctx: Ctx
) -> EngineSettingsOut:
    await _stub(ctx, "integration.configure")


@engine_settings_router.put(
    "/{key}/office-mapping",
    action="integration.configure",
    response_model=EngineSettingsOut,
    errors=(409, 501),
)
async def put_office_mapping_route(
    key: IntegrationKey, body: MappingIn, ctx: Ctx
) -> EngineSettingsOut:
    await _stub(ctx, "integration.configure")


@engine_settings_router.put(
    "/{key}/status-mirror",
    action="integration.configure",
    response_model=EngineSettingsOut,
    errors=(409, 501),
)
async def put_status_mirror_route(
    key: IntegrationKey, body: MappingIn, ctx: Ctx
) -> EngineSettingsOut:
    """Workflow-status mapping (409 `mapping_conflict`)."""
    await _stub(ctx, "integration.configure")


@engine_settings_router.post(
    "/{key}/test",
    action="integration.test",
    response_model=FormatCheckOut,
    errors=(501,),
)
async def test_engine_route(key: IntegrationKey, ctx: Ctx) -> FormatCheckOut:
    await _stub(ctx, "integration.test")
