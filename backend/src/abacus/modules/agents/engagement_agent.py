"""The engagement agent v1: deterministic policies (SPEC-027; TASK-050; ADR-058, ADR-060).
PROTECTED.

No model calls. The platform retrieves and suggests by rule; agents screen and propose. Every
policy reads fresh and checks, in order: the firm's pause, the engagement's pause, archived, the
feature flag, then its own rule. Each writes one feed row (`agent_activity`), once per event.

- P-0 lifecycle: started, paused, resumed (resume screens what arrived while paused, once, and
  runs the retrieval rule once).
- P-1 screen: new evidence starts the screener, as before (same workflow ID and initiator); not at
  Advise.
- P-2 retrieve: the platform's rule-based retrieval (`connections.auto_retrieve`), with its reason.
- P-3 match: records how many items the matching rule suggested for a waiting inbox file; it never
  assigns.

In TASK-050 the agent starts work that already runs under a person (D2); its own `AgentContext`
under the engagement partner arrives with reminders (TASK-051).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4, uuid5

from temporalio import activity

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import signal_with_start
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import OutboxEvent, Target, uow
from abacus.modules.agents.engagement_agent_workflow import HANDLE, NEXT_TICK, EngagementAgent
from abacus.modules.agents.models import AgentActivity
from abacus.modules.agents.reminders import remind, seconds_to_next_tick
from abacus.modules.agents.repository import (
    activity_page,
    agent_state,
    drafted_reminders,
    last_resume_check,
    lock_reminder,
    record_activity,
    screenings_skipped_while_paused,
    set_agent_paused,
    set_self_paused,
    settle_reminder,
)
from abacus.modules.agents.workflow_types import (
    AgentEvent,
    AgentInput,
    HandleInput,
    HandleResult,
    NextTickInput,
    ScreeningInput,
)
from abacus.modules.communications.api import send_reminder
from abacus.modules.engagements.api import (
    get_ref,
    is_archived,
    lock_ref,
    open_engagements,
    run_auto_retrieval,
)
from abacus.modules.identity.api import (
    AuthContext,
    agents_paused,
    authorise,
    autonomy_level,
    earliest_partner,
    firm_time_zone,
    names_of,
)
from abacus.modules.requests.api import overdue_for

VERSION: Final = 1
RESUMED: Final = "agent.resumed"
TICK: Final = "agent.tick"
STARTED: Final = "agent.started"  # started by the platform (existing engagements, Q7)
FIRM_RESUMED: Final = "firm.agents_resumed"
REPLAY_WINDOW: Final = timedelta(days=30)
_SYSTEM: Final = "agents.engagement_agent"
_log = get_logger(__name__)


def agent_id(tenant_id: UUID, engagement_id: UUID) -> str:
    return f"engagement-agent:{tenant_id}:{engagement_id}"


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", _SYSTEM)


async def agent_on(tenant_id: UUID) -> bool:
    """The per-firm flag (D3): off, today's direct handlers run as before."""
    return await flag_enabled(_system(tenant_id), _flags.ENGAGEMENT_AGENT_ENABLED)


async def signal_agent(
    tenant_id: UUID, engagement_id: UUID, event_type: str, event_id: UUID, payload: dict[str, str]
) -> None:
    await signal_with_start(
        EngagementAgent,
        AgentInput(str(tenant_id), str(engagement_id)),
        id=agent_id(tenant_id, engagement_id),
        signal="event",
        payload=AgentEvent(event_type, str(event_id), payload),
    )


# --- From the outbox relay -------------------------------------------------------------------


async def to_agent(event: OutboxEvent) -> None:
    """Route an engagement's domain event to its agent (starting it if needed), when the firm's
    agent is on. Off, the modules' own handlers act as before."""
    if not await agent_on(event.tenant_id):
        return
    engagement = event.payload.get("engagement_id")
    if engagement is None:
        return
    payload = {k: str(v) for k, v in event.payload.items() if v is not None}
    await signal_agent(
        event.tenant_id, UUID(str(engagement)), event.event_type, event.event_id, payload
    )


async def start_agents(tenant_id: UUID) -> int:
    """SPEC-027 Q7 (TASK-051): every open engagement of a firm with the agent on gets its agent
    (idempotent: a running agent just records it). Returns how many were signalled."""
    if not await agent_on(tenant_id):
        return 0
    engagements = await open_engagements(_system(tenant_id))
    for engagement_id in engagements:
        await signal_agent(tenant_id, engagement_id, STARTED, uuid5(engagement_id, STARTED), {})
    return len(engagements)


