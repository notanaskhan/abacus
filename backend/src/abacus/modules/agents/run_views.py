"""The run read model for runtime-v2 runs (P-09-T07; SPEC-648; P-09 §4.3; DEC-57, DEC-87).
PROTECTED (agents).

What the dock reads beside C6 v1's summary (`runs.py`), from P-10's v2 columns and tables:

- **Header**: run number, what the run is blocked on, code's counters, who it runs as, what
  started it and the work item it is on (`agent_runs` v2 columns, 0680).
- **Projection by level** ("Run projection", glossary): computed by code from the newest decided
  plan version's steps and each step key's latest step row, never stored (ADR-050; DEC-57). A
  plan step with no step row yet is `queued`. Every level's six counts sum to its total, and the
  totals sum to the plan's steps in every state.
- **Items** of a v2 run: its `item.appended` run events in `run_seq` order, in the C6 v2 wire set
  (`user`, `line`, `block`, `tool`, ...). A legacy run keeps `runs.items_for`'s read-time adapter
  (the whole run as one tool card, the engagement agent's activity as templated narration).
- **Active**: a v2 run is active while its state is not terminal.

Authorisation is the caller's (`runs._run`): `agent_run.read` on the run's engagement, walls first
(404). Every value here is a code, a count or a reference; names come from the engagement team.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.ext.asyncio import AsyncSession

StepState = Literal[
    "queued",
    "dispatched",
    "running",
    "waiting_on_inputs",
    "blocked",
    "succeeded",
    "failed",
    "cancelled",
    "skipped",
]
Bucket = Literal["done", "running", "blocked", "waiting", "queued", "failed"]
# A step's state counted in the projection's six buckets (DEC-3004): a skipped step is done (the
# plan moved past it), a cancelled one failed (it will not complete), dispatched is running.
BUCKET: Final[Mapping[str, Bucket]] = {
    "succeeded": "done",
    "skipped": "done",
    "running": "running",
    "dispatched": "running",
    "blocked": "blocked",
    "waiting_on_inputs": "waiting",
    "queued": "queued",
    "failed": "failed",
    "cancelled": "failed",
}
TERMINAL: Final = frozenset(
    {"succeeded", "approved", "partially_approved", "rejected", "failed", "cancelled"}
)
ITEM_KINDS: Final = frozenset(
    {
        "user", "line", "block", "tool", "progress", "question", "answer", "error", "plan",
        "approval", "decision_ref", "artifact", "run_card", "notice",
    }
)  # fmt: skip


@dataclass(frozen=True)
class PlanStep:
    key: str
    level: int


@dataclass(frozen=True)
class LevelCount:
    level: int
    total: int
    done: int = 0
    running: int = 0
    blocked: int = 0
    waiting: int = 0
    queued: int = 0
    failed: int = 0


def project_levels(steps: Sequence[PlanStep], latest: Mapping[str, str]) -> list[LevelCount]:
    """The projection by level: each plan step counted once, in its latest step's bucket (no
    step row yet: queued). Levels below 1 count in level 1 (a plan without levels is one)."""
    counts: dict[int, dict[str, int]] = {}
    for step in steps:
        level = max(1, step.level)
        bucket = BUCKET.get(latest.get(step.key, "queued"), "queued")
        row = counts.setdefault(level, {})
        row[bucket] = row.get(bucket, 0) + 1
    return [LevelCount(level, sum(row.values()), **row) for level, row in sorted(counts.items())]


@dataclass(frozen=True)
class Counters:
    records_read: int = 0
    citations_count: int = 0
    writes_done: int = 0
    writes_waiting: int = 0
    agent_ms: int = 0
    agent_minutes: int = 0


@dataclass(frozen=True)
class V2Facts:
    run_id: UUID
    run_number: int | None
    state: str | None
    state_reason: str | None
    blocked_on: dict[str, object] | None
    counters: Counters
    runs_as_user_id: UUID | None
    trigger_kind: str | None
    work_item_ref: str | None
    plan_id: UUID | None
    stepped: bool  # the run has runtime steps: a v2 run, not a legacy specialist

    @property
    def v2(self) -> bool:
        return self.plan_id is not None or self.stepped

    @property
    def active(self) -> bool:
        return self.state is not None and self.state not in TERMINAL


_FACTS = text(
    "SELECT r.id, r.run_number, r.state, r.state_reason, r.blocked_on, r.records_read, "
    "r.citations_count, r.writes_done, r.writes_waiting, r.agent_ms, r.agent_minutes, "
    "r.runs_as_user_id, r.trigger_kind, r.work_item_ref, r.plan_id, "
    "EXISTS (SELECT 1 FROM agent_run_steps s WHERE s.run_id = r.id) AS stepped "
    "FROM agent_runs r WHERE r.id = ANY(:ids)"
).bindparams(bindparam("ids", type_=ARRAY(PgUUID(as_uuid=True))))


async def v2_facts(session: AsyncSession, run_ids: Sequence[UUID]) -> dict[UUID, V2Facts]:
    """Each run's v2 columns, in one read (row-level security scopes it to the tenant)."""
    if not run_ids:
        return {}
    rows = (await session.execute(_FACTS, {"ids": list(run_ids)})).all()
    return {
        r.id: V2Facts(
            r.id,
            r.run_number,
            r.state,
            r.state_reason,
            cast(dict[str, object] | None, r.blocked_on),
            Counters(
                r.records_read or 0,
                r.citations_count or 0,
                r.writes_done or 0,
                r.writes_waiting or 0,
                r.agent_ms or 0,
                r.agent_minutes or 0,
            ),
            r.runs_as_user_id,
            r.trigger_kind,
            r.work_item_ref,
            r.plan_id,
            bool(r.stepped),
        )
        for r in rows
    }


