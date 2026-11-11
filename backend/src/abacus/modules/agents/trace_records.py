"""Durable run records: frozen trace exports, the `run_events` prune and the archive hook
(P-10-T44; SPEC-647 §3.9 AC-RR2 to AC-RR5; P-10 §4.4; ADR-032, ADR-090; DEC-4302). PROTECTED.

- **Frozen exports** (`frozen_body`): the trace a v2 run exports is built from its durable rows
  (steps, plan versions, writes, usage records; P-09-T08), never from `run_events`, so it
  survives the 30-day prune. Once the run has ended, the first export of each projection is
  frozen in `agent_run_traces` with the fingerprint of the durable rows it came from
  (`source_fingerprint`: the run's state and counters, each step's state and end, the newest
  plan version, each write's decision). A later export whose fingerprint still matches answers
  the frozen bytes, so a run adopted 90 days earlier re-exports byte-identical even after names,
  the team or the renderer moved (AC-RR2, AC-RR3). A run whose rows moved (an approved write
  landed) freezes a new version. Each version is audited `agent_run.trace_frozen` with its hash,
  so the hash chain covers it (AC-RR4). Kept as Q-02's `agent_run_records` class.
- **`RunEventsPruneWorkflow`** (daily, `run_events_prune:platform`): `prune_run_events()` in each
  firm, in batches, as the one actor the definer admits (`agents.run_events_prune`); only rows
  older than 30 days go.
- **Archive hook** (`adopted_run_traces`): an engagement's adopted runs (approved, partially
  approved) with their newest content trace's version and hash, for A-07's packaging (AUD-25,
  AC-RR5). Identifiers and hashes only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio import activity

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import PlatformSchedule
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.run_events_prune_workflow import PRUNE_ID, RunEventsPruneWorkflow

_log = get_logger(__name__)
PRUNE_ACTOR: Final = "agents.run_events_prune"
PRUNE_BATCH: Final = 5_000
ENDED: Final = frozenset(
    {"succeeded", "approved", "partially_approved", "rejected", "failed", "cancelled"}
)
ADOPTED: Final = frozenset({"approved", "partially_approved"})

_RUN = text(
    "SELECT engagement_id, state, state_reason, writes_done, writes_waiting, records_read, "
    "citations_count, signed_off_at, finished_at FROM agent_runs WHERE id = :run"
)
_STEPS = text(
    "SELECT seq, state, ended_at, error_code FROM agent_run_steps WHERE run_id = :run ORDER BY seq"
)
_PLAN = text(
    "SELECT version, state FROM agent_plans WHERE run_id = :run ORDER BY version DESC LIMIT 1"
)
_WRITES = text("SELECT id, state, version FROM proposals WHERE agent_run_id = :run ORDER BY id")
_NEWEST = text(
    "SELECT version, body, source_sha256 FROM agent_run_traces WHERE run_id = :run "
    "AND projection = :projection ORDER BY version DESC LIMIT 1"
)
_FREEZE = text(
    "INSERT INTO agent_run_traces (tenant_id, run_id, engagement_id, projection, version, "
    "renderer_version, body, body_sha256, source_sha256) VALUES (:t, :run, :eng, :projection, "
    ":version, :renderer, :body, :sha, :source)"
)


def _iso(value: object) -> str | None:
    return None if value is None else str(value)


async def source_fingerprint(session: AsyncSession, run_id: UUID) -> tuple[str, str, UUID] | None:
    """(fingerprint, state, engagement) of the durable rows a v2 trace is built from; None when
    the run is missing or not a v2 run."""
    run = (await session.execute(_RUN, {"run": run_id})).first()
    if run is None or run.state is None or run.engagement_id is None:
        return None
    steps = (await session.execute(_STEPS, {"run": run_id})).all()
    plan = (await session.execute(_PLAN, {"run": run_id})).first()
    writes = (await session.execute(_WRITES, {"run": run_id})).all()
    facts = {
        "run": [
            run.state,
            run.state_reason,
            int(run.writes_done or 0),
            int(run.writes_waiting or 0),
            int(run.records_read or 0),
            int(run.citations_count or 0),
            _iso(run.signed_off_at),
            _iso(run.finished_at),
        ],
        "steps": [[int(s.seq), s.state, _iso(s.ended_at), s.error_code] for s in steps],
        "plan": [int(plan.version), plan.state] if plan is not None else None,
        "writes": [[str(w.id), w.state, int(w.version)] for w in writes],
    }
    body = json.dumps(facts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(body.encode()).hexdigest(), str(run.state), cast(UUID, run.engagement_id)


async def frozen_body(
    tenant: TenantContext,
    run_id: UUID,
    projection: str,
    renderer_version: str,
    build: Callable[[], Awaitable[bytes]],
) -> bytes:
    """The export body (module docstring): the frozen version when the run has ended and its
    durable rows have not moved, else freshly built (and frozen when the run has ended)."""
    async with tenant_session(tenant) as session:
        found = await source_fingerprint(session, run_id)
        newest = (
            (await session.execute(_NEWEST, {"run": run_id, "projection": projection})).first()
            if found is not None
            else None
        )
    if found is None or found[1] not in ENDED:
        return await build()
    source, _, engagement_id = found
    if newest is not None and newest.source_sha256 == source:
        return str(newest.body).encode()
    body = await build()
    version = int(newest.version) + 1 if newest is not None else 1
    digest = hashlib.sha256(body).hexdigest()
    async with uow(tenant) as tx:
        await tx.session.execute(
            _FREEZE,
            {
                "t": tenant.tenant_id,
                "run": run_id,
                "eng": engagement_id,
                "projection": projection,
                "version": version,
                "renderer": renderer_version,
                "body": body.decode(),
                "sha": digest,
                "source": source,
            },
        )
        tx.record(
            "agent_run.trace_frozen",
            target=Target("agent_run", run_id),
            after=Ref(sha256=digest, version=version),
        )
    return body


@dataclass(frozen=True)
class AdoptedTrace:
    run_id: UUID
    run_number: int | None
    version: int
    body_sha256: str


_ADOPTED = text(
    "SELECT DISTINCT ON (t.run_id) t.run_id, r.run_number, t.version, t.body_sha256 "
    "FROM agent_run_traces t JOIN agent_runs r ON r.id = t.run_id "
    "WHERE t.engagement_id = :e AND t.projection = 'content' AND r.state = ANY(:adopted) "
    "ORDER BY t.run_id, t.version DESC"
)


async def adopted_run_traces(tenant: TenantContext, engagement_id: UUID) -> list[AdoptedTrace]:
    """A-07's archive hook (AUD-25): each adopted run's newest frozen content trace."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(_ADOPTED, {"e": engagement_id, "adopted": sorted(ADOPTED)})
        ).all()
    return [
        AdoptedTrace(r.run_id, r.run_number, int(r.version), r.body_sha256)
        for r in sorted(rows, key=lambda r: (r.run_number or 0, str(r.run_id)))
    ]