async def firm_resumed(event: OutboxEvent) -> None:
    """The firm switch was turned back on: every open engagement's agent looks once."""
    if not await agent_on(event.tenant_id):
        return
    for engagement_id in await open_engagements(_system(event.tenant_id)):
        await signal_agent(event.tenant_id, engagement_id, FIRM_RESUMED, event.event_id, {})


# --- The activity: one event, one policy -----------------------------------------------------


@dataclass(frozen=True)
class _Row:
    policy: str
    action: str
    outcome: str
    reason: str | None = None
    record_type: str | None = None
    record_id: UUID | None = None
    item_count: int | None = None
    for_user: UUID | None = None


async def _write(tenant: TenantContext, engagement_id: UUID, source: UUID, row: _Row) -> bool:
    async with uow(tenant) as tx:
        written = await record_activity(
            tx.session,
            tenant_id=tenant.tenant_id,
            engagement_id=engagement_id,
            policy=row.policy,
            policy_version=VERSION,
            action=row.action,
            outcome=row.outcome,
            reason=row.reason,
            record_type=row.record_type,
            record_id=row.record_id,
            item_count=row.item_count,
            for_user=row.for_user,
            source_event_id=source,
        )
        tx.record(
            "agent.activity",
            target=Target("engagement", engagement_id),
        )
    return written


def _uuid(payload: dict[str, str], key: str) -> UUID | None:
    value = payload.get(key)
    return UUID(value) if value else None


async def _paused(tenant: TenantContext, engagement_id: UUID) -> str | None:
    if await agents_paused(tenant) is not None:
        return "firm_paused"
    async with tenant_session(tenant) as session:
        state = await agent_state(session, engagement_id)
    if state is not None and state.paused_at is not None:
        return "paused"
    return "self_paused" if state is not None and state.self_paused_reason else None


async def _self_pause(tenant: TenantContext, engagement_id: UUID) -> _Row | None:
    """SPEC-027 AC-8: with no active partner to act for, the agent pauses itself; it resumes on
    its own when there's one again. The row to record when that changes, else None."""
    partner = await earliest_partner(tenant, engagement_id)
    async with tenant_session(tenant) as session:
        state = await agent_state(session, engagement_id)
    paused = state is not None and state.self_paused_reason is not None
    if (partner is None) == paused:
        return None
    async with uow(tenant) as tx:
        await set_self_paused(
            tx.session, tenant.tenant_id, engagement_id, "no_partner" if partner is None else None
        )
        tx.record(
            "engagement_agent.self_paused" if partner is None else "engagement_agent.self_resumed",
            target=Target("engagement", engagement_id),
        )
    if partner is None:
        return _Row("P-0", "agent.self_paused", "done", "no_partner")
    return _Row("P-0", "agent.self_resumed", "done")


async def _tick(tenant: TenantContext, engagement_id: UUID, tick_id: UUID) -> list[_Row]:
    """The daily tick: P-2's daily retrieval, P-4 reminders, P-5 digest (SPEC-027)."""
    rows: list[_Row] = []
    changed = await _self_pause(tenant, engagement_id)
    if changed is not None:
        rows.append(changed)
    paused = await _paused(tenant, engagement_id)
    if paused is not None:
        return [*rows, _Row("P-0", "agent.tick", "skipped", paused)]
    found = await run_auto_retrieval(tenant.tenant_id, engagement_id, None)
    if found == "done":
        rows.append(_Row("P-2", "retrieval.start", "done"))
    outcome = await remind(tenant, engagement_id, await firm_time_zone(tenant), tick_id)
    if outcome.sent:
        rows.append(_Row("P-4", "reminders.sent", "done", None, None, None, outcome.sent))
    elif outcome.drafted:
        rows.append(_Row("P-4", "reminders.drafted", "done", None, None, None, outcome.drafted))
    elif outcome.reason in ("not_open", "no_partner"):
        rows.append(_Row("P-4", "reminders.check", "skipped", outcome.reason))
    if outcome.overdue and outcome.reason != "no_partner":
        rows.append(_Row("P-5", "digest.sent", "done", None, None, None, outcome.overdue))
    return rows


async def _screen(
    tenant: TenantContext, version: UUID, source: UUID, requested_by: UUID | None
) -> None:
    from abacus.modules.agents.screenings import (  # screenings routes events here
        dispatch_screening,
    )

    await dispatch_screening(
        ScreeningInput(
            str(tenant.tenant_id),
            str(version),
            str(source),
            str(requested_by) if requested_by is not None else None,
        )
    )


