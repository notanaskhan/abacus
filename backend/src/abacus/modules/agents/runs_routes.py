"""Agent run list, trace and trace export (P-09; SPEC-318; TASK-461). Read-only over runs:
nothing here lets anyone act on a proposal (ADR-005). `model_text` is untrusted model text:
render it through AgentText.

C6 v1.1 (P-09-T01; TASK-6201; DEC-2801) is additive: the run header and projection by level, the
`access` field, the v2 item kinds on the feed, trace phases, marks and durations, the trace
summary, records-read connections, proposed-write approvers and the step detail route. Fields a
handler cannot fill yet answer null or empty until P-09-T07 (run view, feed), P-09-T08 (trace)
and P-10-T29 (v2 fields) fill them; the step detail answers 404 while `run_trace.enabled` is off
and 501 until P-09-T08. Every count is code's (ADR-050)."""

from __future__ import annotations

import base64
import time
from datetime import datetime
from typing import Annotated, Literal, cast, get_args
from uuid import UUID

from fastapi import Depends, Path, Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from abacus.kernel._flags import RUN_TRACE_ENABLED
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.metrics import meter
from abacus.modules.agents.blocks import AgentBlocks
from abacus.modules.agents.run_records import RunRecord, record_for
from abacus.modules.agents.runs import (
    LEGACY_PHASE,
    RunHeader,
    RunItem,
    RunItems,
    RunSummary,
    RunWrite,
    Trace,
    TraceRow,
    export_trace,
    items_for,
    records_read_for,
    run_view,
    runs_for,
    step_detail,
    trace_for,
    writes_for,
)
from abacus.modules.agents.runs_v2_contract import (
    BlockedOnOut,
    RunCountersOut,
    RunStateV2,
    TriggerKind,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

TRIGGER_KINDS: frozenset[str] = frozenset(get_args(TriggerKind))

engagement_runs_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["agents"])
runs_router = AbacusRouter(prefix="/v1/agent-runs", tags=["agents"])
Ctx = Annotated[AuthContext, Depends(current_context)]
RunState = Literal["queued", "running", "succeeded", "needs_input", "failed"]
Access = Literal["content", "metadata"]
# C6 v1.1: the v2 wire set of session items (P-09 §4.3), so the dock renders one grammar for v1
# and v2 runs. A legacy run's synthesised items map onto it (`tool_card` → tool, `narration` →
# line, `decision` → decision_ref, `failure` → error).
SessionItemKind = Literal[
    "user",
    "line",
    "block",
    "tool",
    "progress",
    "question",
    "answer",
    "error",
    "plan",
    "approval",
    "decision_ref",
    "artifact",
    "run_card",
    "notice",
]
LEGACY_SESSION_KIND: dict[str, SessionItemKind] = {
    "tool_card": "tool",
    "narration": "line",
    "decision": "decision_ref",
    "failure": "error",
}
# WB-09's timeline grammar: what a row is (phase) and the mark drawn on the rail.
TracePhase = Literal[
    "plan", "execute", "compute", "proposed_write", "decision", "policy", "steer", "notice"
]
TraceMark = Literal["start", "plan", "done", "running", "waiting", "blocked", "failed", "muted"]
WriteState = Literal["waiting", "approved", "declined", "superseded"]


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
    # A v2 run's rows (P-09-T08, additive): `plan` for the plan decision, `step` for a step row.
    kind: Annotated[
        Literal["start", "queued", "attempt", "output", "decision", "finish", "plan", "step"],
        classified("internal"),
    ]
    title: Annotated[str, classified("internal")]
    state: Annotated[Literal["done", "failed", "waiting", "running"], classified("internal")]
    detail: Annotated[str | None, classified("internal")]
    actor: Annotated[str | None, classified("internal")]
    # C6 v1.1 (P-09-T01): WB-09's phase and mark, and the step's own duration. Null on v1 rows
    # until P-09-T08 maps them.
    phase: Annotated[TracePhase | None, classified("internal")] = None
    mark: Annotated[TraceMark | None, classified("internal")] = None
    duration_ms: Annotated[int | None, Field(ge=0), classified("internal")] = None
    # P-09-T10 (additive): a v2 step row's id, for its detail (the trace step detail route).
    step_id: Annotated[UUID | None, classified("internal")] = None


class RecordsReadOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: Annotated[str, classified("internal")]
    count: Annotated[int, classified("internal")]
    # C6 v1.1: "Through" on WB-09's Records read tab: the firm connection a source was read
    # through (`connection_id`), or null for Accrued's own records.
    connection_id: Annotated[UUID | None, classified("internal")] = None
    through: Annotated[str | None, classified("internal")] = None


class OutputCountOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[str, classified("internal")]
    count: Annotated[int, classified("internal")]


class TraceSummaryOut(BaseModel):
    """C6 v1.1: WB-09's summary card. Every figure is code's: #4118 reads 2,625 records, 79
    citations, 0 writes done and 1 waiting, over 2 m 41 s."""

    model_config = ConfigDict(frozen=True)

    run_number: Annotated[int | None, classified("internal")] = None
    agent_label: Annotated[str, classified("internal")]
    started_at: Annotated[datetime, classified("internal")]
    trigger_kind: Annotated[TriggerKind | None, classified("internal")] = None
    runs_as_name: Annotated[str | None, classified("internal")] = None
    duration_ms: Annotated[int | None, Field(ge=0), classified("internal")] = None
    records_read: Annotated[int, Field(ge=0), classified("internal")] = 0
    citations: Annotated[int, Field(ge=0), classified("internal")] = 0
    writes_done: Annotated[int, Field(ge=0), classified("internal")] = 0
    writes_waiting: Annotated[int, Field(ge=0), classified("internal")] = 0


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
    # C6 v1.1: the summary card and the access the caller holds (the same value as projection).
    summary: Annotated[TraceSummaryOut | None, classified("internal")] = None
    access: Annotated[Access | None, classified("internal")] = None


class RunProjectionLevelOut(BaseModel):
    """C6 v1.1: one level of the run's plan, counted by code from its steps and never stored
    ("Run projection", glossary). `total` is the sum of the six states."""

    model_config = ConfigDict(frozen=True)

    level: Annotated[int, Field(ge=1), classified("internal")]
    total: Annotated[int, Field(ge=0), classified("internal")]
    done: Annotated[int, Field(ge=0), classified("internal")] = 0
    running: Annotated[int, Field(ge=0), classified("internal")] = 0
    blocked: Annotated[int, Field(ge=0), classified("internal")] = 0
    waiting: Annotated[int, Field(ge=0), classified("internal")] = 0
    queued: Annotated[int, Field(ge=0), classified("internal")] = 0
    failed: Annotated[int, Field(ge=0), classified("internal")] = 0


class PlanStepRefOut(BaseModel):
    """One step of the run's newest plan version, for "Change order…" (DEC-3142)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]


class RunHeaderOut(BaseModel):
    """C6 v1.1: the dock's header: the run number, what it is blocked on, code's counters, who it
    runs as and what started it. Null fields wait for P-10-T29's v2 columns."""

    model_config = ConfigDict(frozen=True)

    run_number: Annotated[int | None, classified("internal")] = None
    blocked_on: Annotated[BlockedOnOut | None, classified("internal")] = None
    counters: Annotated[RunCountersOut | None, classified("internal")] = None
    runs_as_name: Annotated[str | None, classified("internal")] = None
    trigger_kind: Annotated[TriggerKind | None, classified("internal")] = None
    work_item_ref: Annotated[str | None, classified("internal")] = None
    plan_version: Annotated[int | None, classified("internal")] = None  # P-09-T14
    plan_steps: Annotated[list[PlanStepRefOut], classified("internal")] = []  # DEC-3142
    # P-10-T29: the v2 state (C2's 14 codes) and its reason code; null for a legacy run.
    state: Annotated[RunStateV2 | None, classified("internal")] = None
    state_reason: Annotated[str | None, classified("internal")] = None


