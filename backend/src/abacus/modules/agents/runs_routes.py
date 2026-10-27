"""Agent run list, trace and trace export (P-09; SPEC-318; TASK-461). Read-only over runs:
nothing here lets anyone act on a proposal (ADR-005). `model_text` is untrusted model text:
render it through AgentText."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.agents.blocks import AgentBlocks
from abacus.modules.agents.run_records import RunRecord, record_for
from abacus.modules.agents.runs import (
    RunItems,
    RunSummary,
    RunWrite,
    Trace,
    export_trace,
    items_for,
    records_read_for,
    run_view,
    runs_for,
    trace_for,
    writes_for,
)
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
    # C6 v1 (Q-02-T45; ADR-169 §4).
    # Optional with defaults: additive to v0, so v0 readers and fixtures stay valid.
    state_reason: Annotated[str | None, classified("internal")] = None
    outcome: Annotated[
        Literal["approved", "partially_approved", "rejected"] | None, classified("internal")
    ] = None
    stage: Annotated[Literal["shadow", "live"], classified("internal")] = "live"
    record_sha256: Annotated[str | None, classified("internal")] = None
    record_persisted_at: Annotated[datetime | None, classified("internal")] = None


class TraceRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    kind: Annotated[
        Literal["start", "queued", "attempt", "output", "decision", "finish"],
        classified("internal"),
    ]
    title: Annotated[str, classified("internal")]
    state: Annotated[Literal["done", "failed", "waiting", "running"], classified("internal")]
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

    run: Annotated[AgentRunOut, classified("internal")]
    runtime: Annotated[str, classified("internal")]
    region: Annotated[str, classified("internal")]
    training: Annotated[str, classified("internal")]
    attempts: Annotated[int, classified("internal")]
    tokens_in: Annotated[int, classified("internal")]
    tokens_out: Annotated[int, classified("internal")]
    rows: Annotated[list[TraceRowOut], classified("internal")]
    records_read: Annotated[list[RecordsReadOut], classified("internal")]
    output_counts: Annotated[list[OutputCountOut], classified("internal")]
    model_text: Annotated[str | None, classified("confidential")]
    # DEC-87: "metadata" drops the content (model text, record references, narration).
    projection: Annotated[Literal["content", "metadata"], classified("internal")]


class RunViewOut(BaseModel):
    """C6 v1 (TASK-5000): one run, its record fingerprint and what the caller may do."""

    model_config = ConfigDict(frozen=True)

    run: Annotated[AgentRunOut, classified("internal")]
    run_record_sha256: Annotated[str, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    projection: Annotated[Literal["content", "metadata"], classified("internal")]


class RunWriteOut(BaseModel):
    """What the run proposed to write and what a person decided. Codes and references only."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["suggestion", "proposal", "screening"], classified("internal")]
    id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str | None, classified("internal")]
    target_id: Annotated[UUID | None, classified("internal")]
    key: Annotated[str, classified("internal")]
    # The row's own status code (a suggestion's, a proposal's or pending/decided).
    outcome: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    decision: Annotated[str | None, classified("internal")]
    decided_by_name: Annotated[str | None, classified("internal")]
    decided_at: Annotated[datetime | None, classified("internal")]


class RunItemOut(BaseModel):
    """A thread item: code words and references only (P-09 Story 8.1); the client words it."""

    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, classified("internal")]
    kind: Annotated[
        Literal["tool_card", "narration", "decision", "failure"], classified("internal")
    ]
    at: Annotated[datetime, classified("internal")]
    code: Annotated[str, classified("internal")]
    # The row's own code: mixed objects, so not one status vocabulary (codes only).
    outcome: Annotated[str | None, classified("internal")]
    detail: Annotated[str | None, classified("internal")]
    actor: Annotated[str | None, classified("internal")]
    ref_type: Annotated[str | None, classified("internal")]
    ref_id: Annotated[UUID | None, classified("internal")]
    # AgentBlocks v1 (P-09-T03): agent-authored content, validated on the server; render only
    # through the client's AgentBlocks. Null on pre-v2 runs.
    blocks: Annotated[AgentBlocks | None, classified("confidential")] = None


class RunItemsOut(BaseModel):
    """The run header plus the items after `after_seq` (P-09 Story 1.3 polling)."""

    model_config = ConfigDict(frozen=True)

    run: Annotated[AgentRunOut, classified("internal")]
    items: Annotated[list[RunItemOut], classified("internal")]
    last_seq: Annotated[int, classified("internal")]
    resync: Annotated[bool, classified("internal")]


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


# --- The run record (Q-02-T41; ADR-169 §3 and §4) --------------------------------------------


class RecordRefOut(BaseModel):
    """A record the run read, or a citation points into: its type and id (null in metadata)."""

    model_config = ConfigDict(frozen=True)

    type: Annotated[str, classified("internal")]
    id: Annotated[UUID | None, classified("internal")]


class CitationLocatorOut(BaseModel):
    """Where a citation points: positions and codes, never the quoted words."""

    model_config = ConfigDict(frozen=True)

    document: Annotated[str | None, classified("internal")] = None
    claim: Annotated[str | None, classified("internal")] = None
    page: Annotated[int | None, classified("internal")] = None
    cell: Annotated[str | None, classified("internal")] = None


