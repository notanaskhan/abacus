"""Overdue reminders and the team digest (SPEC-027 P-4, P-5; TASK-051). PROTECTED.

Deterministic: an item past its due date (its own, else its list's) and still open or sent back is
reminded on the first business-day tick after it's due, then every 3 business days, at most 3 times
for that due date. A changed due date starts the sequence again. One email per contact per tick,
listing their items; the item's client assignee, else the engagement's client admins.

The agent only drafts (TASK-104; the plan's DEC-74, P-06-T14): a person reads the follow-up and
sends it, with ten seconds to undo, at every autonomy level. Its matrix row is `deny` and
`follow_up.sent` is human-only in the database, so no path lets the agent send. The P-4 tick
runs as an activity of the `EngagementAgent` workflow, which holds no business state, so this
change needs no `workflow.patched` marker (DEC-220): the recorded histories replay unchanged.
A person can also draft follow-ups for everything overdue now (`draft_now`). Nothing
client-facing happens before the engagement is open (SPEC-025).

R-01-T24 (DEC-74, DEC-563, DEC-564): from `patched("follow_up_policy_v1")` the workflow's tick
carries `{"follow_up_policy": "v1"}` and the tick reads the firm's follow-up policy instead of
`CADENCE` and `MAX_PER_ITEM`: a reminder every `cadence_days` (calendar days from the last one,
off a weekend when `weekdays_only`), at most `max_reminders`, P-06's per-binder override winning;
nothing for an item whose binder the client marked done (`stop_on_binder_done`); once the
maximum is reached, `follow_up.limit_reached` on the business day the next one would have been
due (`notify_preparer_after_max`). With the policy's `send_on_schedule` mode and
`follow_ups.scheduled_send` on, the due reminders are sent by the system from the firm's
published Reminder (`send_templated`, attributed to its publisher) instead of drafted; agent text
never goes out this way. Without the marker (recorded histories) the constants apply unchanged.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError

from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.events import AgentDigest, FollowUpLimitReached, FollowUpsDrafted
from abacus.modules.agents.repository import (
    drafted_item_ids,
    follow_up_history,
    insert_follow_up,
)
from abacus.modules.communications.api import (
    FollowUpPolicy,
    Sent,
    follow_up_policy,
    limit_reached_today,
    next_sequence_by_policy,
    scheduled_send_enabled,
    send_scheduled_reminder,
)
from abacus.modules.engagements.api import EngagementNotOpen, require_open
from abacus.modules.identity.api import client_admins
from abacus.modules.requests.api import OverdueItem, overdue_for

CADENCE: Final = 3  # business days between reminders of an item
MAX_PER_ITEM: Final = 3
MAX_SEQUENCE: Final = 4  # P-06-T14: a person's chase may add one more (POR-20: at most four)
TICK_AT: Final = time(9, 0)
POLICY_MARKER: Final = "follow_up_policy"  # the tick event's payload key (R-01-T24)
POLICY_V1: Final = "v1"
_log = get_logger(__name__)


def business_day(day: date) -> bool:
    return day.weekday() < 5  # holidays aren't modelled in v1


def business_days_between(earlier: date, later: date) -> int:
    """Business days after `earlier`, up to and including `later`."""
    count, day = 0, earlier
    while day < later:
        day += timedelta(days=1)
        count += business_day(day)
    return count


def seconds_to_next_tick(now: datetime, zone: str) -> int:
    """Until the next 09:00 on a business day in the firm's zone, strictly after `now`."""
    local = now.astimezone(ZoneInfo(zone))
    day = local.date()
    while True:
        at = datetime.combine(day, TICK_AT, tzinfo=ZoneInfo(zone))
        if at > local and business_day(day):
            return max(1, int((at - local).total_seconds()))
        day += timedelta(days=1)


def today_in(zone: str, at: datetime) -> date:
    return at.astimezone(ZoneInfo(zone)).date()


def next_sequence(due_on: date, sent: Sent, today: date) -> int | None:
    """Which reminder this item is due today (1-3), or None. `sent` counts only reminders for this
    due date that weren't dismissed."""
    if today <= due_on or sent.count >= MAX_PER_ITEM:
        return None
    if sent.count == 0 or sent.last_on is None:
        return 1
    return sent.count + 1 if business_days_between(sent.last_on, today) >= CADENCE else None


def plan(
    overdue: Sequence[OverdueItem],
    history: Sequence[tuple[UUID, date, int, datetime]],
    admins: Sequence[UUID],
    today: date,
    zone: str,
) -> dict[UUID, list[tuple[OverdueItem, int]]]:
    """Recipient -> the items (and their sequence) to remind them about today."""
    sent: dict[UUID, Sent] = {}
    for item in overdue:
        rows = [(n, at) for i, d, n, at in history if i == item.id and d == item.due_on]
        last = max((at for _, at in rows), default=None)
        sent[item.id] = Sent(len(rows), today_in(zone, last) if last is not None else None)
    batches: dict[UUID, list[tuple[OverdueItem, int]]] = defaultdict(list)
    for item in overdue:
        sequence = next_sequence(item.due_on, sent[item.id], today)
        if sequence is None:
            continue
        for recipient in (
            [item.client_assignee_user_id] if item.client_assignee_user_id else admins
        ):
            batches[recipient].append((item, sequence))
    return dict(batches)