class RunViewOut(BaseModel):
    """C6 v1 (TASK-5000): one run, its record fingerprint and what the caller may do."""

    model_config = ConfigDict(frozen=True)

    run: Annotated[AgentRunOut, classified("internal")]
    run_record_sha256: Annotated[str, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    projection: Annotated[Literal["content", "metadata"], classified("internal")]
    # C6 v1.1 (P-09-T01): the header, the projection by level (P-09-T07 computes it), and
    # `access`, the same value as `projection` under the name the dock and drawer read.
    header: Annotated[RunHeaderOut | None, classified("internal")] = None
    levels: Annotated[list[RunProjectionLevelOut], classified("internal")] = Field(
        default_factory=list[RunProjectionLevelOut]
    )
    access: Annotated[Access | None, classified("internal")] = None


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
    # C6 v1.1: WB-09's Writes & approvals row: its state, who it waits on, and the proposal it
    # belongs to. Null until P-09-T08 reads the proposal's approver.
    state: Annotated[WriteState | None, classified("internal")] = None
    approver_name: Annotated[str | None, classified("internal")] = None
    proposal_id: Annotated[UUID | None, classified("internal")] = None


class RunItemOut(BaseModel):
    """A thread item: code words and references only (P-09 Story 8.1); the client words it."""

    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, classified("internal")]
    # Legacy kinds, then (C6 v1.1, P-09-T07, additive) the v2 wire set a v2 run's items carry.
    kind: Annotated[
        Literal[
            "tool_card", "narration", "decision", "failure",
            "user", "line", "block", "tool", "progress", "question", "answer", "error", "plan",
            "approval", "decision_ref", "artifact", "run_card", "notice",
        ],
        classified("internal"),
    ]  # fmt: skip
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
    # C6 v1.1: the item in the v2 wire set, so one renderer serves v1 and v2 runs.
    session_kind: Annotated[SessionItemKind | None, classified("internal")] = None


class RunItemsOut(BaseModel):
    """The run header plus the items after `after_seq` (P-09 Story 1.3 polling)."""

    model_config = ConfigDict(frozen=True)

    run: Annotated[AgentRunOut, classified("internal")]
    items: Annotated[list[RunItemOut], classified("internal")]
    last_seq: Annotated[int, classified("internal")]
    resync: Annotated[bool, classified("internal")]
    # C6 v1.1: the cursor to poll with next (`after_seq=next_seq`), the same value as last_seq.
    next_seq: Annotated[int | None, Field(ge=0), classified("internal")] = None


class TraceSampleOut(BaseModel):
    """One of up to five records a tool step read, visible to the caller, with its open route."""

    model_config = ConfigDict(frozen=True)

    record_type: Annotated[str, classified("internal")]
    id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]
    open_route: Annotated[str, classified("internal")]


class TraceStepOut(BaseModel):
    """C6 v1.1: a tool row expanded (WB-09a2): its argument summary and up to five sample records
    it read, filtered by `visible()`. Content only (DEC-87)."""

    model_config = ConfigDict(frozen=True)

    step_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("internal")]
    args_summary: Annotated[str | None, classified("confidential")]
    records_read: Annotated[int, Field(ge=0), classified("internal")]
    samples: Annotated[list[TraceSampleOut], Field(max_length=5), classified("internal")]


class TraceExportIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # TASK-7825 (DEC-4820): `pdf` is C11's run_export rendering of the same JSON body.
    format: Annotated[Literal["json", "pdf"], classified("internal")] = "json"


class TraceExportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: Annotated[str, classified("internal")]
    content: Annotated[str, classified("confidential")]
    sha256: Annotated[str, classified("internal")]
    rows: Annotated[int, classified("internal")]
    renderer_version: Annotated[str, classified("internal")]
    # P-09-T11 (DEC-3118): the signed manifest's additions.
    run_record_sha256: Annotated[str | None, classified("internal")] = None
    signature: Annotated[str | None, classified("internal")] = None
    signature_key_id: Annotated[str | None, classified("internal")] = None
    # TASK-7825 (DEC-4820): JSON is UTF-8 text; a PDF's bytes are base64. `source_sha256` names the
    # JSON body a PDF was drawn from (null for JSON, whose `sha256` is its own).
    media_type: Annotated[
        Literal["application/json", "application/pdf"], classified("internal")
    ] = "application/json"
    content_encoding: Annotated[Literal["utf-8", "base64"], classified("internal")] = "utf-8"
    source_sha256: Annotated[str | None, classified("internal")] = None


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


