"""Agent run transparency v1: the run list and the run trace (P-09; SPEC-318; TASK-461).

Read-only over the runs that exist: the run row, the gateway's recorded attempts, the run's
output and the people's decisions on it. Every summary figure (duration, attempts, counts) is
computed from the rows, never stored for display. Model text appears only as `model_text`, for
the browser to render through AgentText (ADR-065); the model id is never shown, only the
runtime label. Shadow runs are never shown (SPEC-036). Firm-level runs stay out of this slice.
An export is deterministic canonical JSON with a SHA-256 manifest, and is audited.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.ai_gateway import attempts_for
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.tin_patterns import scrub_tins
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.models import AgentActivity, AgentRun, AgentRunRecord, Proposal
from abacus.modules.agents.repository import (
    RunWriteRow,
    engagement_runs,
    get_run,
    run_activity,
    run_writes,
    screening_results_of_run,
)
from abacus.modules.agents.run_views import (
    Counters,
    LevelCount,
    V2Facts,
    levels_for,
    v2_facts,
    v2_items,
)
from abacus.modules.agents.run_views import V2Item as V2ItemT
from abacus.modules.agents.trace import (
    Sample,
    SourceCount,
    V2TraceRow,
    args_summary_text,
    plan_of,
    records_read_by_source,
    region_of,
    samples_for,
    step_of,
    steps_of,
    timeline,
)
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import decisions_on_screenings, withdrawn_among
from abacus.modules.identity.api import (
    AuthContext,
    allowed_actions,
    authorise,
    engagement_team,
    refuse_unmasked_read,
)

# DEC-87: the trace names the runtime and region, never the model family.
RUNTIME_LABEL: Final = "Accrued Agent runtime"
REGION: Final = "United States (data and inference)"
TRAINING: Final = "Firm data is never used for training"
RENDERER_VERSION: Final = "trace-v1"
AGENT_LABEL: Final = {
    "evidence.screener": "Evidence screener",
    "evidence.upload_reviewer": "Upload reviewer",
    "evidence.matcher": "Inbox matcher",
    "requests.guidance_drafter": "Guidance drafter",
    "fieldwork.entry_assessor": "Entry assessor",
    "engagement.agent": "Engagement agent",
    "reporting.fs_draft": "Statements draft",
}
State = Literal["queued", "running", "succeeded", "needs_input", "failed"]
# DEC-87 (TASK-5002): content for the engagement's people and oversight in scope; metadata for
# everyone else agent_run.read lets in (security and firm admins): what ran, never the content.
Projection = Literal["content", "metadata"]
# ADR-169 §1: derived, never stored, once every proposal of the run is decided.
Outcome = Literal["approved", "partially_approved", "rejected"]
Stage = Literal["shadow", "live"]
# The C6 v1 summary fields the trace-v1 export leaves out, so its bytes stay as they were.
_V1_SUMMARY_FIELDS: Final = (
    "state_reason",
    "outcome",
    "stage",
    "record_sha256",
    "record_persisted_at",
)
RowKind = Literal["start", "queued", "attempt", "output", "decision", "finish"]
_V11_TRACE_FIELDS: Final = ("summary", "v2_rows", "sources")
# C6 v1.1 (P-09-T08): a legacy row's WB-09 phase and mark.
LEGACY_PHASE: Final[dict[str, tuple[str, str]]] = {
    "start": ("notice", "start"),
    "queued": ("notice", "waiting"),
    "attempt": ("execute", "done"),
    "output": ("proposed_write", "done"),
    "decision": ("decision", "done"),
    "finish": ("notice", "done"),
}


@dataclass(frozen=True)
class RunSummary:
    id: UUID
    agent: str
    agent_label: str
    state: State
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    initiator_name: str
    subject: str | None  # what the run worked on, as a reference kind
    # C6 v1 (Q-02-T45; ADR-169 §4): the canonical state's reason, the outcome derived from the
    # decisions on the run's proposals, the stage, and the durable record's fingerprint and when
    # it was written (null until persisted). Not part of the trace-v1 export (`canonical`).
    state_reason: str | None = None
    outcome: Outcome | None = None
    stage: Stage = "live"
    record_sha256: str | None = None
    record_persisted_at: datetime | None = None


@dataclass(frozen=True)
class TraceRow:
    seq: int
    at: datetime
    kind: RowKind
    title: str
    state: Literal["done", "failed", "waiting", "running"]
    detail: str | None  # code words only
    actor: str | None


@dataclass(frozen=True)
class RecordsRead:
    source: str
    count: int
    # C6 v1.1 (P-09-T08): the firm connection the records came through, or "Accrued".
    connection_id: UUID | None = None
    through: str | None = None


@dataclass(frozen=True)
class Trace:
    run: RunSummary
    runtime: str
    region: str
    training: str
    attempts: int
    tokens_in: int
    tokens_out: int
    rows: list[TraceRow]
    records_read: list[RecordsRead]
    output_counts: list[tuple[str, int]]
    model_text: str | None  # the run's own words, rendered through AgentText
    projection: Projection = "content"
    # C6 v1.1 (P-09-T08): WB-09's summary card, and a v2 run's timeline from its durable records.
    summary: TraceSummary | None = None
    v2_rows: tuple[V2TraceRow, ...] = ()
    sources: tuple[SourceCount, ...] = ()


@dataclass(frozen=True)
class TraceSummary:
    run_number: int | None
    agent_label: str
    started_at: datetime
    trigger_kind: str | None
    runs_as_name: str | None
    duration_ms: int | None
    records_read: int
    citations: int
    writes_done: int
    writes_waiting: int


def state_of(run: AgentRun) -> State:
    if run.status == "running":
        return "queued" if run.queued_reason else "running"
    return {"completed": "succeeded", "escalated": "needs_input"}.get(run.status, "failed")  # type: ignore[return-value]  # the four statuses


def duration_ms(start: datetime, end: datetime | None) -> int | None:
    return None if end is None else int((end - start).total_seconds() * 1000)


def _subject(run: AgentRun) -> str | None:
    if run.evidence_version_id is not None:
        return "evidence_version"
    if run.inbox_file_id is not None:
        return "inbox_file"
    if run.methodology_version_id is not None:
        return "template_version"
    return None


def written_counts(writes: Sequence[RunWriteRow]) -> list[tuple[str, int]]:
    """How many suggestions and proposals the run recorded (migration 0095), when it did."""
    counts: dict[str, int] = {}
    for w in writes:
        counts[w.kind + "s"] = counts.get(w.kind + "s", 0) + 1
    return sorted(counts.items())


def output_counts(output: dict[str, object] | None) -> list[tuple[str, int]]:
    """How many of each thing the run proposed, from its structured output (lists only)."""
    if not output:
        return []
    counts: list[tuple[str, int]] = []
    for key, value in output.items():
        if isinstance(value, list):
            items: list[object] = value  # pyright: ignore[reportUnknownVariableType] -- JSONB
            counts.append((key, len(items)))
    return sorted(counts)


def state_reason_of(run: AgentRun) -> str | None:
    """ADR-169 §2's legacy map: the queued reason while queued, `escalated` for needs_input."""
    state = state_of(run)
    if state == "queued":
        return run.queued_reason
    return "escalated" if state == "needs_input" else None