async def reminder_history_of(
    tenant: TenantContext, item_ids: Sequence[UUID]
) -> Sequence[tuple[UUID, date, int, datetime]]:
    """What communications checks a scheduled Reminder's sequence against (review M-a)."""
    async with tenant_session(tenant) as session:
        return await follow_up_history(session, item_ids)


@dataclass(frozen=True)
class PolicyPlan:
    batches: dict[UUID, list[tuple[OverdueItem, int]]]
    # (binder, recipient, the last reminder's date), once each: the limit's dedupe key (L2).
    limits: tuple[tuple[UUID, UUID, date], ...]


def plan_by_policy(
    overdue: Sequence[OverdueItem],
    history: Sequence[tuple[UUID, date, int, datetime]],
    admins: Sequence[UUID],
    today: date,
    zone: str,
    firm: FollowUpPolicy,
) -> PolicyPlan:
    """`plan` under the firm's policy, each binder's override winning (R-01-T24)."""
    batches: dict[UUID, list[tuple[OverdueItem, int]]] = defaultdict(list)
    limits: dict[tuple[UUID, UUID], date] = {}
    for item in overdue:
        if not item.sendable:
            continue  # security review H1: internal, deleted, or not in an open Published binder
        policy = firm.overridden(item.binder_override)
        if policy.stop_on_binder_done and item.binder_marked_done:
            continue  # the client marked the binder done: no further reminder
        rows = [(n, at) for i, d, n, at in history if i == item.id and d == item.due_on]
        last = max((at for _, at in rows), default=None)
        sent = Sent(len(rows), today_in(zone, last) if last is not None else None)
        recipients = [item.client_assignee_user_id] if item.client_assignee_user_id else admins
        if limit_reached_today(sent, today, policy):
            if policy.notify_preparer_after_max and item.binder_id is not None:
                for recipient in recipients:
                    key = (item.binder_id, recipient)
                    last_on = sent.last_on or today
                    limits[key] = max(limits.get(key, last_on), last_on)
            continue
        sequence = next_sequence_by_policy(item.due_on, sent, today, policy)
        if sequence is None:
            continue
        for recipient in recipients:
            batches[recipient].append((item, sequence))
    return PolicyPlan(dict(batches), tuple((b, r, d) for (b, r), d in limits.items()))


@dataclass(frozen=True)
class Outcome:
    overdue: int
    sent: int = 0
    drafted: int = 0
    reason: str | None = None  # why nothing client-facing happened


async def chase_overdue(
    tenant: TenantContext,
    engagement_id: UUID,
    zone: str,
    tick_id: UUID,
    *,
    policy_v1: bool = False,
) -> Outcome:
    """P-4 for one tick, then P-5's digest event. `policy_v1`: the tick carried R-01-T24's
    marker, so the firm's follow-up policy applies."""
    today = today_in(zone, await now(tenant))
    overdue = await overdue_for(tenant, engagement_id, today)
    if not overdue:
        return Outcome(0)
    try:
        await require_open(tenant, engagement_id)
    except EngagementNotOpen:
        return await _digest(tenant, engagement_id, Outcome(len(overdue), reason="not_open"))
    async with tenant_session(tenant) as session:
        history = await follow_up_history(session, [i.id for i in overdue])
    admins = await client_admins(tenant, engagement_id)
    if policy_v1:
        return await _chase_by_policy(tenant, engagement_id, overdue, history, admins, today, zone)
    batches = plan(overdue, history, admins, today, zone)
    if not batches:
        return await _digest(tenant, engagement_id, Outcome(len(overdue), reason="not_due"))
    drafted = await _draft(tenant, engagement_id, batches)
    return await _digest(tenant, engagement_id, Outcome(len(overdue), drafted=drafted))


async def _chase_by_policy(
    tenant: TenantContext,
    engagement_id: UUID,
    overdue: Sequence[OverdueItem],
    history: Sequence[tuple[UUID, date, int, datetime]],
    admins: Sequence[UUID],
    today: date,
    zone: str,
) -> Outcome:
    firm = await follow_up_policy(tenant)
    planned = plan_by_policy(overdue, history, admins, today, zone, firm)
    for binder_id, recipient, last_on in planned.limits:
        await _limit_reached(tenant, engagement_id, binder_id, recipient, last_on)
    if not planned.batches:
        return await _digest(tenant, engagement_id, Outcome(len(overdue), reason="not_due"))
    if firm.mode == "send_on_schedule" and await scheduled_send_enabled(tenant):
        sent = await _send_scheduled(tenant, engagement_id, planned.batches)
        return await _digest(tenant, engagement_id, Outcome(len(overdue), sent=sent))
    drafted = await _draft(tenant, engagement_id, planned.batches)
    return await _digest(tenant, engagement_id, Outcome(len(overdue), drafted=drafted))


