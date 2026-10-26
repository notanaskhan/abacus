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

from abacus.ai_gateway import attempts_for
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.models import AgentActivity, AgentRun
from abacus.modules.agents.repository import (
    RunWriteRow,
    engagement_runs,
    get_run,
    run_activity,
    run_writes,
    screening_results_of_run,
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
}
State = Literal["queued", "running", "succeeded", "needs_input", "failed"]
# DEC-87 (TASK-5002): content for the engagement's people and oversight in scope; metadata for
# everyone else agent_run.read lets in (security and firm admins): what ran, never the content.
Projection = Literal["content", "metadata"]
RowKind = Literal["start", "queued", "attempt", "output", "decision", "finish"]


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


def _summary(run: AgentRun, names: dict[UUID, str]) -> RunSummary:
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
    )


async def runs_for(
    ctx: AuthContext, engagement_id: UUID, state: Literal["active", "recent"], limit: int
) -> list[RunSummary]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "agent_run.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        runs = await engagement_runs(session, ctx, engagement_id, max(1, min(limit, 100)))
    if state == "active":
        runs = [r for r in runs if r.status == "running"]
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    return [_summary(r, names) for r in runs]


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
    return Trace(
        _summary(run, names),
        RUNTIME_LABEL,
        REGION,
        TRAINING,
        len(attempts),
        sum(a.input_tokens for a in attempts),
        sum(a.output_tokens for a in attempts),
        rows,
        read,
        counts,
        model_text if projection == "content" else None,
        projection,
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
    return json.dumps(_plain(asdict(trace)), sort_keys=True, separators=(",", ":")).encode()


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
            "projection": "content",
        },
    )


# --- C6 v1 (TASK-5000): the run, its records read and its writes ---------------------------


@dataclass(frozen=True)
class RunView:
    run: RunSummary
    run_record_sha256: str
    allowed_actions: list[str]
    projection: Projection


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
    actions = await allowed_actions(ctx, ref.resource(), ["agent_run.read", "run_trace.export"])
    projection = await projection_for(ctx, engagement_id)
    return RunView(_summary(run, names), run_record_sha256(run), sorted(actions), projection)


def records_read_of(run: AgentRun) -> list[RecordsRead]:
    read: list[RecordsRead] = []
    subject = _subject(run)
    if subject is not None:
        read.append(RecordsRead(subject, 1))
    if run.task_scope:
        read.append(RecordsRead("task_scope", len(run.task_scope)))
    return read


async def records_read_for(ctx: AuthContext, run_id: UUID) -> list[RecordsRead]:
    return records_read_of(await _run(ctx, run_id, "agent_run.read"))


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
    if await projection_for(ctx, engagement_id) == "metadata":  # DEC-87: no record references
        out = [replace(w, target_id=None) for w in out]
    return sorted(out, key=lambda w: (w.at, str(w.id)))


# --- C6 v1 run items (TASK-5001; P-09 Story 1.3 and 8.1) ------------------------------------

ItemKind = Literal["tool_card", "narration", "decision", "failure"]
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
    summary = _summary(run, names)
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
    "trace_for",
    "writes_for",
]
