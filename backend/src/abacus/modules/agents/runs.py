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
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Final, Literal, cast
from uuid import UUID

from abacus.ai_gateway import attempts_for
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.models import AgentRun
from abacus.modules.agents.repository import engagement_runs, get_run, screening_results_of_run
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import decisions_on_screenings
from abacus.modules.identity.api import AuthContext, authorise, engagement_team

RUNTIME_LABEL: Final = "Abacus agent runtime"
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


async def trace_for(ctx: AuthContext, run_id: UUID) -> Trace:
    run = await _run(ctx, run_id, "agent_run.read")
    engagement_id = run.engagement_id
    if engagement_id is None:  # _run refuses firm-level runs
        raise NotFound
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    attempts = await attempts_for(ctx.tenant, run.id)
    async with tenant_session(ctx.tenant) as session:
        results = await screening_results_of_run(session, run.id)
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
    counts = output_counts(run.output)
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
    read: list[RecordsRead] = []
    subject = _subject(run)
    if subject is not None:
        read.append(RecordsRead(subject, 1))
    if run.task_scope:
        read.append(RecordsRead("task_scope", len(run.task_scope)))
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
        model_text,
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


__all__: Sequence[str] = ["export_trace", "runs_for", "trace_for"]
