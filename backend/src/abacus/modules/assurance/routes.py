"""Trial balance routes (SPEC-309; TASK-320). Reads follow `trial_balance.read`; adoption
`trial_balance.adopt`; areas and WP refs `trial_balance.annotate`."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.assurance.trial_balance import (
    adopt,
    new_version,
    newer,
    overview,
    set_annotations,
    sheets,
    view,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.ledger.api import AnnotationEdit, Candidate, Leadsheet, Totals, VersionInfo

router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/trial-balances", tags=["trial balance"]
)
Ctx = Annotated[AuthContext, Depends(current_context)]
Label = Literal["standard", "interim", "prior", "budget", "preliminary"]
Unit = Literal["cents", "whole_dollars"]
Layer = Literal["unadjusted", "aje", "rje", "final"]


class SnapshotOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    period_start: Annotated[date, classified("internal")]
    period_end: Annotated[date, classified("internal")]
    source: Annotated[str, classified("internal")]
    pulled_at: Annotated[datetime, classified("internal")]
    line_count: Annotated[int, classified("internal")]
    total_debit: Annotated[Decimal, classified("confidential")]
    total_credit: Annotated[Decimal, classified("confidential")]
    lines_changed: Annotated[int | None, classified("internal")]
    net_change: Annotated[Decimal | None, classified("confidential")]


class TrialBalanceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    label: Annotated[Label, classified("internal")]
    period_start: Annotated[date, classified("internal")]
    period_end: Annotated[date, classified("internal")]
    display_unit: Annotated[Unit, classified("internal")]
    current_version_no: Annotated[int, classified("internal")]


class TrialBalancesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial_balances: Annotated[list[TrialBalanceOut], classified("internal")]
    snapshots: Annotated[list[SnapshotOut], classified("internal")]


class TbLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("confidential")]
    account_name: Annotated[str, classified("confidential")]
    boy: Annotated[Decimal | None, classified("confidential")]
    debit: Annotated[Decimal, classified("confidential")]
    credit: Annotated[Decimal, classified("confidential")]
    eoy: Annotated[Decimal, classified("confidential")]
    change: Annotated[Decimal | None, classified("confidential")]
    area: Annotated[str | None, classified("confidential")]
    wp_ref: Annotated[str | None, classified("internal")]


class TotalsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    debit: Annotated[Decimal, classified("confidential")]
    credit: Annotated[Decimal, classified("confidential")]
    difference: Annotated[Decimal, classified("confidential")]
    balanced: Annotated[bool, classified("internal")]


class TbVersionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, classified("internal")]
    snapshot_id: Annotated[UUID, classified("internal")]
    prior_snapshot_id: Annotated[UUID | None, classified("internal")]
    adopted_by_name: Annotated[str, classified("internal")]
    reason: Annotated[str | None, classified("confidential")]
    adopted_at: Annotated[datetime, classified("internal")]
    source: Annotated[str, classified("internal")]
    pulled_at: Annotated[datetime, classified("internal")]


class TrialBalanceDetailOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial_balance: Annotated[TrialBalanceOut, classified("internal")]
    version: Annotated[TbVersionOut, classified("internal")]
    versions: Annotated[list[TbVersionOut], classified("internal")]
    lines: Annotated[list[TbLineOut], classified("confidential")]
    eoy: Annotated[TotalsOut, classified("confidential")]
    boy: Annotated[TotalsOut | None, classified("confidential")]


class LeadRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("confidential")]
    account_name: Annotated[str, classified("confidential")]
    py: Annotated[Decimal | None, classified("confidential")]
    cy: Annotated[Decimal, classified("confidential")]
    change: Annotated[Decimal | None, classified("confidential")]
    change_pct: Annotated[Decimal | None, classified("confidential")]


class LeadsheetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    area: Annotated[str, classified("confidential")]
    rows: Annotated[list[LeadRowOut], classified("confidential")]
    py: Annotated[Decimal | None, classified("confidential")]
    cy: Annotated[Decimal, classified("confidential")]
    change: Annotated[Decimal | None, classified("confidential")]
    change_pct: Annotated[Decimal | None, classified("confidential")]


class AdoptBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: Annotated[UUID, classified("internal")]
    prior_snapshot_id: Annotated[UUID | None, classified("internal")] = None
    label: Annotated[Label, classified("internal")] = "standard"
    display_unit: Annotated[Unit, classified("internal")] = "cents"


class VersionBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot_id: Annotated[UUID, classified("internal")]
    prior_snapshot_id: Annotated[UUID | None, classified("internal")] = None
    reason: Annotated[str, Field(min_length=1, max_length=500), classified("confidential")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class AnnotationBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    account_code: Annotated[str, Field(min_length=1, max_length=64), classified("confidential")]
    area: Annotated[str | None, Field(max_length=120), classified("confidential")] = None
    wp_ref: Annotated[str | None, Field(max_length=20), classified("internal")] = None


class AnnotationsBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    accounts: Annotated[
        list[AnnotationBody], Field(min_length=1, max_length=500), classified("confidential")
    ]
    reason: Annotated[str | None, Field(max_length=500), classified("confidential")] = None


def _snapshot(c: Candidate) -> SnapshotOut:
    s = c.snapshot
    return SnapshotOut(
        id=s.id,
        period_start=s.period_start,
        period_end=s.period_end,
        source=s.source,
        pulled_at=s.pulled_at,
        line_count=s.line_count,
        total_debit=s.total_debit,
        total_credit=s.total_credit,
        lines_changed=c.lines_changed,
        net_change=c.net_change,
    )


def _totals(t: Totals) -> TotalsOut:
    return TotalsOut(debit=t.debit, credit=t.credit, difference=t.difference, balanced=t.balanced)


def _sheet(s: Leadsheet) -> LeadsheetOut:
    return LeadsheetOut(
        area=s.area,
        rows=[LeadRowOut.model_validate(r, from_attributes=True) for r in s.rows],
        py=s.py,
        cy=s.cy,
        change=s.change,
        change_pct=s.change_pct,
    )


async def _detail(
    ctx: AuthContext, engagement_id: UUID, tb_id: UUID, version: int | None, layer: str
) -> TrialBalanceDetailOut:
    found = await view(ctx, engagement_id, tb_id, version, layer)
    v, names = found.view, found.names

    def version_out(x: VersionInfo) -> TbVersionOut:
        return TbVersionOut(
            version_no=x.version_no,
            snapshot_id=x.snapshot_id,
            prior_snapshot_id=x.prior_snapshot_id,
            adopted_by_name=names.get(x.adopted_by, "Former member"),
            reason=x.reason,
            adopted_at=x.adopted_at,
            source=x.source,
            pulled_at=x.pulled_at,
        )

    return TrialBalanceDetailOut(
        trial_balance=TrialBalanceOut.model_validate(v.summary, from_attributes=True),
        version=version_out(v.version),
        versions=[version_out(x) for x in v.versions],
        lines=[TbLineOut.model_validate(line, from_attributes=True) for line in v.lines],
        eoy=_totals(v.eoy),
        boy=None if v.boy is None else _totals(v.boy),
    )


@router.get("", action="trial_balance.read", response_model=TrialBalancesOut)
async def trial_balances_route(engagement_id: UUID, ctx: Ctx) -> TrialBalancesOut:
    """SPEC-309 AC-1: the engagement's trial balances and the snapshots to adopt from."""
    found = await overview(ctx, engagement_id)
    return TrialBalancesOut(
        trial_balances=[
            TrialBalanceOut.model_validate(t, from_attributes=True) for t in found.trial_balances
        ],
        snapshots=[_snapshot(c) for c in found.snapshots],
    )