# P-09-T20: the dashboards' two signals (RB-69). A poll is one `items` read, labelled by whether
# it brought anything new and the run's state; the trace latency is the trace read's server time.
_meter = meter(__name__)
_polls = _meter.create_counter(
    "abacus.agent_run.items_polls", description="Run feed polls (GET /v1/agent-runs/{id}/items)"
)
_trace_seconds = _meter.create_histogram(
    "abacus.agent_run.trace_latency", unit="s", description="Run trace read time (WB-09)"
)


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
        rows=_rows(trace),
        records_read=[
            RecordsReadOut.model_validate(r, from_attributes=True) for r in trace.records_read
        ],
        output_counts=[OutputCountOut(kind=k, count=n) for k, n in trace.output_counts],
        model_text=trace.model_text,
        projection=trace.projection,
        summary=_trace_summary(trace),
        access=trace.projection,
    )


def _legacy_row(r: TraceRow) -> TraceRowOut:
    phase, mark = LEGACY_PHASE[r.kind]
    if r.state == "failed":
        mark = "failed"
    elif r.state == "waiting" and r.kind == "finish":
        mark = "waiting"
    return TraceRowOut.model_validate(r, from_attributes=True).model_copy(
        update={"phase": phase, "mark": mark}
    )


def _rows(trace: Trace) -> list[TraceRowOut]:
    """A v2 run's timeline from its durable records; a legacy run's rows with phase and mark."""
    if not trace.v2_rows:
        return [_legacy_row(r) for r in trace.rows]
    return [
        TraceRowOut(
            seq=r.seq,
            at=r.at,
            kind="plan" if r.phase == "plan" else "step",
            title=r.title,
            state=r.state,
            detail=r.detail,
            actor=r.actor,
            phase=r.phase,
            mark=r.mark,
            duration_ms=r.duration_ms,
            step_id=r.step_id if r.phase in ("execute", "compute") else None,
        )
        for r in trace.v2_rows
    ]


def _trace_summary(trace: Trace) -> TraceSummaryOut | None:
    s = trace.summary
    if s is None:
        return None
    trigger = s.trigger_kind if s.trigger_kind in TRIGGER_KINDS else None
    return TraceSummaryOut(
        run_number=s.run_number,
        agent_label=s.agent_label,
        started_at=s.started_at,
        trigger_kind=cast(TriggerKind | None, trigger),
        runs_as_name=s.runs_as_name,
        duration_ms=s.duration_ms,
        records_read=s.records_read,
        citations=s.citations,
        writes_done=s.writes_done,
        writes_waiting=s.writes_waiting,
    )


@engagement_runs_router.get(
    "/agent-runs", action="agent_run.read", response_model=list[AgentRunOut]
)
async def list_agent_runs_route(
    engagement_id: UUID, ctx: Ctx, state: Literal["active", "recent"] = "recent", limit: int = 25
) -> list[AgentRunOut]:
    return [_run(r) for r in await runs_for(ctx, engagement_id, state, limit)]


def _header(header: RunHeader | None) -> RunHeaderOut | None:
    if header is None:
        return None
    blocked = (
        BlockedOnOut.model_validate(header.blocked_on) if header.blocked_on is not None else None
    )
    counters = (
        RunCountersOut.model_validate(header.counters, from_attributes=True)
        if header.counters is not None
        else None
    )
    trigger = header.trigger_kind if header.trigger_kind in TRIGGER_KINDS else None
    return RunHeaderOut(
        run_number=header.run_number,
        blocked_on=blocked,
        counters=counters,
        runs_as_name=header.runs_as_name,
        trigger_kind=cast(TriggerKind | None, trigger),
        work_item_ref=header.work_item_ref,
        plan_version=header.plan_version,
        plan_steps=[PlanStepRefOut(key=k, label=label) for k, label in header.plan_steps],
        state=cast("RunStateV2 | None", header.state),  # agent_runs.state CHECK holds the 14 codes
        state_reason=header.state_reason,
    )


@runs_router.get("/{run_id}", action="agent_run.read", response_model=RunViewOut)
async def agent_run_route(run_id: UUID, ctx: Ctx) -> RunViewOut:
    view = await run_view(ctx, run_id)
    return RunViewOut(
        run=_run(view.run),
        run_record_sha256=view.run_record_sha256,
        allowed_actions=view.allowed_actions,
        projection=view.projection,
        access=view.projection,
        header=_header(view.header),
        levels=[
            RunProjectionLevelOut.model_validate(lv, from_attributes=True) for lv in view.levels
        ],
    )


