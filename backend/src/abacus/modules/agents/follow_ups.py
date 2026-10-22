"""Overdue reminders and the team digest (SPEC-027 P-4, P-5; TASK-051). PROTECTED.

Deterministic: an item past its due date (its own, else its list's) and still open or sent back is
reminded on the first business-day tick after it's due, then every 3 business days, at most 3 times
for that due date. A changed due date starts the sequence again. One email per contact per tick,
listing their items; the item's client assignee, else the engagement's client admins.

The agent only drafts (TASK-104; the plan's DEC-74, P-06-T14): a person reads the follow-up and
sends it, with ten seconds to undo, at every autonomy level. A person can also draft follow-ups for
everything overdue now (`draft_now`). Nothing client-facing happens before the engagement is open
(SPEC-025).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Target, uow
from abacus.modules.agents.events import AgentDigest, FollowUpsDrafted
from abacus.modules.agents.repository import (
    drafted_item_ids,
    follow_up_history,
    insert_follow_up,
)
from abacus.modules.engagements.api import EngagementNotOpen, require_open
from abacus.modules.identity.api import client_admins
from abacus.modules.requests.api import OverdueItem, overdue_for

CADENCE: Final = 3  # business days between reminders of an item
MAX_PER_ITEM: Final = 3
TICK_AT: Final = time(9, 0)


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


def today_in(zone: str, now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).astimezone(ZoneInfo(zone)).date()


@dataclass(frozen=True)
class Sent:
    count: int
    last_on: date | None


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


@dataclass(frozen=True)
class Outcome:
    overdue: int
    sent: int = 0
    drafted: int = 0
    reason: str | None = None  # why nothing client-facing happened


async def chase_overdue(
    tenant: TenantContext, engagement_id: UUID, zone: str, tick_id: UUID
) -> Outcome:
    """P-4 for one tick, then P-5's digest event."""
    today = today_in(zone)
    overdue = await overdue_for(tenant, engagement_id, today)
    if not overdue:
        return Outcome(0)
    try:
        await require_open(tenant, engagement_id)
    except EngagementNotOpen:
        return await _digest(tenant, engagement_id, Outcome(len(overdue), reason="not_open"))
    async with tenant_session(tenant) as session:
        history = await follow_up_history(session, [i.id for i in overdue])
    batches = plan(overdue, history, await client_admins(tenant, engagement_id), today, zone)
    if not batches:
        return await _digest(tenant, engagement_id, Outcome(len(overdue), reason="not_due"))
    drafted = await _draft(tenant, engagement_id, batches)
    return await _digest(tenant, engagement_id, Outcome(len(overdue), drafted=drafted))


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
            tx.record("reminder.drafted", target=Target("reminder", follow_up_id))
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
    today = today_in(zone)
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
