"""Briefing dispatch and freshness (I-02-T13; TASK-7913; I-02 §4.4, F3; SPEC-654; ADR-019, ADR-050,
ADR-090; DEC-4916, DEC-4917). RED: `agents.api.ensure_briefings` decides which engagement
briefings of the viewer's day to build and starts them; it never writes a briefing's text.

- **Idempotent dispatch.** Per (viewer, engagement, firm day) a `building` row is claimed under a
  transaction-scoped advisory lock before any run starts, so two concurrent first opens start one
  run per engagement. A day's ready row with the same facts hash is never rebuilt; a `building`
  row younger than `STALE_BUILD` is in flight and left alone. The run is P-10's engagement run on
  the `briefing.today` plan provider (one `briefing_today` step, `run_step.briefing_today`), its
  id the run's own (`AgentRunWorkflow`), so the dispatch key is the claimed row.
- **At most three at once** per viewer: rows still `building` count against `MAX_PARALLEL`; the
  rest are picked up by the next call (the screen's refetch, or the staleness poll).
- **Pre-checks, no model call.** Before claiming, the capability's readiness for the viewer on the
  engagement (`capability_ready`: boundary, §7216 consent, budget, pause) is read; not ready, the
  day's row is recorded `unavailable` with its reason (`boundary_refused:<code>`, `consent_7216`,
  `budget_soft_limit`, `metadata_only`, `flag_off`) and nothing runs.
- **Modes.** `interactive` (the first open, or a person's Build) builds what is missing; `force`
  rebuilds every engagement (three forced builds a day, 429 `rebuild_limit`); `background`
  (staleness) is debounced: no rebuild within 15 minutes of the last one and at most six a day.
- **Snapshot.** `write_snapshot` records the viewer's day as a `user` row of integers and ids only
  (counts, lead-fact refs, card refs): no text.
- **Events.** `daily_briefing.built` (C16-free, identifiers only) reaches the viewer's `user`
  topic; dispatch and unavailability are audited (`daily_briefing.dispatched`,
  `daily_briefing.unavailable`). The run meters its own agent-minutes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainRateLimited
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow

PROVIDER: Final = "briefing.today"
STEP: Final = "briefing_today"
MAX_PARALLEL: Final = 3
STALE_BUILD: Final = timedelta(minutes=10)
DEBOUNCE: Final = timedelta(minutes=15)
MAX_BACKGROUND: Final = 6
MAX_FORCED: Final = 3
Mode = Literal["interactive", "force", "background"]
_REASON: Final = re.compile(
    r"^(boundary_refused:[a-z_]{1,20}|consent_7216|metadata_only|budget_soft_limit|flag_off)$"
)


class RebuildLimit(DomainRateLimited):
    """Three forced rebuilds a day (I-02 §4.3)."""

    code = "rebuild_limit"


class BuildInProgress(DomainConflict):
    code = "in_progress"


class DailyBriefingBuilt(DomainEvent):
    """A viewer's engagement briefing or day snapshot was written (identifiers only)."""

    event_type: ClassVar[str] = "daily_briefing.built"

    viewer_user_id: Annotated[UUID, classified("internal")]
    brief_date: Annotated[date, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")] = None
    status: Annotated[str, classified("internal")] = "ready"


def unavailable_reason(reason: str | None) -> str:
    """The capability's refusal as the table's closed set of reasons."""
    raw = (reason or "").lower()
    if raw in ("consent_7216", "consent_required"):
        return "consent_7216"
    if raw.startswith("budget"):
        return "budget_soft_limit"
    if raw in ("metadata_only", "flag_off"):
        return raw
    code = re.sub(r"[^a-z_]", "_", raw.removeprefix("boundary_refused:"))[:20] or "unavailable"
    out = f"boundary_refused:{code}"
    return out if _REASON.fullmatch(out) else "boundary_refused:unavailable"


@dataclass(frozen=True)
class Dispatched:
    started: list[UUID] = field(default_factory=list[UUID])
    unavailable: list[UUID] = field(default_factory=list[UUID])
    skipped: list[UUID] = field(default_factory=list[UUID])


_LOCK: Final = text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))")
_DAY: Final = text(
    "SELECT id, seq, status, facts_hash, built_at, created_at FROM daily_briefings "
    "WHERE scope = 'engagement' AND viewer_user_id = :v AND engagement_id = :e "
    "AND brief_date = :d ORDER BY seq DESC"
)
_BUILDING: Final = text(
    "SELECT count(*) FROM daily_briefings WHERE scope = 'engagement' AND viewer_user_id = :v "
    "AND brief_date = :d AND status = 'building' AND created_at > :since"
)
_CLAIM: Final = text(
    "INSERT INTO daily_briefings (tenant_id, scope, viewer_user_id, engagement_id, brief_date, "
    "seq, status, unavailable_reason, capability_version) VALUES (:t, 'engagement', :v, :e, :d, "
    ":seq, :status, :reason, 1) RETURNING id"
)
_RUN: Final = text("UPDATE daily_briefings SET agent_run_id = :run WHERE id = :id")