def outcome_of(states: Sequence[str]) -> Outcome | None:
    """ADR-169 §1: approved, partially approved or rejected once every live proposal is decided;
    null while one is pending or when the run proposed nothing (superseded ones don't count)."""
    live = [s for s in states if s != "superseded"]
    if not live or "pending" in live:
        return None
    approved = sum(1 for s in live if s in ("approved", "approved_with_edits"))
    if approved == len(live):
        return "approved"
    return "rejected" if approved == 0 else "partially_approved"


@dataclass(frozen=True)
class _V1Facts:
    record: AgentRunRecord | None
    proposal_states: tuple[str, ...]


async def _v1_facts(session: AsyncSession, run_ids: Sequence[UUID]) -> dict[UUID, _V1Facts]:
    """Each run's persisted record and its proposals' states, in two reads (RLS-scoped)."""
    if not run_ids:
        return {}
    records = {
        r.run_id: r
        for r in (
            await session.scalars(select(AgentRunRecord).where(AgentRunRecord.run_id.in_(run_ids)))
        ).all()
    }
    states: dict[UUID, list[str]] = {}
    for run_id, state in (
        await session.execute(
            select(Proposal.agent_run_id, Proposal.state).where(Proposal.agent_run_id.in_(run_ids))
        )
    ).all():
        states.setdefault(run_id, []).append(state)
    return {i: _V1Facts(records.get(i), tuple(states.get(i, ()))) for i in run_ids}