def _blocks(raw: dict[str, object] | None) -> AgentBlocks | None:
    """A v2 item's stored blocks, validated again on the way out; invalid ones are dropped
    (the dock shows the item without them rather than unvalidated content)."""
    if raw is None:
        return None
    try:
        return AgentBlocks.model_validate(raw)
    except ValidationError:
        return None


def _item(i: RunItem) -> RunItemOut:
    session_kind = LEGACY_SESSION_KIND.get(i.kind, cast(SessionItemKind, i.kind))
    return RunItemOut(
        seq=i.seq,
        kind=i.kind,
        at=i.at,
        code=i.code,
        outcome=i.outcome,
        detail=i.detail,
        actor=i.actor,
        ref_type=i.ref_type,
        ref_id=i.ref_id,
        blocks=_blocks(i.blocks),
        session_kind=session_kind,
    )


def _items(found: RunItems) -> RunItemsOut:
    return RunItemsOut(
        run=_run(found.run),
        items=[_item(i) for i in found.items],
        last_seq=found.last_seq,
        resync=found.resync,
        next_seq=found.last_seq,
    )


@runs_router.get("/{run_id}/record", action="agent_run.read", response_model=RunRecordOut)
async def agent_run_record_route(run_id: UUID, ctx: Ctx) -> RunRecordOut:
    return _record(await record_for(ctx, run_id))


@runs_router.get("/{run_id}/items", action="agent_run.read", response_model=RunItemsOut)
async def agent_run_items_route(
    run_id: UUID, ctx: Ctx, after_seq: Annotated[int, Query(ge=0)] = 0
) -> RunItemsOut:
    found = _items(await items_for(ctx, run_id, after_seq))
    _polls.add(1, {"state": found.run.state, "empty": not found.items})
    return found


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


@runs_router.get(
    "/{run_id}/trace/steps/{step_id}", action="agent_run.read", response_model=TraceStepOut
)
async def agent_run_trace_step_route(
    run_id: UUID,
    step_id: Annotated[UUID, Path()],
    ctx: Ctx,
    records: Annotated[int, Query(ge=0, le=5)] = 5,
) -> TraceStepOut:
    """WB-09 a2 (P-09-T08): 404 while `run_trace.enabled` is off. The run is authorised first, so
    no one learns the flag's state for a run they may not read; content only."""
    await run_view(ctx, run_id)
    if not await flag_enabled(ctx.tenant, RUN_TRACE_ENABLED):
        raise NotFound(RUN_TRACE_ENABLED.name)
    found = await step_detail(ctx, run_id, step_id, records)
    return TraceStepOut(
        step_id=found.step_id,
        title=found.title,
        args_summary=found.args_summary,
        records_read=found.records_read,
        samples=[TraceSampleOut.model_validate(x, from_attributes=True) for x in found.samples],
    )


@runs_router.get("/{run_id}/trace", action="agent_run.read", response_model=RunTraceOut)
async def agent_run_trace_route(run_id: UUID, ctx: Ctx) -> RunTraceOut:
    started = time.perf_counter()
    try:
        return _trace(await trace_for(ctx, run_id))
    finally:
        _trace_seconds.record(time.perf_counter() - started)


@runs_router.post(
    "/{run_id}/trace-exports",
    action="run_trace.export",
    response_model=TraceExportOut,
    status_code=201,
)
async def export_run_trace_route(run_id: UUID, body: TraceExportIn, ctx: Ctx) -> TraceExportOut:
    exported = await export_trace(ctx, run_id, body.format)
    pdf = body.format == "pdf"
    return TraceExportOut(
        filename=f"run-trace-{run_id}.{body.format}",
        content=base64.b64encode(exported.trace).decode() if pdf else exported.trace.decode(),
        media_type="application/pdf" if pdf else "application/json",
        content_encoding="base64" if pdf else "utf-8",
        source_sha256=str(exported.manifest["source_sha256"]) if pdf else None,
        sha256=str(exported.manifest["sha256"]),
        rows=int(str(exported.manifest["rows"])),
        renderer_version=str(exported.manifest["renderer_version"]),
        run_record_sha256=str(exported.manifest["run_record_sha256"]),
        signature=str(exported.manifest["signature"]),
        signature_key_id=str(exported.manifest["signature_key_id"]),
    )