async def _now(tenant: TenantContext) -> datetime:
    from abacus.kernel import clock

    return await clock.now(tenant)


def due(
    rows: Sequence[object], mode: Mode, now: datetime
) -> Literal["build", "in_flight", "fresh", "debounced", "limit"]:
    """Whether one engagement's day needs a build (module docstring); `rows` newest first."""
    if not rows:
        return "build"
    newest = rows[0]
    status = str(getattr(newest, "status", ""))
    created = cast(datetime, getattr(newest, "created_at", now))
    if status == "building" and now - created < STALE_BUILD:
        return "in_flight"
    if mode == "force":
        return "build"
    if mode == "background":
        built = cast(datetime | None, getattr(newest, "built_at", None)) or created
        if now - built < DEBOUNCE:
            return "debounced"
        if len(rows) >= MAX_BACKGROUND:
            return "limit"
        return "build"
    return "fresh" if status in ("ready", "unavailable", "unverified") else "build"


async def ensure_briefings(
    viewer: object, engagements: Sequence[tuple[UUID, str]], mode: Mode, on: date
) -> Dispatched:
    """The viewer's day (module docstring). `viewer` is the person's `AuthContext`; `engagements`
    the (id, label) pairs the assembly found on their gates, already visible to them."""
    from abacus.modules.agents.api import PlanRequest, capability_ready, start_engagement_run
    from abacus.modules.identity.api import AuthContext

    if not isinstance(viewer, AuthContext):
        raise TypeError("briefings are dispatched for a person")
    if viewer.tenant.actor_kind != "human":
        raise TypeError("briefings are dispatched for a person")
    now = await _now(viewer.tenant)
    out = Dispatched()
    if mode == "force" and await forced_today(viewer.tenant, viewer.user_id, on) >= MAX_FORCED:
        raise RebuildLimit(facts={"limit": MAX_FORCED})
    async with tenant_session(viewer.tenant) as session:
        in_flight = int(
            await session.scalar(
                _BUILDING, {"v": viewer.user_id, "d": on, "since": now - STALE_BUILD}
            )
            or 0
        )
    room = max(0, MAX_PARALLEL - in_flight)
    for engagement_id, label in engagements:
        ready, reason = await capability_ready(viewer, engagement_id, PROVIDER)
        async with uow(viewer.tenant) as tx:
            await tx.session.execute(
                _LOCK, {"k": f"briefing:{viewer.user_id}:{engagement_id}:{on.isoformat()}"}
            )
            rows = (
                await tx.session.execute(_DAY, {"v": viewer.user_id, "e": engagement_id, "d": on})
            ).all()
            verdict = due(rows, mode, now)
            if verdict != "build":
                out.skipped.append(engagement_id)
                continue
            seq = 1 if not rows else int(rows[0].seq) + 1
            if not ready:
                why = unavailable_reason(reason)
                claimed = cast(
                    UUID,
                    await tx.session.scalar(
                        _CLAIM,
                        {"t": viewer.tenant_id, "v": viewer.user_id, "e": engagement_id,
                         "d": on, "seq": seq, "status": "unavailable", "reason": why},
                    ),
                )  # fmt: skip
                tx.record(
                    "daily_briefing.unavailable",
                    target=Target("daily_briefing", claimed),
                    after=Ref(reason=why),
                    scope=Scope(engagement_id=engagement_id),
                )
                tx.emit(
                    DailyBriefingBuilt(
                        viewer_user_id=viewer.user_id, brief_date=on,
                        engagement_id=engagement_id, status="unavailable",
                    )
                )  # fmt: skip
                out.unavailable.append(engagement_id)
                continue
            if room <= 0:
                out.skipped.append(engagement_id)
                continue
            claimed = cast(
                UUID,
                await tx.session.scalar(
                    _CLAIM,
                    {"t": viewer.tenant_id, "v": viewer.user_id, "e": engagement_id, "d": on,
                     "seq": seq, "status": "building", "reason": None},
                ),
            )  # fmt: skip
            tx.record(
                "daily_briefing.dispatched",
                target=Target("daily_briefing", claimed),
                after=Ref(mode=mode, seq=seq),
                scope=Scope(engagement_id=engagement_id),
            )
        room -= 1
        started = await start_engagement_run(
            viewer,
            engagement_id,
            work_item_ref=f"briefing:{viewer.user_id}:{on.isoformat()}",
            provider=PROVIDER,
            request=PlanRequest(engagement_id, "all", (label,)),
        )
        async with uow(viewer.tenant) as tx:
            await tx.session.execute(_RUN, {"run": started.run_id, "id": claimed})
        out.started.append(engagement_id)
    return out


_FORCED: Final = text(
    "SELECT count(DISTINCT seq) FROM daily_briefings WHERE scope = 'engagement' AND "
    "viewer_user_id = :v AND brief_date = :d AND seq > 1"
)


async def forced_today(tenant: TenantContext, viewer_user_id: UUID, on: date) -> int:
    """Rebuilds recorded today: each rebuild adds the day's next `seq` for its engagements."""
    async with tenant_session(tenant) as session:
        return int(await session.scalar(_FORCED, {"v": viewer_user_id, "d": on}) or 0)


