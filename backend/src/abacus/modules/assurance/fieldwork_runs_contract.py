"""Fieldwork run rows (A-08-T24; DEC-5403): AUD-13 / AUD-26 Run and AUD-14 Reconcile, plus the
polling fallback for C6 v2's progress. Contract: `docs/contracts/audit-analytics.md` §4b and
`docs/contracts/confirmations.md` (run rows). One action each: client 404; the record's flag;
the service authorises on the record's engagement; `audits.fieldwork_agents` off 404; a closed
data boundary 409 `drafting_not_enabled` (DF-04) with no run recorded.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDITS_ANALYTICS, AUDITS_CONFIRMATIONS
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.agents.api import RunStateV2
from abacus.modules.assurance import fieldwork_runs as svc
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
RowKind = Literal[
    "fieldwork_attribute", "flux_explain", "tie_out", "client_questions", "confirmation_reconcile"
]


class RunStateCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Annotated[RunStateV2, classified("internal")]
    runs: Annotated[int, Field(ge=0), classified("internal")]


class RunRowOut(BaseModel):
    """One run row: "Simone Baptiste via Agent" for an agent row, "Code" for a code row."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[RowKind, classified("internal")]
    label: Annotated[str, classified("public")]
    run_ids: Annotated[list[UUID], classified("internal")]
    items: Annotated[int, Field(ge=0), classified("internal")]
    states: Annotated[list[RunStateCountOut], classified("internal")]
    attribution: Annotated[str, classified("confidential")]
    tb_balanced: Annotated[bool | None, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]


class RunRowsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: Annotated[list[RunRowOut], classified("internal")]


router = AbacusRouter(prefix="/v1", tags=["fieldwork-runs"])


async def _gate(ctx: AuthContext, flag: Flag) -> None:
    if ctx.client:
        raise NotFound("run")
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


def _out(rows: list[svc.RunRow]) -> RunRowsOut:
    return RunRowsOut(
        rows=[
            RunRowOut(
                kind=r.kind,
                label=r.label,
                run_ids=list(r.run_ids),
                items=r.items,
                states=[
                    RunStateCountOut(state=cast("RunStateV2", k), runs=v)
                    for k, v in sorted(r.states.items())
                ],
                attribution=r.attribution,
                tb_balanced=(
                    bool(r.code_result.get("tb_balanced"))
                    if r.code_result is not None and "tb_balanced" in r.code_result
                    else None
                ),
                started_at=r.started_at,
            )
            for r in rows
        ]
    )


@router.post(
    "/analytics-sets/{analytics_set_id}/runs",
    action="analytics.explain",
    response_model=RunRowsOut,
    status_code=202,
    errors=(409,),
)
async def start_analytics_runs(
    analytics_set_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> RunRowsOut:
    await _gate(ctx, AUDITS_ANALYTICS)
    return _out(await svc.run_analytics(ctx, analytics_set_id, _key))


@router.get(
    "/analytics-sets/{analytics_set_id}/runs", action="analytics.read", response_model=RunRowsOut
)
async def analytics_run_rows(analytics_set_id: UUID, ctx: Ctx) -> RunRowsOut:
    """The polling fallback while the SSE stream is unavailable."""
    await _gate(ctx, AUDITS_ANALYTICS)
    from abacus.modules.assurance import analytics

    await analytics.set_view(ctx, analytics_set_id)  # authorises analytics.read
    return _out(await svc.run_rows(ctx, analytics_set_id))


@router.post(
    "/confirmations/{confirmation_id}/runs",
    action="confirmation.read",
    response_model=RunRowsOut,
    status_code=202,
    errors=(409,),
)
async def start_reconcile_run(confirmation_id: UUID, ctx: Ctx, _key: IdempotencyKey) -> RunRowsOut:
    await _gate(ctx, AUDITS_CONFIRMATIONS)
    return _out(await svc.run_reconcile(ctx, confirmation_id, _key))
