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

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final
from uuid import UUID
from zoneinfo import ZoneInfo

from abacus.kernel.clock import now
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Target, uow
from abacus.modules.agents.events import AgentDigest, FollowUpLimitReached, FollowUpsDrafted
from abacus.modules.agents.repository import (
    drafted_item_ids,
    follow_up_history,
    insert_follow_up,
)
from abacus.modules.communications.api import (
    FollowUpPolicy,
    RecipientRef,
    SendScope,
    SystemSendContext,
    engagement_display_name,
    follow_up_policy,
    next_send_on,
    scheduled_send_enabled,
    send_templated,
)
from abacus.modules.engagements.api import EngagementNotOpen, require_open
from abacus.modules.identity.api import client_admins, firm_name, names_of
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


def first_tick_on_or_after(day: date) -> date:
    """The tick runs on business days only: the first one on or after `day`."""
    while not business_day(day):
        day += timedelta(days=1)
    return day


def next_sequence_by_policy(
    due_on: date, sent: Sent, today: date, policy: FollowUpPolicy
) -> int | None:
    """R-01-T24: which reminder is due today under the firm's policy (or the binder's
    override), or None. The first goes on the first tick after the due date; each next one
    `cadence_days` after the last, moved off a weekend when `weekdays_only`."""
    if today <= due_on or sent.count >= policy.max_reminders:
        return None
    if sent.count == 0 or sent.last_on is None:
        return 1
    due, _ = next_send_on(sent.last_on, policy)
    return sent.count + 1 if today >= due else None


def limit_reached_today(sent: Sent, today: date, policy: FollowUpPolicy) -> bool:
    """The maximum was reached and today is the tick a further reminder would have been due
    on: the one day `follow_up.limit_reached` is raised (DEC-564)."""
    if sent.count < policy.max_reminders or sent.last_on is None:
        return False
    due, _ = next_send_on(sent.last_on, policy)
    return first_tick_on_or_after(due) == today


@dataclass(frozen=True)
class PolicyPlan:
    batches: dict[UUID, list[tuple[OverdueItem, int]]]
    limits: tuple[tuple[UUID, UUID], ...]  # (binder, recipient), once each


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
    limits: dict[tuple[UUID, UUID], None] = {}
    for item in overdue:
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
                    limits[(item.binder_id, recipient)] = None
            continue
        sequence = next_sequence_by_policy(item.due_on, sent, today, policy)
        if sequence is None:
            continue
        for recipient in recipients:
            batches[recipient].append((item, sequence))
    return PolicyPlan(dict(batches), tuple(limits))


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
    if planned.limits:
        async with uow(tenant) as tx:
            for binder_id, recipient in planned.limits:
                tx.emit(
                    FollowUpLimitReached(
                        engagement_id=engagement_id, binder_id=binder_id, contact_id=recipient
                    )
                )
            tx.record("follow_up.limit_reached", target=Target("engagement", engagement_id))
    if not planned.batches:
        return await _digest(tenant, engagement_id, Outcome(len(overdue), reason="not_due"))
    if firm.mode == "send_on_schedule" and await scheduled_send_enabled(tenant):
        sent = await _send_scheduled(tenant, engagement_id, planned.batches)
        return await _digest(tenant, engagement_id, Outcome(len(overdue), sent=sent))
    drafted = await _draft(tenant, engagement_id, planned.batches)
    return await _digest(tenant, engagement_id, Outcome(len(overdue), drafted=drafted))


def _long_date(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def _items_text(titles: Sequence[str]) -> str:
    lines = [" ".join(t.split()) for t in titles if t.strip()]
    shown = lines[:10]
    if len(lines) > 10:
        shown.append(f"and {len(lines) - 10} more")
    return "\n".join(shown)


async def _send_scheduled(
    tenant: TenantContext,
    engagement_id: UUID,
    batches: dict[UUID, list[tuple[OverdueItem, int]]],
) -> int:
    """DEC-74: the system sends the firm's published Reminder (only `send_templated`'s
    scheduled path: the flag, the `reminder` key, a version the firm published, attributed to
    its publisher; the client-mail checks apply). Each send is recorded as a sent follow-up so
    the cadence counts it, audited `follow_up.scheduled_sent` (never `follow_up.sent`, which is
    a person's). The button opens the portal's sign-in, with no token (DEC-566)."""
    system = TenantContext(tenant.tenant_id, "system", "follow_up:scheduled")
    context = SystemSendContext(tenant=system, reason="scheduled_follow_up", policy_version=1)
    firm = await firm_name(tenant.tenant_id)
    work_item = await engagement_display_name(tenant.tenant_id, engagement_id)
    names = await names_of(sorted(batches))
    link = f"{settings().app_base_url.rstrip('/')}/portal"
    sent = 0
    for recipient, items in sorted(batches.items()):
        first = " ".join(names.get(recipient, "").split()).partition(" ")[0]
        values = {
            "client_first_name": first,
            "firm_name": firm,
            "work_item": work_item,
            "open_items": _items_text([i.description for i, _ in items]),
            "due_date": _long_date(min(i.due_on for i, _ in items)),
            "portal_link": link,
            "staff_name": firm,
        }
        key = f"p4:{engagement_id}:{recipient}:" + ",".join(
            f"{i.id}:{i.due_on.isoformat()}:{n}" for i, n in items
        )
        outcome = await send_templated(
            context,
            "reminder",
            RecipientRef("user", recipient),
            values,
            scope=SendScope(engagement_id),
            idempotency_key=hashlib.sha256(key.encode()).hexdigest(),
        )
        if outcome.status != "queued":
            _log.info("follow_up.scheduled_blocked", reason=outcome.blocked_reason)
            continue
        async with uow(system) as tx:
            follow_up_id = await insert_follow_up(
                tx.session,
                tenant_id=tenant.tenant_id,
                engagement_id=engagement_id,
                recipient_user_id=recipient,
                status="sent",
                agent_run_id=None,
                items=[(i.id, i.due_on, n) for i, n in items],
                drafted_by_kind="person",
                template_key="reminder",
            )
            tx.record(
                "follow_up.scheduled_sent",
                target=Target("follow_up", follow_up_id),
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