def _summary(run: AgentRun, names: dict[UUID, str], facts: _V1Facts | None = None) -> RunSummary:
    record = facts.record if facts is not None else None
    stage: Stage = "shadow" if run.shadow else "live"
    if record is not None and record.stage in ("shadow", "live"):
        stage = record.stage
    return RunSummary(
        run.id,
        run.agent_id,
        AGENT_LABEL.get(run.agent_id, run.agent_id),
        state_of(run),
        run.started_at,
        run.finished_at,
        duration_ms(run.started_at, run.finished_at),
        names.get(run.initiator_user_id, "Former member"),
        _subject(run),
        state_reason_of(run),
        outcome_of(facts.proposal_states) if facts is not None else None,
        stage,
        record.record_sha256 if record is not None else None,
        record.persisted_at if record is not None else None,
    )


async def _summary_v1(ctx: AuthContext, run: AgentRun, names: dict[UUID, str]) -> RunSummary:
    async with tenant_session(ctx.tenant) as session:
        facts = await _v1_facts(session, [run.id])
    return _summary(run, names, facts.get(run.id))


async def runs_for(
    ctx: AuthContext, engagement_id: UUID, state: Literal["active", "recent"], limit: int
) -> list[RunSummary]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "agent_run.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        runs = await engagement_runs(session, ctx, engagement_id, max(1, min(limit, 100)))
    if state == "active":
        async with tenant_session(ctx.tenant) as session:
            facts = await v2_facts(session, [r.id for r in runs])
        # A v2 run is active until its state is terminal; a legacy one while it runs.
        runs = [
            r
            for r in runs
            if (r.id in facts and facts[r.id].v2 and facts[r.id].active)
            or (not (r.id in facts and facts[r.id].v2) and r.status == "running")
        ]
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    async with tenant_session(ctx.tenant) as session:
        facts = await _v1_facts(session, [r.id for r in runs])
    return [_summary(r, names, facts.get(r.id)) for r in runs]


async def run_initiators(
    ctx: AuthContext, engagement_id: UUID, run_ids: Sequence[UUID]
) -> dict[UUID, str]:
    """The person each run acted for, by run id ("Marcus Delaney"), for "<person> via Agent"
    attribution on records an agent wrote (INV-5). Runs off the engagement are left out."""
    if not run_ids:
        return {}
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(AgentRun.id, AgentRun.initiator_user_id).where(
                    AgentRun.id.in_(list(run_ids)), AgentRun.engagement_id == engagement_id
                )
            )
        ).all()
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    return {run_id: names.get(user_id, "Former member") for run_id, user_id in rows}


async def _run(ctx: AuthContext, run_id: UUID, action: str) -> AgentRun:
    async with tenant_session(ctx.tenant) as session:
        run = await get_run(session, run_id)
    if run is None or run.shadow or run.engagement_id is None:
        raise NotFound
    ref = await get_ref(ctx, run.engagement_id)
    await authorise(ctx, action, ref.resource())
    return run


async def authorised_run(ctx: AuthContext, run_id: UUID) -> AgentRun:
    """The run, authorised `agent_run.read` on its engagement, for the run record read
    (Q-02-T41): unknown, shadow and firm-level runs answer 404, as every C6 read does."""
    return await _run(ctx, run_id, "agent_run.read")


async def projection_for(ctx: AuthContext, engagement_id: UUID) -> Projection:
    """Content when the matrix grants `run_content.read` on the engagement, else metadata."""
    ref = await get_ref(ctx, engagement_id)
    found = await allowed_actions(ctx, ref.resource(), ["run_content.read"])
    return "content" if "run_content.read" in found else "metadata"