# --- the plan provider ---------------------------------------------------------------------------


async def briefing_plan(
    tenant: TenantContext, engagement_id: UUID, request: object
) -> list[object]:
    """One `briefing_today` step for the engagement (the run step stores the row)."""
    from abacus.modules.agents.api import PlanStep

    keys = cast(tuple[str, ...], getattr(request, "keys", ()))
    return [
        PlanStep(
            key=STEP,
            label="Today briefing",
            level=1,
            kind="compute",
            tool=f"run_step.{STEP}",
            arguments={"engagement_id": str(engagement_id), "label": keys[0] if keys else ""},
            depends_on=(),
        )
    ]


# --- the day snapshot (code only) --------------------------------------------------------------

_SNAPSHOT: Final = text(
    "INSERT INTO daily_briefings (tenant_id, scope, viewer_user_id, brief_date, seq, status, "
    "counts, lead_facts, card_refs, capability_version, built_at) VALUES (:t, 'user', :v, :d, "
    ":seq, 'ready', CAST(:counts AS jsonb), CAST(:lead AS jsonb), CAST(:cards AS jsonb), 1, "
    "clock_timestamp()) RETURNING id"
)
_SNAPSHOT_SEQ: Final = text(
    "SELECT coalesce(max(seq), 0) FROM daily_briefings WHERE scope = 'user' AND "
    "viewer_user_id = :v AND brief_date = :d"
)


def _ints(values: dict[str, object]) -> dict[str, int]:
    return {k: v for k, v in values.items() if isinstance(v, int) and not isinstance(v, bool)}


async def write_snapshot(viewer: object, vm: object) -> UUID:
    """The viewer's day as integers and ids only (counts, lead-fact refs, card refs)."""
    from abacus.modules.identity.api import AuthContext

    if not isinstance(viewer, AuthContext):
        raise TypeError("a snapshot is a person's")
    on = cast(date, getattr(vm, "brief_date"))  # noqa: B009 -- practice's TodayVM, typed loosely (module direction)
    counts = {str(c.kind): int(c.count) for c in getattr(vm, "cells", [])}
    lead = [
        {"key": str(f.key), "values": _ints(dict(f.values)), "refs": [str(r) for r in f.refs]}
        for f in getattr(vm, "lead_facts", [])
    ]
    cards = [
        {
            "engagement_id": str(c.engagement_id),
            "briefing_id": str(c.briefing_id) if c.briefing_id else None,
        }
        for c in getattr(vm, "cards", [])
    ]
    async with uow(viewer.tenant) as tx:
        seq = int(await tx.session.scalar(_SNAPSHOT_SEQ, {"v": viewer.user_id, "d": on}) or 0) + 1
        snapshot = cast(
            UUID,
            await tx.session.scalar(
                _SNAPSHOT,
                {"t": viewer.tenant_id, "v": viewer.user_id, "d": on, "seq": seq,
                 "counts": json.dumps(counts), "lead": json.dumps(lead),
                 "cards": json.dumps(cards)},
            ),
        )  # fmt: skip
        tx.record(
            "daily_briefing.snapshot",
            target=Target("daily_briefing", snapshot),
            after=Ref(seq=seq),
        )
        tx.emit(DailyBriefingBuilt(viewer_user_id=viewer.user_id, brief_date=on, status="ready"))
    return snapshot


# --- why-line freshness ------------------------------------------------------------------------


def current_why(blocks: object, open_gate_ids: set[str]) -> dict[str, list[dict[str, object]]]:
    """Each why line of a ready briefing whose gate is still open, by gate id. A gate signed (or
    otherwise closed) since the briefing was built drops its line until the rebuild lands."""
    if not isinstance(blocks, dict):
        return {}
    why = cast(dict[str, object], blocks).get("why")
    if not isinstance(why, list):
        return {}
    out: dict[str, list[dict[str, object]]] = {}
    for raw in cast(list[object], why):
        if not isinstance(raw, dict):
            continue
        line = cast(dict[str, object], raw)
        gate = str(line.get("gate_id", ""))
        doc = line.get("line")
        if gate in open_gate_ids and isinstance(doc, dict):
            out[gate] = [cast(dict[str, object], doc)]
    return out


def register() -> None:
    """At the agents api's import: the plan provider and the user-topic invalidation."""
    from abacus.kernel import realtime
    from abacus.modules.agents.engagement_run import register_plan_provider

    register_plan_provider(PROVIDER, briefing_plan)  # type: ignore[arg-type] -- the provider's PlanStep list
    if realtime.invalidation_of(DailyBriefingBuilt.event_type) is None:
        realtime.register_invalidation(
            DailyBriefingBuilt.event_type,
            realtime.Invalidation(
                "daily_briefing", "viewer_user_id", (("user", "viewer_user_id"),)
            ),
        )


__all__ = [
    "MAX_PARALLEL",
    "PROVIDER",
    "BuildInProgress",
    "DailyBriefingBuilt",
    "Dispatched",
    "RebuildLimit",
    "current_why",
    "due",
    "ensure_briefings",
    "forced_today",
    "register",
    "unavailable_reason",
    "write_snapshot",
]
