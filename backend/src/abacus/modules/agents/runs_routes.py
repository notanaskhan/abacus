"""Agent run list, trace and trace export (P-09; SPEC-318; TASK-461). Read-only over runs:
nothing here lets anyone act on a proposal (ADR-005). `model_text` is untrusted model text:
render it through AgentText."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.agents.runs import RunSummary, Trace, export_trace, runs_for, trace_for
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

engagement_runs_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["agents"])
runs_router = AbacusRouter(prefix="/v1/agent-runs", tags=["agents"])
Ctx = Annotated[AuthContext, Depends(current_context)]
RunState = Literal["queued", "running", "succeeded", "needs_input", "failed"]


class AgentRunOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    agent: Annotated[str, classified("internal")]
    agent_label: Annotated[str, classified("internal")]
    state: Annotated[RunState, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    finished_at: Annotated[datetime | None, classified("internal")]
    duration_ms: Annotated[int | None, classified("internal")]
    initiator_name: Annotated[str, classified("internal")]
    subject: Annotated[str | None, classified("internal")]


class TraceRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    kind: Annotated[
        Literal["start", "queued", "attempt", "output", "decision", "finish"],
        classified("internal"),
    ]
    title: Annotated[str, classified("internal")]
    state: Annotated[
        Literal["done", "failed", "waiting", "running", "info"], classified("internal")
    ]
    detail: Annotated[str | None, classified("internal")]
    actor: Annotated[str | None, classified("internal")]


class RecordsReadOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: Annotated[str, classified("internal")]
    count: Annotated[int, classified("internal")]


class OutputCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[str, classified("internal")]
    count: Annotated[int, classified("internal")]


class RunTraceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    run: AgentRunOut
    runtime: Annotated[str, classified("internal")]
    region: Annotated[str, classified("internal")]
    training: Annotated[str, classified("internal")]
    attempts: Annotated[int, classified("internal")]
    tokens_in: Annotated[int, classified("internal")]
    tokens_out: Annotated[int, classified("internal")]
    rows: list[TraceRowOut]
    records_read: list[RecordsReadOut]
    output_counts: list[OutputCountOut]
    model_text: Annotated[str | None, classified("confidential")]


class TraceExportIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    format: Annotated[Literal["json"], classified("internal")] = "json"


class TraceExportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: Annotated[str, classified("internal")]
    content: Annotated[str, classified("confidential")]
    sha256: Annotated[str, classified("internal")]
    rows: Annotated[int, classified("internal")]
    renderer_version: Annotated[str, classified("internal")]


def _run(run: RunSummary) -> AgentRunOut:
    return AgentRunOut.model_validate(run, from_attributes=True)


def _trace(trace: Trace) -> RunTraceOut:
    return RunTraceOut(
        run=_run(trace.run),
        runtime=trace.runtime,
        region=trace.region,
        training=trace.training,
        attempts=trace.attempts,
        tokens_in=trace.tokens_in,
        tokens_out=trace.tokens_out,
        rows=[TraceRowOut.model_validate(r, from_attributes=True) for r in trace.rows],
        records_read=[
            RecordsReadOut.model_validate(r, from_attributes=True) for r in trace.records_read
        ],
        output_counts=[OutputCountOut(kind=k, count=n) for k, n in trace.output_counts],
        model_text=trace.model_text,
    )


@engagement_runs_router.get(
    "/agent-runs", action="agent_run.read", response_model=list[AgentRunOut]
)
async def list_agent_runs_route(
    engagement_id: UUID, ctx: Ctx, state: Literal["active", "recent"] = "recent", limit: int = 25
) -> list[AgentRunOut]:
    return [_run(r) for r in await runs_for(ctx, engagement_id, state, limit)]


@runs_router.get("/{run_id}/trace", action="agent_run.read", response_model=RunTraceOut)
async def agent_run_trace_route(run_id: UUID, ctx: Ctx) -> RunTraceOut:
    return _trace(await trace_for(ctx, run_id))


@runs_router.post(
    "/{run_id}/trace-exports",
    action="run_trace.export",
    response_model=TraceExportOut,
    status_code=201,
)
async def export_run_trace_route(run_id: UUID, body: TraceExportIn, ctx: Ctx) -> TraceExportOut:
    del body  # JSON is the only format in this slice
    exported = await export_trace(ctx, run_id)
    return TraceExportOut(
        filename=f"run-trace-{run_id}.json",
        content=exported.trace.decode(),
        sha256=str(exported.manifest["sha256"]),
        rows=int(str(exported.manifest["rows"])),
        renderer_version=str(exported.manifest["renderer_version"]),
    )