async def trace_for(ctx: AuthContext, run_id: UUID) -> Trace:
    run = await _run(ctx, run_id, "agent_run.read")
    # DEC-52 (TASK-1207): a trace carries the model's text; its export, built from this, too.
    await refuse_unmasked_read(ctx, "agent_run.read")
    engagement_id = run.engagement_id
    if engagement_id is None:  # _run refuses firm-level runs
        raise NotFound
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    projection = await projection_for(ctx, engagement_id)
    attempts = await attempts_for(ctx.tenant, run.id)
    async with tenant_session(ctx.tenant) as session:
        results = await screening_results_of_run(session, run.id)
    hidden = await withdrawn_among(ctx.tenant, [r.evidence_version_id for r in results])
    results = [r for r in results if r.evidence_version_id not in hidden]  # P-06-T19
    decisions = await decisions_on_screenings(ctx.tenant, [r.id for r in results])
    rows: list[TraceRow] = [
        TraceRow(
            0,
            run.started_at,
            "start",
            "Run started",
            "done",
            "event" if run.source_event_id is not None else "requested",
            names.get(run.initiator_user_id, "Former member"),
        )
    ]
    if run.queued_reason:
        rows.append(
            TraceRow(
                0,
                run.started_at,
                "queued",
                "Waiting for a slot",
                "waiting",
                run.queued_reason,
                None,
            )
        )
    for a in attempts:
        rows.append(
            TraceRow(
                0,
                a.at,
                "attempt",
                "Model call",
                "done" if a.outcome == "ok" else "failed",
                a.outcome,
                None,
            )
        )
    async with tenant_session(ctx.tenant) as session:
        writes = await run_writes(session, run.id)
    counts = written_counts(writes) or output_counts(run.output)
    model_text: str | None = None
    for r in results:
        model_text = r.rationale
        rows.append(
            TraceRow(
                0,
                r.created_at,
                "output",
                "Proposed " + r.action.replace("_", " "),
                "done",
                f"{len(r.citations)} citations, {len(r.unverified)} unverified claims",
                None,
            )
        )
    if not results and counts:
        rows.append(
            TraceRow(
                0,
                run.finished_at or run.started_at,
                "output",
                "Proposed",
                "done",
                ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in counts),
                None,
            )
        )
    for d in decisions:
        actor = names.get(UUID(d.actor_id), "Former member") if d.actor_kind == "human" else None
        rows.append(TraceRow(0, d.at, "decision", f"Decided: {d.decision}", "done", None, actor))
    for w in writes:  # people's decisions on the run's suggestions and proposals (ADR-161)
        if w.decision is not None and w.decided_at is not None and w.decided_by is not None:
            rows.append(
                TraceRow(
                    0,
                    w.decided_at,
                    "decision",
                    f"Decided: {w.decision.replace('_', ' ')}",
                    "done",
                    w.kind,
                    names.get(w.decided_by, "Former member"),
                )
            )
    if run.finished_at is not None:
        state = state_of(run)
        rows.append(
            TraceRow(
                0,
                run.finished_at,
                "finish",
                {"succeeded": "Finished", "needs_input": "Needs a person", "failed": "Failed"}.get(
                    state, "Finished"
                ),
                "failed" if state == "failed" else "waiting" if state == "needs_input" else "done",
                run.failure_code,
                None,
            )
        )
    ordered = sorted(
        rows,
        key=lambda r: (
            r.at,
            ["start", "queued", "attempt", "output", "finish", "decision"].index(r.kind),
        ),
    )
    rows = [
        TraceRow(i + 1, r.at, r.kind, r.title, r.state, r.detail, r.actor)
        for i, r in enumerate(ordered)
    ]
    read = records_read_of(run)
    metadata = projection == "metadata"
    async with tenant_session(ctx.tenant) as session:
        facts = (await v2_facts(session, [run.id])).get(run.id)
        is_v2 = facts is not None and facts.v2
        plan = await plan_of(session, run.id) if is_v2 else None
        steps = await steps_of(session, run.id) if is_v2 else []
    v2_rows: tuple[V2TraceRow, ...] = ()
    sources: tuple[SourceCount, ...] = ()
    region = REGION
    if is_v2 and facts is not None:
        role = facts.blocked_on.get("role") if facts.blocked_on else None
        v2_rows = tuple(
            timeline(
                plan,
                steps,
                names,
                metadata=metadata,
                blocked_role=role if isinstance(role, str) else None,
            )
        )
        sources = tuple(records_read_by_source(steps))
        read = [RecordsRead(c.source, c.count, c.connection_id, c.through) for c in sources]
        region = region_of(await _route_of(ctx, run.id), run.started_at)
    summary = _trace_summary(run, names, facts, sources)
    return Trace(
        _summary(run, names),
        RUNTIME_LABEL,
        region,
        TRAINING,
        len(attempts),
        sum(a.input_tokens for a in attempts),
        sum(a.output_tokens for a in attempts),
        rows,
        read,
        counts,
        scrub_tins(model_text) if projection == "content" and model_text else None,
        projection,
        summary,
        v2_rows,
        sources,
    )


_ROUTE = text("SELECT route FROM agent_runs WHERE id = :run")


async def _route_of(ctx: AuthContext, run_id: UUID) -> str | None:
    async with tenant_session(ctx.tenant) as session:
        return cast(str | None, (await session.execute(_ROUTE, {"run": run_id})).scalar())


