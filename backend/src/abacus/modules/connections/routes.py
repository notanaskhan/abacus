"""Retrieval routes (SPEC-000 §8; TASK-010 design §7, Q4). PROTECTED."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel.classification import classified
from abacus.modules.connections.connect import (
    ConnectionView,
    access_log,
    check,
    complete,
    connection_of,
    providers,
    revoke,
    start,
)
from abacus.modules.connections.connector import Period
from abacus.modules.connections.retrievals import trigger_retrieval
from abacus.modules.connections.service import RetrievalView, retrieval_status
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/retrievals", tags=["retrievals"])
Status = Literal["running", "succeeded", "failed_validation", "failed", "queued"]


class RetrievalIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    request_item_id: Annotated[UUID, classified("internal")]
    period_start: Annotated[date, classified("confidential")]
    period_end: Annotated[date, classified("confidential")]

    @model_validator(mode="after")
    def _period(self) -> RetrievalIn:
        if self.period_end < self.period_start:
            raise ValueError("period_end must not be before period_start")
        return self


class RetrievalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    sync_run_id: Annotated[UUID, classified("internal")]
    request_item_id: Annotated[UUID, classified("internal")]
    status: Annotated[Status, classified("internal")]
    failure_code: Annotated[str | None, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    finished_at: Annotated[datetime | None, classified("internal")]
    # SPEC-003 AC-13: why a queued run waits (`firm_cap`, `engagement_cap`, `class_capacity`) and
    # when it is expected to start (None when unknown). Never names another firm.
    queued_reason: Annotated[str | None, classified("internal")]
    estimated_start_at: Annotated[datetime | None, classified("internal")]


def _out(view: RetrievalView) -> RetrievalOut:
    return RetrievalOut.model_validate(
        {**asdict(view), "status": view.reported_status}, from_attributes=False
    )


Ctx = Annotated[AuthContext, Depends(current_context)]


@router.post(
    "",
    action="evidence.upload",
    response_model=RetrievalOut,
    status_code=202,
    errors=(409, 503),
)
async def start_retrieval_route(engagement_id: UUID, body: RetrievalIn, ctx: Ctx) -> RetrievalOut:
    view = await trigger_retrieval(
        ctx,
        engagement_id=engagement_id,
        request_item_id=body.request_item_id,
        period=Period(body.period_start, body.period_end),
    )
    return _out(view)


@router.get("/{sync_run_id}", action="request_item.read", response_model=RetrievalOut)
async def get_retrieval_route(engagement_id: UUID, sync_run_id: UUID, ctx: Ctx) -> RetrievalOut:
    return _out(await retrieval_status(ctx, engagement_id=engagement_id, run_id=sync_run_id))


# --- The connection flow (SPEC-020; TASK-036) --------------------------------------------------

connection_router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/connection", tags=["connection"]
)
complete_router = AbacusRouter(prefix="/v1/connections", tags=["connection"])
ConnectionStatus = Literal["active", "needs_attention"]
RunStatus = Literal["running", "succeeded", "failed_validation", "failed"]


class ProviderOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: Annotated[str, classified("internal")]
    name: Annotated[str, classified("internal")]
    datasets: Annotated[list[str], classified("internal")]


class StartIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: Annotated[str, Field(min_length=1, max_length=50), classified("internal")]


class StartOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    authorise_url: Annotated[str, classified("internal")]


class CompleteIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    state: Annotated[str, Field(min_length=1, max_length=200), classified("restricted")]
    code: Annotated[str, Field(min_length=1, max_length=2000), classified("restricted")]


class CompleteOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]


class ConnectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    provider: Annotated[str, classified("internal")]
    status: Annotated[ConnectionStatus, classified("internal")]
    scopes: Annotated[list[str], classified("internal")]
    created_by: Annotated[str, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    expires_at: Annotated[datetime | None, classified("internal")]
    last_checked_at: Annotated[datetime | None, classified("internal")]
    last_check_ok: Annotated[bool | None, classified("internal")]
    last_pull_at: Annotated[datetime | None, classified("internal")]


class LogEntryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    dataset: Annotated[str, classified("internal")]
    period_start: Annotated[date, classified("confidential")]
    period_end: Annotated[date, classified("confidential")]
    status: Annotated[RunStatus, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    finished_at: Annotated[datetime | None, classified("internal")]
    started_by: Annotated[str, classified("internal")]


def _connection_out(view: ConnectionView) -> ConnectionOut:
    return ConnectionOut.model_validate({**asdict(view), "scopes": list(view.scopes)})


@connection_router.get(
    "/providers", action="connection.read_log", response_model=list[ProviderOut]
)
async def providers_route(engagement_id: UUID, ctx: Ctx) -> list[ProviderOut]:
    """SPEC-020 Q1: what can be connected here (the demo ledger only outside production)."""
    return [
        ProviderOut(provider=p.provider, name=p.name, datasets=list(p.datasets))
        for p in await providers(ctx, engagement_id)
    ]


@connection_router.post(
    "/start", action="connection.create", response_model=StartOut, errors=(409,)
)
async def start_route(engagement_id: UUID, body: StartIn, ctx: Ctx) -> StartOut:
    """SPEC-020 AC-2, AC-3: a client admin, signed in recently, starts connecting."""
    started = await start(ctx, engagement_id, body.provider)
    return StartOut(authorise_url=started.authorise_url)


@complete_router.post(
    "/complete",
    action="connection.create",
    response_model=CompleteOut,
    status_code=201,
    errors=(409,),
)
async def complete_route(body: CompleteIn, ctx: Ctx) -> CompleteOut:
    """SPEC-020 AC-2 (TASK-036 D1): the SPA hands back the provider's state and code."""
    return CompleteOut(engagement_id=await complete(ctx, body.state, body.code))


@connection_router.get("", action="connection.read_log", response_model=ConnectionOut | None)
async def connection_route(engagement_id: UUID, ctx: Ctx) -> ConnectionOut | None:
    """SPEC-020 AC-4: the live connection and its health, or null."""
    view = await connection_of(ctx, engagement_id)
    return None if view is None else _connection_out(view)


@connection_router.post(
    "/check", action="connection.check", response_model=ConnectionOut, errors=(409,)
)
async def check_route(engagement_id: UUID, ctx: Ctx) -> ConnectionOut:
    """SPEC-020 AC-4: ask the provider now."""
    return _connection_out(await check(ctx, engagement_id))


@connection_router.post(
    "/revoke", action="connection.revoke", response_model=CompleteOut, errors=(409,)
)
async def revoke_route(engagement_id: UUID, ctx: Ctx) -> CompleteOut:
    """SPEC-020 AC-6: end the connection; pulls stop at once."""
    await revoke(ctx, engagement_id)
    return CompleteOut(engagement_id=engagement_id)


@connection_router.get("/log", action="connection.read_log", response_model=list[LogEntryOut])
async def log_route(
    engagement_id: UUID, ctx: Ctx, page: Annotated[int, Query(ge=0, le=10_000)] = 0
) -> list[LogEntryOut]:
    """SPEC-020 AC-5: every pull, newest first."""
    return [
        LogEntryOut.model_validate(asdict(entry))
        for entry in await access_log(ctx, engagement_id, page)
    ]