@router.post(
    "", action="trial_balance.adopt", response_model=TrialBalanceDetailOut, status_code=201
)
async def adopt_trial_balance_route(
    engagement_id: UUID, body: AdoptBody, ctx: Ctx
) -> TrialBalanceDetailOut:
    """SPEC-309 AC-1: adopt a snapshot as the trial balance of record (version 1)."""
    tb_id = await adopt(
        ctx, engagement_id, body.snapshot_id, body.prior_snapshot_id, body.label, body.display_unit
    )
    return await _detail(ctx, engagement_id, tb_id, None, "unadjusted")


@router.get("/{tb_id}", action="trial_balance.read", response_model=TrialBalanceDetailOut)
async def trial_balance_route(
    engagement_id: UUID,
    tb_id: UUID,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
    layer: Layer = "unadjusted",
) -> TrialBalanceDetailOut:
    """SPEC-309 AC-2, AC-4: a version's lines, totals and balance."""
    return await _detail(ctx, engagement_id, tb_id, version, layer)


@router.get("/{tb_id}/candidates", action="trial_balance.read", response_model=list[SnapshotOut])
async def tb_candidates_route(engagement_id: UUID, tb_id: UUID, ctx: Ctx) -> list[SnapshotOut]:
    """SPEC-309 AC-7: snapshots with the difference from the current version."""
    return [_snapshot(c) for c in await newer(ctx, engagement_id, tb_id)]


@router.post(
    "/{tb_id}/versions",
    action="trial_balance.adopt",
    response_model=TrialBalanceDetailOut,
    status_code=201,
)
async def adopt_tb_version_route(
    engagement_id: UUID, tb_id: UUID, body: VersionBody, ctx: Ctx
) -> TrialBalanceDetailOut:
    """SPEC-309 AC-7: adopt a newer snapshot as the next version."""
    await new_version(
        ctx,
        engagement_id,
        tb_id,
        body.snapshot_id,
        body.prior_snapshot_id,
        body.reason,
        body.seen_version,
    )
    return await _detail(ctx, engagement_id, tb_id, None, "unadjusted")


@router.get("/{tb_id}/leadsheets", action="trial_balance.read", response_model=list[LeadsheetOut])
async def leadsheets_route(
    engagement_id: UUID,
    tb_id: UUID,
    ctx: Ctx,
    version: Annotated[int | None, Query(ge=1)] = None,
) -> list[LeadsheetOut]:
    """SPEC-309 AC-5: leadsheets by audit area (PY, CY, Δ, Δ%)."""
    return [_sheet(s) for s in await sheets(ctx, engagement_id, tb_id, version)]


@router.post(
    "/{tb_id}/annotations",
    action="trial_balance.annotate",
    response_model=TrialBalanceDetailOut,
    status_code=201,
)
async def annotate_tb_route(
    engagement_id: UUID, tb_id: UUID, body: AnnotationsBody, ctx: Ctx
) -> TrialBalanceDetailOut:
    """SPEC-309 AC-6: set accounts' audit areas and working-paper references."""
    edits = [AnnotationEdit(a.account_code, a.area, a.wp_ref) for a in body.accounts]
    await set_annotations(ctx, engagement_id, tb_id, edits, body.reason)
    return await _detail(ctx, engagement_id, tb_id, None, "unadjusted")