async def apply_policy(given: HandleInput) -> tuple[list[_Row], bool]:
    """The rows to record for one event, after doing what the policy says, and whether the agent
    should end. Reads fresh; every outcome has a reason when nothing was done."""
    tenant = _system(UUID(given.tenant_id))
    engagement_id = UUID(given.engagement_id)
    payload = given.payload
    archived = await is_archived(tenant, engagement_id)
    if archived is None or archived:
        return [], True
    kind = given.event_type
    if kind in ("engagement.created", STARTED):
        return [_Row("P-0", "agent.started", "done")], False
    if kind == TICK:
        return await _tick(tenant, engagement_id, UUID(given.event_id)), False
    if kind == "due_dates.changed":
        return [_Row("P-4", "reminders.restarted", "done")], False
    paused = await _paused(tenant, engagement_id)
    if kind in (RESUMED, FIRM_RESUMED):
        if paused is not None:
            return [_Row("P-0", "agent.resume_checked", "skipped", paused)], False
        return await _resume(tenant, engagement_id), False
    if kind == "evidence_version.created":
        version = _uuid(payload, "evidence_version_id")
        who = _uuid(payload, "requested_by")
        base = _Row(
            "P-1", "screening.start", "skipped", None, "evidence_version", version, None, who
        )
        if paused is not None:
            return [_replace(base, reason=paused)], False
        if not await agent_on(tenant.tenant_id):
            return [_replace(base, reason="agent_off")], False
        if await autonomy_level(tenant.tenant_id) < 1:
            return [_replace(base, reason="advise")], False
        if version is None:
            return [_replace(base, outcome="failed", reason="malformed_event")], False
        await _screen(tenant, version, UUID(given.event_id), who)
        return [_replace(base, outcome="done")], False
    if kind in ("connection.created", "request_item.classified"):
        item = _uuid(payload, "request_item_id") if kind == "request_item.classified" else None
        base = _Row(
            "P-2", "retrieval.start", "skipped", None, "request_item" if item else None, item
        )
        if paused is not None:
            return [_replace(base, reason=paused)], False
        found = await run_auto_retrieval(tenant.tenant_id, engagement_id, item)
        if found == "done":
            return [_replace(base, outcome="done")], False
        reason = "auto_retrieval_off" if found == "flag_off" else found
        return [_replace(base, reason=reason)], False
    if kind == "inbox_file.added":
        file_id = _uuid(payload, "inbox_file_id")
        count = int(payload.get("suggestions", "0"))
        base = _Row("P-3", "match.suggested", "done", None, "inbox_file", file_id, count)
        if paused is not None:
            return [_replace(base, outcome="skipped", reason=paused)], False
        return [base], False
    return [], False


def _replace(row: _Row, **changes: object) -> _Row:
    return _Row(**{**row.__dict__, **changes})  # pyright: ignore[reportArgumentType] -- the same fields


async def _skipped_screenings(tenant: TenantContext, engagement_id: UUID) -> list[AgentActivity]:
    async with tenant_session(tenant) as session:
        since = datetime.now(UTC) - REPLAY_WINDOW
        last = await last_resume_check(session, engagement_id)
        return list(
            await screenings_skipped_while_paused(
                session, engagement_id, max(since, last) if last is not None else since
            )
        )


async def _resume(tenant: TenantContext, engagement_id: UUID) -> list[_Row]:
    """AC-6: evidence that arrived while paused is screened once; retrieval runs once."""
    rows = [_Row("P-0", "agent.resume_checked", "done")]
    skipped = await _skipped_screenings(tenant, engagement_id)
    if skipped and await autonomy_level(tenant.tenant_id) >= 1:
        for row in skipped:
            if row.record_id is None or row.source_event_id is None:
                continue
            await _screen(tenant, row.record_id, row.source_event_id, row.for_user)
        rows.append(_Row("P-1", "screening.replayed", "done", None, None, None, len(skipped)))
    found = await run_auto_retrieval(tenant.tenant_id, engagement_id, None)
    rows.append(
        _Row(
            "P-2",
            "retrieval.start",
            "done" if found == "done" else "skipped",
            None if found == "done" else ("auto_retrieval_off" if found == "flag_off" else found),
        )
    )
    return rows


@activity.defn(name=NEXT_TICK)
async def next_tick(given: NextTickInput) -> int:
    """Seconds until the next 09:00 business day in the firm's time zone (SPEC-027 Q3)."""
    zone = await firm_time_zone(_system(UUID(given.tenant_id)))
    return seconds_to_next_tick(datetime.now(UTC), zone)