# The plan the projection counts: the run's own plan, or else its newest decided version.
_PLAN = text(
    "SELECT steps FROM agent_plans WHERE run_id = :run AND (id = :plan OR (CAST(:plan AS uuid) "
    "IS NULL AND state IN ('approved', 'edited', 'standing'))) ORDER BY version DESC LIMIT 1"
)
# Each plan step key's latest step row (a retry is a later seq of the same key).
_LATEST = text(
    "SELECT DISTINCT ON (plan_step_key) plan_step_key, state FROM agent_run_steps "
    "WHERE run_id = :run AND plan_step_key IS NOT NULL ORDER BY plan_step_key, seq DESC"
)


def plan_steps(raw: object) -> list[PlanStep]:
    """The plan's steps from its stored JSON (C6 v2 `RunPlanStepOut`: `key`, `level`)."""
    steps: list[PlanStep] = []
    if not isinstance(raw, list):
        return steps
    for item in cast(list[object], raw):
        if isinstance(item, dict):
            entry = cast(dict[str, object], item)
            key, level = entry.get("key"), entry.get("level", 0)
            if isinstance(key, str) and isinstance(level, int):
                steps.append(PlanStep(key, level))
    return steps


async def levels_for(session: AsyncSession, facts: V2Facts) -> list[LevelCount]:
    plan = (await session.execute(_PLAN, {"run": facts.run_id, "plan": facts.plan_id})).first()
    if plan is None:
        return []
    latest = {
        str(r.plan_step_key): str(r.state)
        for r in (await session.execute(_LATEST, {"run": facts.run_id})).all()
    }
    return project_levels(plan_steps(plan.steps), latest)


@dataclass(frozen=True)
class V2Item:
    seq: int
    kind: str
    at: datetime
    code: str
    outcome: str | None
    detail: str | None
    ref_type: str | None
    ref_id: UUID | None
    actor_user_id: UUID | None
    blocks: dict[str, object] | None = None
    extra: dict[str, object] = field(default_factory=dict[str, object])


_ITEMS = text(
    "SELECT run_seq, payload, created_at FROM run_events WHERE run_id = :run "
    "AND type = 'item.appended' AND run_seq > :after ORDER BY run_seq LIMIT :limit"
)
_LAST = text("SELECT max(run_seq) FROM run_events WHERE run_id = :run AND run_seq IS NOT NULL")


def _uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value)) if value is not None else None
    except ValueError:
        return None


def _code(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def item_of(seq: int, payload: Mapping[str, object], at: datetime) -> V2Item | None:
    """One `item.appended` payload as a feed item; an unknown kind is skipped (fail closed)."""
    kind = payload.get("kind")
    if not isinstance(kind, str) or kind not in ITEM_KINDS:
        return None
    blocks = payload.get("blocks")
    return V2Item(
        seq,
        kind,
        at,
        _code(payload.get("code"), kind),
        cast(str | None, payload.get("outcome"))
        if isinstance(payload.get("outcome"), str)
        else None,
        cast(str | None, payload.get("detail"))
        if isinstance(payload.get("detail"), str)
        else None,
        cast(str | None, payload.get("ref_type"))
        if isinstance(payload.get("ref_type"), str)
        else None,
        _uuid(payload.get("ref_id")),
        _uuid(payload.get("actor_user_id")),
        cast(dict[str, object], blocks) if isinstance(blocks, dict) else None,
    )


async def v2_items(
    session: AsyncSession, run_id: UUID, after_seq: int, limit: int = 200
) -> tuple[list[V2Item], int, bool]:
    """The v2 run's items after `after_seq`, the last seq, and whether the client is ahead."""
    last = int((await session.execute(_LAST, {"run": run_id})).scalar() or 0)
    if after_seq > last:
        after_seq = 0
        resync = True
    else:
        resync = False
    rows = (
        await session.execute(
            _ITEMS, {"run": run_id, "after": after_seq, "limit": max(1, min(limit, 200))}
        )
    ).all()
    items = [
        found
        for r in rows
        if (found := item_of(int(r.run_seq), cast(Mapping[str, object], r.payload), r.created_at))
    ]
    return items, last, resync


__all__ = [
    "BUCKET",
    "Counters",
    "LevelCount",
    "PlanStep",
    "V2Facts",
    "V2Item",
    "item_of",
    "levels_for",
    "plan_steps",
    "project_levels",
    "v2_facts",
    "v2_items",
]