_LIMIT_NAMESPACE: Final = UUID("5b0f2c4e-9d61-4a8e-8c3b-1f24d0a7e624")


async def _limit_reached(
    tenant: TenantContext, engagement_id: UUID, binder_id: UUID, recipient: UUID, last_on: date
) -> None:
    """Security review L2: the event's id derives from the binder, the recipient and the last
    reminder's date, so a retried tick raises it once (a second insert of the same id is a
    unique violation, and nothing is written)."""
    event_id = uuid5(_LIMIT_NAMESPACE, f"{binder_id}:{recipient}:{last_on.isoformat()}")
    try:
        async with uow(tenant) as tx:
            tx.emit(
                FollowUpLimitReached(
                    event_id=event_id,
                    engagement_id=engagement_id,
                    binder_id=binder_id,
                    contact_id=recipient,
                )
            )
            tx.record(
                "follow_up.limit_reached",
                target=Target("engagement", engagement_id),
                after=Ref(binder_id=binder_id, event_id=event_id),
            )
    except IntegrityError:
        _log.info("follow_up.limit_already_raised", binder_id=binder_id)


async def _send_scheduled(
    tenant: TenantContext,
    engagement_id: UUID,
    batches: dict[UUID, list[tuple[OverdueItem, int]]],
) -> int:
    """DEC-74, DEC-568: the tick only asks communications to send the firm's Reminder for each
    batch (identifiers only); communications re-reads the requests, checks the policy, the flag
    and the key, and builds the words itself. What it sent is recorded as a sent follow-up so the
    cadence counts it, `drafted_by_kind = 'system'` (0222), audited `follow_up.scheduled_sent`
    (never `follow_up.sent`, which is a person's)."""
    sent = 0
    for recipient, items in sorted(batches.items()):
        done = await send_scheduled_reminder(
            tenant.tenant_id,
            engagement_id,
            recipient,
            [(i.id, i.due_on, n) for i, n in items],
        )
        if done is None:
            continue
        if done.outcome.status != "queued":
            _log.info("follow_up.scheduled_blocked", reason=done.outcome.blocked_reason)
            continue
        async with uow(tenant) as tx:
            follow_up_id = await insert_follow_up(
                tx.session,
                tenant_id=tenant.tenant_id,
                engagement_id=engagement_id,
                recipient_user_id=recipient,
                status="sent",
                agent_run_id=None,
                items=list(done.items),
                drafted_by_kind="system",
                template_key="reminder",
            )
            tx.record(
                "follow_up.scheduled_sent",
                target=Target("follow_up", follow_up_id),
                after=Ref(message_id=done.outcome.message_id),
            )
        sent += 1
    return sent


async def _draft(
    tenant: TenantContext, engagement_id: UUID, batches: dict[UUID, list[tuple[OverdueItem, int]]]
) -> int:
    async with uow(tenant) as tx:
        for recipient, items in batches.items():
            follow_up_id = await insert_follow_up(
                tx.session,
                tenant_id=tenant.tenant_id,
                engagement_id=engagement_id,
                recipient_user_id=recipient,
                status="drafted",
                agent_run_id=None,
                items=[(i.id, i.due_on, n) for i, n in items],
            )
            tx.record("follow_up.drafted", target=Target("follow_up", follow_up_id))
        tx.emit(FollowUpsDrafted(engagement_id=engagement_id, count=len(batches)))
    return len(batches)


async def _digest(tenant: TenantContext, engagement_id: UUID, outcome: Outcome) -> Outcome:
    """P-5: the team hears about overdue items once a day, in the app."""
    if outcome.overdue:
        async with uow(tenant) as tx:
            tx.emit(
                AgentDigest(
                    engagement_id=engagement_id,
                    overdue=outcome.overdue,
                    sent=outcome.sent,
                    drafted=outcome.drafted,
                )
            )
            tx.record("agent.digest", target=Target("engagement", engagement_id))
    return outcome


async def draft_now(tenant: TenantContext, engagement_id: UUID, zone: str) -> int:
    """TASK-104: a person asks for follow-ups on everything overdue now, one draft per contact,
    outside the cadence. Items already in a waiting draft, or reminded three times for this due
    date, are left out."""
    today = today_in(zone, await now(tenant))
    overdue = await overdue_for(tenant, engagement_id, today)
    if not overdue:
        return 0
    await require_open(tenant, engagement_id)
    async with tenant_session(tenant) as session:
        history = await follow_up_history(session, [i.id for i in overdue])
        waiting = await drafted_item_ids(session, engagement_id)
    admins = await client_admins(tenant, engagement_id)
    batches: dict[UUID, list[tuple[OverdueItem, int]]] = defaultdict(list)
    for item in overdue:
        if item.id in waiting:
            continue
        sent = sum(1 for i, d, _n, _at in history if i == item.id and d == item.due_on)
        if sent >= MAX_PER_ITEM:
            continue
        for recipient in (
            [item.client_assignee_user_id] if item.client_assignee_user_id else admins
        ):
            batches[recipient].append((item, sent + 1))
    return await _draft(tenant, engagement_id, dict(batches)) if batches else 0
