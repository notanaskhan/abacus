"""The override-rate projection and its reads (Q-05-T07; TASK-8714; DEC-96; DEC-5710).

`record_outcome` is the idempotent outbox consumer: an event that names its agent output
(`agent_key`, `outcome`, and the source it decided) becomes one `agent_output_outcomes` row, keyed
by the event id, so a replayed event changes nothing; an event that names no agent output is not
an agent outcome and is skipped. `rebuild` replays a list of events the same way (the back-fill
command). The reads (`overrides`, `override_reasons`) roll the rows up through
`compute/override_rates.py` with the published AI policy's tolerance.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.practice.compute.override_rates import (
    Outcome,
    OutcomeRow,
    per_agent,
    reasons,
    totals,
)

SOURCE_KINDS: Final = {
    "review_decision.recorded": "review_decision",
    "proposal.decided": "proposal",
    "checkpoint.approved": "checkpoint",
    "checkpoint.rejected": "checkpoint",
    # a held proposed entry's decision has no outcome event yet (`proposed_entry.rejected` and
    # `.approval_decided` carry no agent key): S51 end pass, TASK-8728, carried to S52.
}
OUTCOMES: Final = frozenset({"adopted", "changed", "rejected"})
DEFAULT_TOLERANCE: Final = Decimal(8)  # the AI policy's default until a firm publishes one
WINDOWS: Final = {"30d": 30, "90d": 90, "cycle": 365}

_INSERT = text(
    "INSERT INTO agent_output_outcomes (tenant_id, source_kind, source_id, agent_key, "
    "engagement_id, work_item_id, office_id, service_line, outcome, reason_code, decided_at, "
    "decided_by, source_event_id) VALUES (:t, :kind, :sid, :agent, :e, :w, :o, :line, :outcome, "
    ":reason, :at, :by, :event) ON CONFLICT DO NOTHING"
)


def _uuid(v: object) -> UUID | None:
    try:
        return UUID(str(v)) if v not in (None, "") else None
    except ValueError:
        return None


async def record_outcome(event: OutboxEvent) -> None:
    kind = SOURCE_KINDS.get(event.event_type)
    payload = event.payload
    agent = payload.get("agent_key")
    outcome = payload.get("outcome")
    source = _uuid(payload.get("source_id"))
    if kind is None or not isinstance(agent, str) or outcome not in OUTCOMES or source is None:
        return
    if not isinstance(payload.get("decided_at"), str):
        return  # an outcome is dated by its decision, never by the relay
    tenant = TenantContext(event.tenant_id, "system", "practice:override_outcomes")
    async with tenant_session(tenant) as session, session.begin():
        await session.execute(
            _INSERT,
            {
                "t": event.tenant_id, "kind": kind, "sid": source, "agent": agent,
                "e": _uuid(payload.get("engagement_id")), "w": _uuid(payload.get("work_item_id")),
                "o": _uuid(payload.get("office_id")), "line": payload.get("service_line"),
                "outcome": outcome, "reason": payload.get("reason_code"),
                "at": payload.get("decided_at"),
                "by": _uuid(payload.get("decided_by")), "event": event.event_id,
            },
        )  # fmt: skip


async def rebuild(events: Iterable[OutboxEvent]) -> int:
    """The back-fill: replay decision events into the projection (idempotent by event id)."""
    n = 0
    for e in events:
        await record_outcome(e)
        n += 1
    return n


_ROWS = text(
    "SELECT agent_key, outcome, reason_code FROM agent_output_outcomes "
    "WHERE decided_at >= :since AND (CAST(:office AS uuid) IS NULL OR office_id = :office)"
)


async def _rows(tenant: TenantContext, since: datetime, office: UUID | None) -> list[OutcomeRow]:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_ROWS, {"since": since, "office": office})).all()
    return [OutcomeRow(str(r[0]), cast(Outcome, r[1]), r[2]) for r in found]


async def tolerance(tenant: TenantContext) -> Decimal:
    from abacus.modules.agents.api import effective_ai_policy

    found = await effective_ai_policy(tenant, "audit")
    sections = cast(dict[str, object], getattr(found, "sections", {}) or {})
    governance = cast(dict[str, object], sections.get("governance", {}) or {})
    value = governance.get("override_tolerance_pct")
    return Decimal(str(value)) if value is not None else DEFAULT_TOLERANCE


async def overrides(
    tenant: TenantContext, now: datetime, window: str, office: UUID | None
) -> dict[str, object]:
    days = WINDOWS.get(window, 30)
    rows = await _rows(tenant, now - timedelta(days=days), office)
    tol = await tolerance(tenant)
    outputs, n_over, r = totals(rows)
    agents = per_agent(rows, tol)
    return {
        "window_days": days,
        "tolerance_pct": tol,
        "sample_n": 25,
        "outputs": outputs,
        "overrides": n_over,
        "rate": r,
        "unrated": sum(1 for a in agents if not a.rated),
        "rows": [
            {
                "agent_key": a.agent_key, "label": a.agent_key, "outputs": a.outputs,
                "overrides": a.overrides, "rate": a.rate, "rated": a.rated,
                "above_tolerance": a.above_tolerance,
            }
            for a in agents
        ],
    }  # fmt: skip


async def override_reasons(
    tenant: TenantContext, now: datetime, agent_key: str
) -> list[tuple[str, int]]:
    return reasons(await _rows(tenant, now - timedelta(days=90), None), agent_key)


__all__ = ["SOURCE_KINDS", "override_reasons", "overrides", "rebuild", "record_outcome"]
