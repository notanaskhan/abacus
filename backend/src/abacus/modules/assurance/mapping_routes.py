"""Account mapping and draft statement routes (SPEC-316; TASK-345)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.assurance.mapping import (
    edit,
    import_csv,
    mapping_for,
    publish,
    sign_mapping,
    start,
    statements,
    versions,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.ledger.api import VersionView

firm_router = AbacusRouter(prefix="/v1/grouping-sets", tags=["mapping"])
router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/trial-balances/{tb_id}", tags=["mapping"]
)
Ctx = Annotated[AuthContext, Depends(current_context)]
Class = Literal["assets", "liabilities", "equity", "revenue", "expenses"]


class GroupingProblemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    row: Annotated[int, classified("internal")]
    code: Annotated[str, classified("internal")]
    detail: Annotated[str, classified("internal")]


class GroupingVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    set_key: Annotated[str, classified("internal")]
    set_name: Annotated[str, classified("internal")]
    version: Annotated[int, classified("internal")]
    status: Annotated[Literal["draft", "published"], classified("internal")]
    problems: Annotated[list[GroupingProblemOut], classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    published_at: Annotated[datetime | None, classified("internal")]


class GroupingImportBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$"), classified("internal")]
    name: Annotated[str, Field(min_length=1, max_length=120), classified("internal")]
    csv: Annotated[str, Field(min_length=1, max_length=500_000), classified("internal")]


class FsLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    normal_balance: Annotated[Literal["debit", "credit"], classified("internal")]
    grouping_key: Annotated[str, classified("internal")]


class GroupingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    class_: Annotated[Class, Field(serialization_alias="class"), classified("internal")]
    lines: Annotated[list[FsLineOut], classified("internal")]


class MappedAccountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("confidential")]
    account_name: Annotated[str, classified("confidential")]
    eoy: Annotated[Decimal, classified("confidential")]
    final: Annotated[Decimal | None, classified("confidential")]
    boy: Annotated[Decimal | None, classified("confidential")]
    fs_line_id: Annotated[UUID | None, classified("internal")]
    method: Annotated[Literal["manual", "number_range"] | None, classified("internal")]
    edited_by: Annotated[UUID | None, classified("internal")]
    edited_at: Annotated[datetime | None, classified("internal")]


class MappingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    mapping_set_id: Annotated[UUID | None, classified("internal")]
    version: Annotated[GroupingVersionOut | None, classified("internal")]
    groupings: Annotated[list[GroupingOut], classified("internal")]
    accounts: Annotated[list[MappedAccountOut], classified("confidential")]
    mapped: Annotated[int, classified("internal")]
    unmapped: Annotated[int, classified("internal")]
    manual: Annotated[int, classified("internal")]
    content_hash: Annotated[str | None, classified("internal")]
    published_versions: Annotated[list[GroupingVersionOut], classified("internal")]


class StartMappingBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    grouping_set_version_id: Annotated[UUID, classified("internal")]


class MappingEditBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    account_code: Annotated[str, Field(min_length=1, max_length=64), classified("confidential")]
    fs_line_id: Annotated[UUID | None, classified("internal")] = None


class MappingEditsBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    accounts: Annotated[
        list[MappingEditBody], Field(min_length=1, max_length=500), classified("confidential")
    ]


class FsStatementLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    cy: Annotated[Decimal, classified("confidential")]
    py: Annotated[Decimal | None, classified("confidential")]


class FsStatementGroupOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    class_: Annotated[Class, Field(serialization_alias="class"), classified("internal")]
    lines: Annotated[list[FsStatementLineOut], classified("confidential")]
    cy: Annotated[Decimal, classified("confidential")]
    py: Annotated[Decimal | None, classified("confidential")]


class FsStatementsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    layer: Annotated[Literal["unadjusted", "final"], classified("internal")]
    groups: Annotated[list[FsStatementGroupOut], classified("confidential")]
    totals: Annotated[dict[str, Decimal], classified("confidential")]
    py_totals: Annotated[dict[str, Decimal] | None, classified("confidential")]
    net_income: Annotated[Decimal, classified("confidential")]
    py_net_income: Annotated[Decimal | None, classified("confidential")]
    difference: Annotated[Decimal, classified("confidential")]
    balanced: Annotated[bool, classified("internal")]
    unmapped: Annotated[int, classified("internal")]


def _version_out(v: VersionView) -> GroupingVersionOut:
    return GroupingVersionOut.model_validate(asdict(v))


async def _mapping_out(ctx: AuthContext, engagement_id: UUID, tb_id: UUID) -> MappingOut:
    found, published = await mapping_for(ctx, engagement_id, tb_id)
    if found is None:
        return MappingOut(
            mapping_set_id=None,
            version=None,
            groupings=[],
            accounts=[],
            mapped=0,
            unmapped=0,
            manual=0,
            content_hash=None,
            published_versions=[_version_out(v) for v in published],
        )
    data = asdict(found)
    return MappingOut.model_validate(
        {
            **data,
            "version": _version_out(found.version),
            "groupings": [GroupingOut.model_validate(g) for g in data["groupings"]],
            "published_versions": [],
        }
    )


@firm_router.get("", action="grouping_set.import", response_model=list[GroupingVersionOut])
async def grouping_set_versions_route(ctx: Ctx) -> list[GroupingVersionOut]:
    """SPEC-316 AC-1: the firm's grouping-set versions, newest first, with their problems."""
    return [_version_out(v) for v in await versions(ctx)]


