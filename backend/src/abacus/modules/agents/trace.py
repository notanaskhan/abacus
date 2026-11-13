"""The trace read model for runtime-v2 runs (P-09-T08; SPEC-648; P-09 §4.3, Stories 4.1 to 4.3;
DEC-87, DEC-3005). PROTECTED (agents).

WB-09's drawer over a v2 run: the summary card, the timeline, a tool row's detail with up to five
sample records, records read by source and connection, and the writes with their approvers.

- **Timeline rows** come from the run's durable records (so they survive `run_events`' 30-day
  prune): the plan decision ("Plan approved by" a person, phase `plan`), then each step row in
  `seq` order. A step's phase follows its kind (`tool` execute, `compute` compute, `approval`
  proposed_write, `decision` decision, `question` steer, the rest notice); its mark follows its
  state; its title is the verb, a right angle quote and the plan label; its detail is a code:
  the needs for a waiting step, the error code for a failed one, the blocked-on role for a
  blocked one. Durations are code's.
- **Metadata projection** (DEC-87): titles and states only. No plan labels (a step reads as its
  kind), no details, no names but the actor of a plan decision, no samples.
- **Step detail**: content only. `args_summary` is the harness's redacted summary with TINs
  scrubbed; samples resolve through the owning module's registered resolver
  (`register_trace_samples`), which filters by `visible()` for the caller. A record type with no
  resolver shows no sample (fail closed).
- **Records read**: each step's `records_read` summed by the record type its tool declares (C17's
  `records_read`) and its `source_ref`.
- **Region and training** from the provider-terms register entry covering the run's route on the
  day it started.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.provider_terms import covering
from abacus.kernel.tin_patterns import scrub_tins
from abacus.modules.agents.tools.registry import ToolNotRegistered, row_fields, tool
from abacus.modules.identity.api import AuthContext

Phase = Literal[
    "plan", "execute", "compute", "proposed_write", "decision", "policy", "steer", "notice"
]
Mark = Literal["start", "plan", "done", "running", "waiting", "blocked", "failed", "muted"]
RowState = Literal["done", "failed", "waiting", "running"]
PHASE_OF_KIND: Final[Mapping[str, Phase]] = {
    "tool": "execute",
    "compute": "compute",
    "model": "execute",
    "approval": "proposed_write",
    "decision": "decision",
    "question": "steer",
}
MARK_OF_STATE: Final[Mapping[str, Mark]] = {
    "succeeded": "done",
    "skipped": "muted",
    "running": "running",
    "dispatched": "running",
    "waiting_on_inputs": "waiting",
    "queued": "muted",
    "blocked": "blocked",
    "failed": "failed",
    "cancelled": "failed",
}
ROW_STATE_OF_MARK: Final[Mapping[Mark, RowState]] = {
    "done": "done",
    "muted": "waiting",
    "running": "running",
    "waiting": "waiting",
    "blocked": "waiting",
    "failed": "failed",
    "start": "done",
    "plan": "done",
}
VERB_OF_PHASE: Final[Mapping[Phase, str]] = {
    "execute": "Execute",
    "compute": "Compute",
    "proposed_write": "Propose",
    "decision": "Decide",
    "steer": "Ask",
    "notice": "Note",
    "plan": "Plan",
    "policy": "Policy",
}
US_REGION: Final = "United States (data and inference)"


@dataclass(frozen=True)
class V2TraceRow:
    seq: int
    at: datetime
    phase: Phase
    mark: Mark
    title: str
    state: RowState
    detail: str | None
    actor: str | None
    duration_ms: int | None
    step_id: UUID | None = None


@dataclass(frozen=True)
class StepRow:
    id: UUID
    seq: int
    plan_step_key: str | None
    kind: str
    tool_name: str | None
    state: str
    needs: object
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime
    error_code: str | None
    records_read: int
    args_summary: object
    sample_refs: object
    source_ref: str | None


_STEPS = text(
    "SELECT id, seq, plan_step_key, kind, tool_name, state, needs, started_at, ended_at, "
    "created_at, error_code, records_read, args_summary, sample_refs, source_ref "
    "FROM agent_run_steps WHERE run_id = :run ORDER BY seq"
)
_PLAN = text(
    "SELECT steps, state, decided_by, decided_at FROM agent_plans WHERE run_id = :run "
    "AND state IN ('approved', 'edited', 'standing') ORDER BY version DESC LIMIT 1"
)
_STEP = text(
    "SELECT id, seq, plan_step_key, kind, tool_name, state, needs, started_at, ended_at, "
    "created_at, error_code, records_read, args_summary, sample_refs, source_ref "
    "FROM agent_run_steps WHERE run_id = :run AND id = :step"
)


def _step(r: object) -> StepRow:
    row = cast(Mapping[str, object], getattr(r, "_mapping"))  # noqa: B009 -- a Row's mapping
    return StepRow(**{k: row[k] for k in StepRow.__dataclass_fields__})  # type: ignore[arg-type] -- the row's keys are the dataclass fields


async def steps_of(session: AsyncSession, run_id: UUID) -> list[StepRow]:
    return [_step(r) for r in (await session.execute(_STEPS, {"run": run_id})).all()]


async def step_of(session: AsyncSession, run_id: UUID, step_id: UUID) -> StepRow | None:
    found = (await session.execute(_STEP, {"run": run_id, "step": step_id})).first()
    return None if found is None else _step(found)


@dataclass(frozen=True)
class PlanDecision:
    labels: Mapping[str, str]
    decided_by: UUID | None
    decided_at: datetime | None
    state: str


async def plan_of(session: AsyncSession, run_id: UUID) -> PlanDecision | None:
    found = (await session.execute(_PLAN, {"run": run_id})).first()
    if found is None:
        return None
    labels: dict[str, str] = {}
    raw = cast(object, found.steps)
    if isinstance(raw, list):
        for item in cast(list[object], raw):
            if isinstance(item, dict):
                entry = cast(dict[str, object], item)
                key, label = entry.get("key"), entry.get("label")
                if isinstance(key, str) and isinstance(label, str):
                    labels[key] = label
    return PlanDecision(labels, found.decided_by, found.decided_at, str(found.state))


def _needs(raw: object) -> str | None:
    if isinstance(raw, list):
        codes = [str(n) for n in cast(list[object], raw) if isinstance(n, str)]
        return ",".join(codes) or None
    return None


def _duration(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds() * 1000))


def timeline(
    plan: PlanDecision | None,
    steps: Sequence[StepRow],
    names: Mapping[UUID, str],
    *,
    metadata: bool,
    blocked_role: str | None = None,
) -> list[V2TraceRow]:
    """The v2 timeline (module docstring); numbered from 1 in time order."""
    rows: list[V2TraceRow] = []
    if plan is not None and plan.decided_at is not None:
        who = None if plan.decided_by is None else names.get(plan.decided_by, "Former member")
        verb = "Plan edited and approved" if plan.state == "edited" else "Plan approved"
        rows.append(V2TraceRow(0, plan.decided_at, "plan", "plan", verb, "done", None, who, None))
    for s in steps:
        phase: Phase = PHASE_OF_KIND.get(s.kind, "notice")
        mark = MARK_OF_STATE.get(s.state, "muted")
        label = (plan.labels.get(s.plan_step_key or "") if plan else None) or None
        if metadata or label is None:
            title = VERB_OF_PHASE[phase]
        else:
            title = f"{VERB_OF_PHASE[phase]} \u203a {label}"
        detail: str | None = None
        if not metadata:
            if mark == "waiting":
                detail = _needs(s.needs)
            elif mark == "failed":
                detail = s.error_code
            elif mark == "blocked":
                detail = blocked_role
        rows.append(
            V2TraceRow(
                0,
                s.started_at or s.created_at,
                phase,
                mark,
                title,
                ROW_STATE_OF_MARK[mark],
                detail,
                None,
                _duration(s.started_at, s.ended_at),
                s.id,
            )
        )
    ordered = sorted(rows, key=lambda r: (r.at, r.phase != "plan"))
    return [
        V2TraceRow(i + 1, r.at, r.phase, r.mark, r.title, r.state, r.detail, r.actor,
                   r.duration_ms, r.step_id)
        for i, r in enumerate(ordered)
    ]  # fmt: skip


def _record_type(tool_name: str | None) -> str:
    if tool_name is None:
        return "records"
    try:
        return tool(tool_name).records_read or tool_name
    except ToolNotRegistered:
        return tool_name


@dataclass(frozen=True)
class SourceCount:
    source: str
    count: int
    connection_id: UUID | None
    through: str | None


def records_read_by_source(steps: Sequence[StepRow]) -> list[SourceCount]:
    """Each step's records read, by its tool's record type and the source it came through."""
    counts: dict[tuple[str, str | None], int] = {}
    for s in steps:
        if s.records_read <= 0:
            continue
        key = (_record_type(s.tool_name), s.source_ref)
        counts[key] = counts.get(key, 0) + s.records_read
    out: list[SourceCount] = []
    for (source, ref), n in sorted(counts.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        connection = None
        if ref is not None and ref != "accrued":
            try:
                connection = UUID(ref)
            except ValueError:
                connection = None
        out.append(SourceCount(source, n, connection, "Accrued" if ref == "accrued" else None))
    return out


def region_of(route: str | None, started: datetime) -> str:
    """The region the register's entry for the run's route names, worded for the trace."""
    entry = covering(route, started.date()) if route else None
    if entry is None or entry.region.lower().startswith("us"):
        return US_REGION
    return f"{entry.region} (data and inference)"


# --- Step detail samples (fail closed per record type) -------------------------------------------


@dataclass(frozen=True)
class Sample:
    record_type: str
    id: UUID
    label: str
    open_route: str


SampleResolver = Callable[[AuthContext, Sequence[UUID]], Awaitable[list[Sample]]]
_RESOLVERS: dict[str, SampleResolver] = {}


def register_trace_samples(record_type: str, resolver: SampleResolver) -> None:
    """A module that owns `record_type` resolves the step's sample ids it may show the caller
    (filtered by `visible()`), with a label and the route that opens each (ADR-106 slot)."""
    if record_type in _RESOLVERS and _RESOLVERS[record_type] is not resolver:
        raise ValueError(f"trace samples for {record_type!r} are already registered")
    _RESOLVERS[record_type] = resolver


SAMPLES_PER_STEP: Final = 5


def _uuid(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def step_sample_refs(tool_name: str, result: Mapping[str, object] | None) -> list[dict[str, str]]:
    """The first five records a tool step read, for `agent_run_steps.sample_refs` (P-09-T08; 0751):
    each `{record_type, id}`, the type the tool declares it reads and the `id` of each row in its
    row lists in the order returned, or the output's own `id` for a single-record read. Ids only:
    a sample's label and route come from the owning module's resolver when someone opens the step,
    filtered by `visible()` for that reader. A tool with no declared record type writes none."""
    if result is None:
        return []
    try:
        declared = tool(tool_name)
    except ToolNotRegistered:
        return []
    kind = declared.records_read
    if not kind:
        return []
    ids: list[UUID] = []
    rows = row_fields(declared.output_model)
    for field in rows:
        values = result.get(field)
        if not isinstance(values, list):
            continue
        for row in cast(list[object], values):
            if isinstance(row, dict):
                found = _uuid(cast(dict[str, object], row).get("id"))
                if found is not None and found not in ids:
                    ids.append(found)
            if len(ids) >= SAMPLES_PER_STEP:
                break
        if len(ids) >= SAMPLES_PER_STEP:
            break
    if not rows:
        own = _uuid(result.get("id"))
        if own is not None:
            ids.append(own)
    return [{"record_type": kind, "id": str(i)} for i in ids[:SAMPLES_PER_STEP]]


def sample_refs(raw: object) -> list[tuple[str, UUID]]:
    refs: list[tuple[str, UUID]] = []
    if not isinstance(raw, list):
        return refs
    for item in cast(list[object], raw)[:5]:
        if isinstance(item, dict):
            entry = cast(dict[str, object], item)
            kind, ident = entry.get("record_type"), entry.get("id")
            if isinstance(kind, str) and isinstance(ident, str):
                try:
                    refs.append((kind, UUID(ident)))
                except ValueError:
                    continue
    return refs


async def samples_for(ctx: AuthContext, raw: object, limit: int) -> list[Sample]:
    """Up to `limit` (at most 5) of the step's samples the caller may see, in the order read."""
    refs = sample_refs(raw)[: max(0, min(limit, 5))]
    by_type: dict[str, list[UUID]] = {}
    for kind, ident in refs:
        by_type.setdefault(kind, []).append(ident)
    found: dict[tuple[str, UUID], Sample] = {}
    for kind, ids in by_type.items():
        resolver = _RESOLVERS.get(kind)
        if resolver is None:
            continue
        for sample in await resolver(ctx, ids):
            if sample.id in ids:
                found[(kind, sample.id)] = Sample(
                    kind, sample.id, scrub_tins(sample.label), sample.open_route
                )
    return [found[r] for r in refs if r in found]


def args_summary_text(raw: object) -> str | None:
    """The harness's redacted argument summary as display text, TINs scrubbed (C19)."""
    if raw is None:
        return None
    if isinstance(raw, str):
        return scrub_tins(raw)
    return scrub_tins(json.dumps(raw, sort_keys=True, default=str))


def today_for(at: datetime) -> date:
    return at.date()


__all__ = [
    "Sample",
    "SourceCount",
    "StepRow",
    "V2TraceRow",
    "args_summary_text",
    "plan_of",
    "records_read_by_source",
    "region_of",
    "register_trace_samples",
    "samples_for",
    "step_of",
    "step_sample_refs",
    "steps_of",
    "timeline",
]