@activity.defn(name=HANDLE)
async def handle(given: HandleInput) -> HandleResult:
    rows, end = await apply_policy(given)
    tenant = _system(UUID(given.tenant_id))
    engagement_id = UUID(given.engagement_id)
    source = UUID(given.event_id)
    for n, row in enumerate(rows):
        # One row per policy per event; a resume's several rows get their own derived ids.
        await _write(
            tenant,
            engagement_id,
            source if n == 0 else uuid5(source, row.policy + row.action),
            row,
        )
    return HandleResult(end)


# --- People: pause, resume, the feed ---------------------------------------------------------


@dataclass(frozen=True)
class AgentView:
    enabled: bool
    paused_at: datetime | None
    paused_by: str | None
    reason: str | None
    firm_paused_at: datetime | None


async def agent_view(ctx: AuthContext, engagement_id: UUID) -> AgentView:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "activity.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        state = await agent_state(session, engagement_id)
    paused_by = state.paused_by if state is not None else None
    names = await names_of([paused_by]) if paused_by is not None else {}
    return AgentView(
        await agent_on(ctx.tenant_id),
        state.paused_at if state is not None else None,
        names.get(paused_by, "") if paused_by is not None else None,
        state.reason if state is not None else None,
        await agents_paused(ctx.tenant),
    )


async def set_paused(
    ctx: AuthContext, engagement_id: UUID, *, paused: bool, reason: str | None = None
) -> AgentView:
    """AC-6: the engagement's switch (partner or manager). Resuming asks the agent to look once."""
    kept = (reason or "").strip()[:300] or None
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "agent.pause", ref.resource())
        await set_agent_paused(
            tx.session,
            ctx.tenant_id,
            engagement_id,
            ctx.user_id if paused else None,
            kept if paused else None,
        )
        await record_activity(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            policy="P-0",
            policy_version=VERSION,
            action="agent.paused" if paused else "agent.resumed",
            outcome="done",
            for_user=ctx.user_id,
        )
        tx.record(
            "engagement_agent.paused" if paused else "engagement_agent.resumed",
            target=Target("engagement", engagement_id),
        )
    if not paused and await agent_on(ctx.tenant_id):
        await signal_agent(ctx.tenant_id, engagement_id, RESUMED, uuid4(), {})
    return await agent_view(ctx, engagement_id)


async def activity_feed(
    ctx: AuthContext, engagement_id: UUID, before: datetime | None, limit: int
) -> list[AgentActivity]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "activity.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        return list(await activity_page(session, ctx, engagement_id, before, limit))


# --- Drafted reminders (SPEC-027 AC-4: Advise) ---------------------------------------------------


@dataclass(frozen=True)
class DraftView:
    id: UUID
    recipient_user_id: UUID
    recipient_name: str
    items: list[tuple[UUID, str]]
    created_at: datetime


async def drafts(ctx: AuthContext, engagement_id: UUID) -> list[DraftView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "follow_up.draft", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        rows = await drafted_reminders(session, engagement_id)
    names = await names_of(sorted({r.recipient_user_id for r, _ in rows}, key=str))
    overdue = {
        i.id: i.description
        for i in await overdue_for(_system(ctx.tenant_id), engagement_id, date.max)
    }
    return [
        DraftView(
            r.id,
            r.recipient_user_id,
            names.get(r.recipient_user_id, ""),
            [(i, overdue[i]) for i in items if i in overdue],
            r.created_at,
        )
        for r, items in rows
    ]


class DraftGone(DomainConflict):
    code = "draft_not_waiting"


async def settle_draft(
    ctx: AuthContext,
    engagement_id: UUID,
    reminder_id: UUID,
    *,
    send: bool,
    note: str | None = None,
) -> None:
    """A person sends (optionally with a note) or dismisses a drafted reminder. Items no longer
    overdue are left out; with none left it's dismissed."""
    kept = (note or "").strip()[:500] or None
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "follow_up.send", ref.resource())
        draft = await lock_reminder(tx.session, engagement_id, reminder_id)
        if draft is None:
            raise NotFound("reminder")
        if draft.status != "drafted":
            raise DraftGone(str(reminder_id))
        found = [d for d in await drafts(ctx, engagement_id) if d.id == reminder_id]
        items = found[0].items if found else []
        outcome = "sent" if send and items else "dismissed"
        await settle_reminder(tx.session, reminder_id, status=outcome, by=ctx.user_id, note=kept)
        tx.record(f"reminder.{outcome}", target=Target("reminder", reminder_id))
    if outcome == "sent":
        await send_reminder(
            ctx, engagement_id, draft.recipient_user_id, [d for _, d in items], kept
        )