@firm_router.post(
    "/imports",
    action="grouping_set.import",
    response_model=list[GroupingVersionOut],
    status_code=201,
)
async def import_grouping_set_route(
    body: GroupingImportBody, ctx: Ctx
) -> list[GroupingVersionOut]:
    """SPEC-316 AC-1: import the firm's taxonomy (CSV) as a draft version."""
    await import_csv(ctx, body.key, body.name, body.csv)
    return [_version_out(v) for v in await versions(ctx)]


@firm_router.post(
    "/versions/{version_id}/publish",
    action="grouping_set.publish",
    response_model=list[GroupingVersionOut],
    status_code=201,
)
async def publish_grouping_set_route(version_id: UUID, ctx: Ctx) -> list[GroupingVersionOut]:
    """SPEC-316 AC-2: publish a draft with no problems."""
    await publish(ctx, version_id)
    return [_version_out(v) for v in await versions(ctx)]


@router.get("/mapping", action="trial_balance.read", response_model=MappingOut)
async def mapping_route(engagement_id: UUID, tb_id: UUID, ctx: Ctx) -> MappingOut:
    """SPEC-316 AC-3: every account's FS line (edited, by rule, or unmapped) and the tallies."""
    return await _mapping_out(ctx, engagement_id, tb_id)


@router.post("/mapping", action="mapping_set.edit", response_model=MappingOut, status_code=201)
async def start_mapping_route(
    engagement_id: UUID, tb_id: UUID, body: StartMappingBody, ctx: Ctx
) -> MappingOut:
    """SPEC-316 AC-3: map the trial balance with a published grouping set."""
    await start(ctx, engagement_id, tb_id, body.grouping_set_version_id)
    return await _mapping_out(ctx, engagement_id, tb_id)


@router.put("/mapping/accounts", action="mapping_set.edit", response_model=MappingOut)
async def edit_mapping_route(
    engagement_id: UUID, tb_id: UUID, body: MappingEditsBody, ctx: Ctx
) -> MappingOut:
    """SPEC-316 AC-4: map accounts to FS lines, or back to the rules."""
    await edit(ctx, engagement_id, tb_id, [(a.account_code, a.fs_line_id) for a in body.accounts])
    return await _mapping_out(ctx, engagement_id, tb_id)


@router.post(
    "/mapping/sign-offs/prepare",
    action="sign_off.prepare",
    response_model=MappingOut,
    status_code=201,
)
async def prepare_mapping_route(engagement_id: UUID, tb_id: UUID, ctx: Ctx) -> MappingOut:
    """SPEC-316 AC-5: the preparer signs the mapping (every account mapped)."""
    await sign_mapping(ctx, engagement_id, tb_id, 1)
    return await _mapping_out(ctx, engagement_id, tb_id)


@router.post(
    "/mapping/sign-offs/review",
    action="sign_off.review",
    response_model=MappingOut,
    status_code=201,
)
async def review_mapping_route(engagement_id: UUID, tb_id: UUID, ctx: Ctx) -> MappingOut:
    """SPEC-316 AC-5: the reviewer signs the mapping."""
    await sign_mapping(ctx, engagement_id, tb_id, 2)
    return await _mapping_out(ctx, engagement_id, tb_id)


@router.get("/statements", action="trial_balance.read", response_model=FsStatementsOut | None)
async def statements_route(
    engagement_id: UUID,
    tb_id: UUID,
    ctx: Ctx,
    layer: Literal["unadjusted", "final"] = "unadjusted",
) -> FsStatementsOut | None:
    """SPEC-316 AC-6: the draft balance sheet and income statement from the mapping."""
    found = await statements(ctx, engagement_id, tb_id, layer)
    if found is None:
        return None
    data = asdict(found)
    return FsStatementsOut.model_validate(
        {**data, "groups": [FsStatementGroupOut.model_validate(g) for g in data["groups"]]}
    )