class RecordCitationOut(BaseModel):
    """A citation of the run's output: its locator, code's verdict and fingerprints only."""

    model_config = ConfigDict(frozen=True)

    source: Annotated[str, classified("internal")]
    record: Annotated[RecordRefOut | None, classified("internal")]
    locator: Annotated[CitationLocatorOut, classified("internal")]
    # HMAC-SHA-256 of the quoted words and of the sheet name under the firm's fingerprint key
    # (DEC-396): never the words; null for readers who may not read unmasked content.
    quote_fingerprint: Annotated[str | None, classified("confidential")]
    sheet_fingerprint: Annotated[str | None, classified("confidential")]
    verified: Annotated[bool | None, classified("internal")] = None
    reason: Annotated[str | None, classified("internal")] = None
    amount_matches: Annotated[bool | None, classified("internal")] = None


class RecordInputHashesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    context: Annotated[str | None, classified("internal")]
    model_calls: Annotated[list[str], classified("internal")]


class RecordOutcomeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Annotated[
        Literal["succeeded", "needs_input", "failed", "cancelled"], classified("internal")
    ]
    failure_code: Annotated[str | None, classified("internal")]
    outputs: Annotated[dict[str, int], classified("internal")]


class RunRecordOut(BaseModel):
    """ADR-169 §3: the run's durable record as stored. Content-free by construction:
    identifiers, versions and fingerprints. `record_sha256` is SHA-256 of the canonical JSON
    (sorted keys, UTC instants) of every stored field but `persisted_at`, citations' keyed
    fingerprints included; it is the record's own hash, not the run view's `run_record_sha256`
    (DEC-396)."""

    model_config = ConfigDict(frozen=True)

    run_id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    capability: Annotated[str, classified("internal")]
    spec_version: Annotated[int, classified("internal")]
    stage: Annotated[Literal["shadow", "live"], classified("internal")]
    prompt_ref: Annotated[str | None, classified("internal")]
    prompt_sha256: Annotated[str | None, classified("internal")]
    model: Annotated[str | None, classified("internal")]
    route: Annotated[str | None, classified("internal")]
    region: Annotated[str | None, classified("internal")]
    terms_version: Annotated[str | None, classified("internal")]
    boundary_basis: Annotated[str | None, classified("internal")]
    input_hashes: Annotated[RecordInputHashesOut, classified("internal")]
    records_read: Annotated[list[RecordRefOut], classified("internal")]
    citations: Annotated[list[RecordCitationOut], classified("internal")]
    outcome: Annotated[RecordOutcomeOut, classified("internal")]
    initiator_user_id: Annotated[UUID, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    completed_at: Annotated[datetime, classified("internal")]
    # SHA-256 of the canonical JSON of the stored fields (not `persisted_at`); citations enter it
    # with their keyed fingerprints (HMAC-SHA-256 under the firm's key), never the quoted words.
    record_sha256: Annotated[str, classified("internal")]
    persisted_at: Annotated[datetime, classified("internal")]
    projection: Annotated[Literal["content", "metadata"], classified("internal")]
    # Entries naming a withdrawn evidence version, left out of this read (P-06-T19); when it is
    # not zero the shown fields no longer hash to `record_sha256`.
    withheld: Annotated[int, classified("internal")]


def _record(found: RunRecord) -> RunRecordOut:
    return RunRecordOut.model_validate(found, from_attributes=True)


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
        projection=trace.projection,
    )


@engagement_runs_router.get(
    "/agent-runs", action="agent_run.read", response_model=list[AgentRunOut]
)
async def list_agent_runs_route(
    engagement_id: UUID, ctx: Ctx, state: Literal["active", "recent"] = "recent", limit: int = 25
) -> list[AgentRunOut]:
    return [_run(r) for r in await runs_for(ctx, engagement_id, state, limit)]


@runs_router.get("/{run_id}", action="agent_run.read", response_model=RunViewOut)
async def agent_run_route(run_id: UUID, ctx: Ctx) -> RunViewOut:
    view = await run_view(ctx, run_id)
    return RunViewOut(
        run=_run(view.run),
        run_record_sha256=view.run_record_sha256,
        allowed_actions=view.allowed_actions,
        projection=view.projection,
    )


def _items(found: RunItems) -> RunItemsOut:
    return RunItemsOut(
        run=_run(found.run),
        items=[RunItemOut.model_validate(i, from_attributes=True) for i in found.items],
        last_seq=found.last_seq,
        resync=found.resync,
    )


@runs_router.get("/{run_id}/record", action="agent_run.read", response_model=RunRecordOut)
async def agent_run_record_route(run_id: UUID, ctx: Ctx) -> RunRecordOut:
    return _record(await record_for(ctx, run_id))


@runs_router.get("/{run_id}/items", action="agent_run.read", response_model=RunItemsOut)
async def agent_run_items_route(
    run_id: UUID, ctx: Ctx, after_seq: Annotated[int, Query(ge=0)] = 0
) -> RunItemsOut:
    return _items(await items_for(ctx, run_id, after_seq))


@runs_router.get(
    "/{run_id}/trace/records-read", action="agent_run.read", response_model=list[RecordsReadOut]
)
async def agent_run_records_read_route(run_id: UUID, ctx: Ctx) -> list[RecordsReadOut]:
    return [
        RecordsReadOut.model_validate(r, from_attributes=True)
        for r in await records_read_for(ctx, run_id)
    ]


def _write(w: RunWrite) -> RunWriteOut:
    return RunWriteOut.model_validate(w, from_attributes=True)


@runs_router.get(
    "/{run_id}/trace/writes", action="agent_run.read", response_model=list[RunWriteOut]
)
async def agent_run_writes_route(run_id: UUID, ctx: Ctx) -> list[RunWriteOut]:
    return [_write(w) for w in await writes_for(ctx, run_id)]


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