# --- the 30-day prune ------------------------------------------------------------------------


async def prune_firm(tenant_id: UUID) -> int:
    """Every `run_events` row of one firm older than 30 days, in batches, audited once."""
    tenant = TenantContext(tenant_id, "system", PRUNE_ACTOR)
    total = 0
    while True:
        try:
            async with uow(tenant) as tx:
                gone = int(
                    cast(
                        int,
                        await tx.session.scalar(
                            text("SELECT prune_run_events(:batch)"), {"batch": PRUNE_BATCH}
                        ),
                    )
                )
                if gone:
                    tx.record(
                        "run_events.pruned",
                        target=Target("firm", tenant_id),
                        after=Ref(count=gone),
                    )
        except MissingAuditEvent:
            gone = 0  # nothing was old enough
        total += gone
        if gone < PRUNE_BATCH:
            return total


@activity.defn(name="agents.run_events.prune")
async def prune_run_events_activity() -> int:
    from abacus.modules.identity.api import firm_tenant_ids

    total = 0
    for tenant in await firm_tenant_ids():
        try:
            total += await prune_firm(tenant)
        except Exception as exc:  # one firm failing does not stop the others
            _log.error("run_events.prune_failed", tenant_id=str(tenant), error=type(exc).__name__)
    _log.info("run_events.pruned", count=total)
    return total


PRUNE_ACTIVITIES: Final = (prune_run_events_activity,)
PRUNE_SCHEDULES: Final = (
    PlatformSchedule(
        id=PRUNE_ID,
        workflow=RunEventsPruneWorkflow,
        every=timedelta(days=1),
        note="SPEC-647 §3.9 AC-RR2: run_events older than 30 days (P-10-T44)",
    ),
)