def _trace_summary(
    run: AgentRun,
    names: dict[UUID, str],
    facts: V2Facts | None,
    sources: Sequence[SourceCount],
) -> TraceSummary:
    """WB-09's summary card: code's counts. A legacy run counts what its record holds."""
    counters = facts.counters if facts is not None and facts.v2 else Counters()
    runs_as = facts.runs_as_user_id if facts is not None else None
    records = sum(c.count for c in sources) if sources else counters.records_read
    end = run.finished_at
    return TraceSummary(
        facts.run_number if facts is not None else None,
        AGENT_LABEL.get(run.agent_id, run.agent_id),
        run.started_at,
        facts.trigger_kind if facts is not None else None,
        None if runs_as is None else names.get(runs_as, "Former member"),
        duration_ms(run.started_at, end),
        records,
        counters.citations_count,
        counters.writes_done,
        counters.writes_waiting,
    )


def _plain(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return {str(k): _plain(v) for k, v in mapping.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in cast("Sequence[object]", value)]
    return value


def canonical(trace: Trace) -> bytes:
    """Sorted keys, UTC instants, rows in seq order: the same trace gives the same bytes."""
    plain = asdict(trace)
    for key in _V1_SUMMARY_FIELDS:
        plain["run"].pop(key, None)
    # P-09-T08's v1.1 fields stay out of trace-v1's bytes; P-09-T11's export version carries them.
    for key in _V11_TRACE_FIELDS:
        plain.pop(key, None)
    for row in plain["records_read"]:
        row.pop("connection_id", None)
        row.pop("through", None)
    return json.dumps(_plain(plain), sort_keys=True, separators=(",", ":")).encode()


@dataclass(frozen=True)
class TraceExport:
    trace: bytes
    manifest: dict[str, object]


async def export_trace(ctx: AuthContext, run_id: UUID) -> TraceExport:
    trace = await trace_for(ctx, run_id)
    await _run(ctx, run_id, "run_trace.export")
    body = canonical(trace)
    digest = hashlib.sha256(body).hexdigest()
    async with uow(ctx.tenant) as tx:
        tx.record(
            "agent_run.trace_exported",
            target=Target("agent_run", run_id),
            after=Ref(sha256=digest, rows=len(trace.rows)),
        )
    return TraceExport(
        body,
        {
            "run_id": str(run_id),
            "rows": len(trace.rows),
            "sha256": digest,
            "renderer_version": RENDERER_VERSION,
            # P-09-T01 (DEC-2801): the export inherits the caller's projection, so an admin's
            # export is the metadata trace and says so.
            "projection": trace.projection,
        },
    )


# --- C6 v1 (TASK-5000): the run, its records read and its writes ---------------------------


@dataclass(frozen=True)
class RunHeader:
    """C6 v1.1's header (P-09-T07): from the v2 columns; names from the engagement team."""

    run_number: int | None
    blocked_on: dict[str, object] | None
    counters: Counters | None
    runs_as_name: str | None
    trigger_kind: str | None
    work_item_ref: str | None


@dataclass(frozen=True)
class RunView:
    run: RunSummary
    run_record_sha256: str
    allowed_actions: list[str]
    projection: Projection
    header: RunHeader | None = None
    levels: tuple[LevelCount, ...] = ()


# What the dock may offer on a run: P-10's policy decides, and the view passes the caller's
# allowed set through (P-09-T07). The commands answer 404 until P-10's routes land (P-09-T14).
RUN_ACTIONS: Final = (
    "agent_run.read",
    "run_trace.export",
    "agent_run.approve_plan",
    "agent_run.answer",
    "agent_run.control",
    "agent_run.sign_off",
)


def _header(facts: V2Facts, names: dict[UUID, str], metadata: bool) -> RunHeader:
    runs_as = facts.runs_as_user_id
    blocked = facts.blocked_on
    if metadata and blocked is not None:  # DEC-87: no record references or needs
        blocked = {"kind": blocked.get("kind"), "role": blocked.get("role")}
    return RunHeader(
        facts.run_number,
        blocked,
        facts.counters if facts.v2 else None,
        None if runs_as is None else names.get(runs_as, "Former member"),
        facts.trigger_kind,
        None if metadata else facts.work_item_ref,
    )


@dataclass(frozen=True)
class RunWrite:
    kind: Literal["suggestion", "proposal", "screening"]
    id: UUID
    target_type: str | None
    target_id: UUID | None
    key: str  # a code: the field key, the proposal kind or the screening action
    outcome: str
    at: datetime
    decision: str | None
    decided_by_name: str | None
    decided_at: datetime | None
    # C6 v1.1 (P-09-T08): WB-09 a4's state, the person it waits on, and its proposal.
    state: WriteState | None = None
    approver_name: str | None = None
    proposal_id: UUID | None = None


WriteState = Literal["waiting", "approved", "declined", "superseded"]
# A suggestion's, proposal's or screening's own state, as WB-09 a4 words it (DEC-3005).
WRITE_STATE: Final[dict[str, WriteState]] = {
    "pending": "waiting",
    "proposed": "waiting",
    "open": "waiting",
    "approved": "approved",
    "approved_with_edits": "approved",
    "accepted": "approved",
    "applied": "approved",
    "decided": "approved",
    "rejected": "declined",
    "declined": "declined",
    "dismissed": "declined",
    "superseded": "superseded",
    "withdrawn": "superseded",
}
_ROUTED = text("SELECT id, routed_to_user_id FROM proposals WHERE agent_run_id = :run")


def run_record_sha256(run: AgentRun) -> str:
    """A fingerprint of the run's own record, so a consumer can tell it changed."""
    record = {
        "id": run.id,
        "agent_id": run.agent_id,
        "spec_version": run.spec_version,
        "engagement_id": run.engagement_id,
        "evidence_version_id": run.evidence_version_id,
        "inbox_file_id": run.inbox_file_id,
        "methodology_version_id": run.methodology_version_id,
        "status": run.status,
        "context_hash": run.context_hash,
        "failure_code": run.failure_code,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "output": run.output,
    }
    body = json.dumps(_plain(record), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(body).hexdigest()


async def run_view(ctx: AuthContext, run_id: UUID) -> RunView:
    run = await _run(ctx, run_id, "agent_run.read")
    engagement_id = run.engagement_id
    if engagement_id is None:  # _run refuses firm-level runs
        raise NotFound
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    ref = await get_ref(ctx, engagement_id)
    actions = await allowed_actions(ctx, ref.resource(), list(RUN_ACTIONS))
    projection = await projection_for(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        facts = (await v2_facts(session, [run.id])).get(run.id)
        levels = await levels_for(session, facts) if facts is not None and facts.v2 else []
    header = None if facts is None else _header(facts, names, projection == "metadata")
    return RunView(
        await _summary_v1(ctx, run, names),
        run_record_sha256(run),
        sorted(actions),
        projection,
        header,
        tuple(levels),
    )


def records_read_of(run: AgentRun) -> list[RecordsRead]:
    read: list[RecordsRead] = []
    subject = _subject(run)
    if subject is not None:
        read.append(RecordsRead(subject, 1))
    if run.task_scope:
        read.append(RecordsRead("task_scope", len(run.task_scope)))
    return read


async def records_read_for(ctx: AuthContext, run_id: UUID) -> list[RecordsRead]:
    """A v2 run's reads by record type and source, summed from its steps; a legacy run's from
    its own row."""
    run = await _run(ctx, run_id, "agent_run.read")
    async with tenant_session(ctx.tenant) as session:
        facts = (await v2_facts(session, [run.id])).get(run.id)
        steps = await steps_of(session, run.id) if facts is not None and facts.v2 else None
    if steps is None:
        return records_read_of(run)
    return [
        RecordsRead(c.source, c.count, c.connection_id, c.through)
        for c in records_read_by_source(steps)
    ]


@dataclass(frozen=True)
class TraceStep:
    step_id: UUID
    title: str
    args_summary: str | None
    records_read: int
    samples: tuple[Sample, ...]


async def step_detail(ctx: AuthContext, run_id: UUID, step_id: UUID, records: int) -> TraceStep:
    """WB-09 a2: one tool row's redacted arguments and up to five sample records the caller may
    open. Content only: a metadata reader, or a step of another run, gets 404 (DEC-87)."""
    run = await _run(ctx, run_id, "agent_run.read")
    engagement_id = run.engagement_id
    if engagement_id is None or await projection_for(ctx, engagement_id) == "metadata":
        raise NotFound
    async with tenant_session(ctx.tenant) as session:
        step = await step_of(session, run.id, step_id)
        plan = await plan_of(session, run.id)
    if step is None:
        raise NotFound
    rows = timeline(plan, [step], {}, metadata=False)
    samples = await samples_for(ctx, step.sample_refs, records)
    return TraceStep(
        step.id,
        rows[-1].title,
        args_summary_text(step.args_summary),
        step.records_read,
        tuple(samples),
    )


async def writes_for(ctx: AuthContext, run_id: UUID) -> list[RunWrite]:
    """What the run proposed to write, and what people decided: suggestions, proposals and
    screening results. Codes and references only; the model's words stay on the trace."""
    run = await _run(ctx, run_id, "agent_run.read")
    engagement_id = run.engagement_id
    if engagement_id is None:
        raise NotFound
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    async with tenant_session(ctx.tenant) as session:
        writes = await run_writes(session, run.id)
        results = await screening_results_of_run(session, run.id)
    hidden = await withdrawn_among(ctx.tenant, [r.evidence_version_id for r in results])
    results = [r for r in results if r.evidence_version_id not in hidden]  # P-06-T19
    decided = {
        d.screening_result_id: d
        for d in await decisions_on_screenings(ctx.tenant, [r.id for r in results])
    }
    out = [
        RunWrite(
            "suggestion" if w.kind == "suggestion" else "proposal",
            w.id,
            w.target_type,
            w.target_id,
            w.key,
            w.state,
            w.at,
            w.decision,
            None if w.decided_by is None else names.get(w.decided_by, "Former member"),
            w.decided_at,
        )
        for w in writes
    ]
    for r in results:
        d = decided.get(r.id)
        human = d is not None and d.actor_kind == "human"
        out.append(
            RunWrite(
                "screening",
                r.id,
                "evidence_version",
                r.evidence_version_id,
                r.action,
                "decided" if d is not None else "pending",
                r.created_at,
                None if d is None else d.decision,
                names.get(UUID(d.actor_id), "Former member") if d is not None and human else None,
                None if d is None else d.at,
            )
        )
    async with tenant_session(ctx.tenant) as session:
        routed = {
            r.id: r.routed_to_user_id
            for r in (await session.execute(_ROUTED, {"run": run.id})).all()
        }
    out = [_write_state(w, routed, names) for w in out]
    if await projection_for(ctx, engagement_id) == "metadata":  # DEC-87: no record references
        out = [replace(w, target_id=None, approver_name=None) for w in out]
    return sorted(out, key=lambda w: (w.at, str(w.id)))


def _write_state(w: RunWrite, routed: dict[UUID, UUID | None], names: dict[UUID, str]) -> RunWrite:
    state = WRITE_STATE.get(w.outcome)
    if w.kind == "screening" and w.decision is not None:
        state = "declined" if w.decision in ("rejected", "dismissed") else "approved"
    proposal = w.id if w.kind == "proposal" else None
    approver: str | None = None
    who = routed.get(w.id) if proposal is not None else None
    if who is not None and state == "waiting":
        approver = names.get(who, "Former member")
    return replace(w, state=state, approver_name=approver, proposal_id=proposal)


# --- C6 v1 run items (TASK-5001; P-09 Story 1.3 and 8.1) ------------------------------------

# Legacy kinds (read-time adapter), then the C6 v2 wire set a v2 run's events carry (P-09-T07).
ItemKind = Literal[
    "tool_card", "narration", "decision", "failure",
    "user", "line", "block", "tool", "progress", "question", "answer", "error", "plan",
    "approval", "decision_ref", "artifact", "run_card", "notice",
]  # fmt: skip
_ITEM_ORDER: Final = ("tool_card", "narration", "decision", "failure")


@dataclass(frozen=True)
class RunItem:
    """One entry in a run's thread, read-time from the run's own records (no back-fill).

    `tool_card`: the whole legacy run as one card, `code` the agent spec; its state follows the
    run header, so a polling client updates it from the header rather than a new item.
    `narration`: the engagement agent's action (`code`, `outcome` what happened, `detail` the
    reason), worded by the client from code words, never model text. `decision`: a person's
    decision on what the run proposed. `failure`: the run's failure code."""

    seq: int
    kind: ItemKind
    at: datetime
    code: str
    outcome: str | None
    detail: str | None
    actor: str | None
    ref_type: str | None
    ref_id: UUID | None
    # A v2 item's AgentBlocks as stored; the route validates them (P-09-T03) or drops them.
    blocks: dict[str, object] | None = None


@dataclass(frozen=True)
class RunItems:
    run: RunSummary
    items: list[RunItem]
    last_seq: int
    resync: bool


async def items_for(ctx: AuthContext, run_id: UUID, after_seq: int) -> RunItems:
    """The run header plus its items after `after_seq`. Items are numbered by time from the
    records, so a seq never changes meaning; asking past the end answers `resync`."""
    run = await _run(ctx, run_id, "agent_run.read")
    engagement_id = run.engagement_id
    if engagement_id is None:
        raise NotFound
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    summary = await _summary_v1(ctx, run, names)
    async with tenant_session(ctx.tenant) as session:
        facts = (await v2_facts(session, [run.id])).get(run.id)
        found = await v2_items(session, run.id, after_seq) if facts and facts.v2 else None
    if found is not None:
        return await _v2_run_items(ctx, engagement_id, summary, names, *found)
    async with tenant_session(ctx.tenant) as session:
        writes = await run_writes(session, run.id)
        results = await screening_results_of_run(session, run.id)
        activity: Sequence[AgentActivity] = (
            await run_activity(
                session, engagement_id, run.source_event_id, run.started_at, run.finished_at
            )
            if run.agent_id == "engagement.agent"
            else []
        )
    hidden = await withdrawn_among(ctx.tenant, [r.evidence_version_id for r in results])
    results = [r for r in results if r.evidence_version_id not in hidden]  # P-06-T19
    decisions = await decisions_on_screenings(ctx.tenant, [r.id for r in results])
    counts = written_counts(writes) or output_counts(run.output)
    subject = _subject(run)
    subject_id = run.evidence_version_id or run.inbox_file_id or run.methodology_version_id
    raw: list[RunItem] = [
        RunItem(
            0,
            "tool_card",
            run.started_at,
            run.agent_id,
            summary.state,
            ",".join(f"{k}:{n}" for k, n in counts) or None,
            None,
            subject,
            subject_id,
        )
    ]
    for a in activity:
        raw.append(
            RunItem(
                0,
                "narration",
                a.created_at,
                a.action,
                a.outcome,
                a.reason,
                None,
                a.record_type,
                a.record_id,
            )
        )
    for d in decisions:
        actor = names.get(UUID(d.actor_id), "Former member") if d.actor_kind == "human" else None
        raw.append(
            RunItem(
                0,
                "decision",
                d.at,
                d.decision,
                None,
                "screening",
                actor,
                "screening_result",
                d.screening_result_id,
            )
        )
    for w in writes:
        if w.decision is not None and w.decided_at is not None:
            actor = None if w.decided_by is None else names.get(w.decided_by, "Former member")
            raw.append(
                RunItem(0, "decision", w.decided_at, w.decision, None, w.kind, actor, w.kind, w.id)
            )
    if run.status == "failed" and run.finished_at is not None:
        raw.append(
            RunItem(
                0,
                "failure",
                run.finished_at,
                run.failure_code or "failed",
                None,
                None,
                None,
                None,
                None,
            )
        )
    items, last, resync = page_items(raw, after_seq)
    if await projection_for(ctx, engagement_id) == "metadata":
        # DEC-87: no narration and no record references. Numbering comes first, so a seq means
        # the same thing to every viewer and polling still works.
        items = [replace(i, ref_id=None) for i in items if i.kind != "narration"]
    return RunItems(summary, items, last, resync)


# DEC-87: what a metadata reader sees of a v2 run's items: the kind and its code, no words, no
# blocks, no record references.
_CONTENT_KINDS: Final = frozenset({"line", "block", "user", "answer", "question"})


async def _v2_run_items(
    ctx: AuthContext,
    engagement_id: UUID,
    summary: RunSummary,
    names: dict[UUID, str],
    items: Sequence[V2ItemT],
    last: int,
    resync: bool,
) -> RunItems:
    out = [
        RunItem(
            i.seq,
            cast(ItemKind, i.kind),
            i.at,
            i.code,
            i.outcome,
            i.detail,
            None if i.actor_user_id is None else names.get(i.actor_user_id, "Former member"),
            i.ref_type,
            i.ref_id,
            i.blocks,
        )
        for i in items
    ]
    if await projection_for(ctx, engagement_id) == "metadata":
        out = [
            replace(i, detail=None, ref_id=None, blocks=None)
            for i in out
            if i.kind not in _CONTENT_KINDS
        ]
    return RunItems(summary, out, last, resync)


def page_items(raw: Sequence[RunItem], after_seq: int) -> tuple[list[RunItem], int, bool]:
    """Number items by time (the tool card first at its instant) and keep those after
    `after_seq`; a client ahead of the server gets everything back with `resync`."""
    ordered = sorted(raw, key=lambda i: (i.at, _ITEM_ORDER.index(i.kind), str(i.ref_id)))
    numbered = [replace(i, seq=n + 1) for n, i in enumerate(ordered)]
    last = len(numbered)
    if after_seq > last:
        return numbered, last, True
    return [i for i in numbered if i.seq > after_seq], last, False


__all__: Sequence[str] = [
    "export_trace",
    "items_for",
    "projection_for",
    "records_read_for",
    "run_view",
    "runs_for",
    "step_detail",
    "trace_for",
    "writes_for",
]
