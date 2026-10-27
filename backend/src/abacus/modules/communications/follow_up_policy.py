"""The firm's follow-up policy (R-01-T24; DEC-74, DEC-563; migration 0221).

One row per firm (`follow_up_policies`), or the defaults when there is none: every 7 days, at
most 4, weekdays at 9:00 AM in the recipient's time zone, stop when the client marks the binder
done, tell the preparer after the last one, and a person sends (`draft_for_person`). P-06's
per-binder override (`every_days`, `max`) wins over it, read by the P-4 tick.

- `next_send_at` is the one rule both the GET and the scheduler use: the last send's local date
  in the recipient's zone plus the cadence in calendar days, a Saturday or Sunday moved to the
  Monday when `weekdays_only`, at `send_local_time` in that zone. Until contacts carry their own
  time zone, the recipient's zone is the firm's (DEC-563).
- `save_follow_up_policy` is the only writer: `portal_settings.manage` (firm admin, fresh second
  factor), `expected_version` (0 when there is no row; else the row's `version`; any other is
  409 `stale_version`), audited `follow_up_policy.saved`. R-01-T26's portal-settings publish
  calls it; POR-20 and ADM-10 read the policy.
- `send_on_schedule` sends by itself only while `follow_ups.scheduled_send` is on for the firm
  (`scheduled_send_enabled`); otherwise every reminder is a draft a person sends.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from typing import Final, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise

Mode = Literal["draft_for_person", "send_on_schedule"]
_SATURDAY: Final = 5


@dataclass(frozen=True)
class FollowUpPolicy:
    cadence_days: int = 7
    max_reminders: int = 4
    send_local_time: time = time(9, 0)
    weekdays_only: bool = True
    stop_on_binder_done: bool = True
    notify_preparer_after_max: bool = True
    cc_assigned_preparer: bool = False
    mode: Mode = "draft_for_person"
    version: int = 0  # 0: no row, the defaults

    def overridden(self, override: dict[str, object] | None) -> FollowUpPolicy:
        """P-06's per-binder override wins over the firm's cadence and maximum."""
        if not override:
            return self
        every, most = override.get("every_days"), override.get("max")
        if not isinstance(every, int) or not isinstance(most, int):
            return self
        if not (1 <= every <= 30 and 1 <= most <= 4):
            return self
        return replace(self, cadence_days=every, max_reminders=most)


DEFAULT: Final = FollowUpPolicy()


class FollowUpPolicyStale(DomainConflict):
    code = "stale_version"


@dataclass(frozen=True)
class NextSend:
    next_send_at: datetime
    shifted_from: date | None  # the cadence's own date when a weekend moved it


def next_send_on(last_on: date, policy: FollowUpPolicy) -> tuple[date, date | None]:
    """The day after `last_on` by the cadence, moved off a weekend when `weekdays_only`."""
    due = last_on + timedelta(days=policy.cadence_days)
    if policy.weekdays_only and due.weekday() >= _SATURDAY:
        return due + timedelta(days=7 - due.weekday()), due
    return due, None


def next_send_at(policy: FollowUpPolicy, last_sent_at: datetime, zone: str) -> NextSend:
    """Mon Sep 14, 2026 9:00 AM + 7 days is Mon Sep 21; + 5 days is Sat Sep 19, moved to Mon Sep
    21. The time is `send_local_time` in `zone` (the recipient's; until contacts carry one, the
    firm's), returned in UTC."""
    tz = ZoneInfo(zone)
    day, shifted = next_send_on(last_sent_at.astimezone(tz).date(), policy)
    at = datetime.combine(day, policy.send_local_time, tzinfo=tz)
    return NextSend(at.astimezone(ZoneInfo("UTC")), shifted)


# --- the cadence rule both the tick and the scheduled send apply (security review M-a) ---------


@dataclass(frozen=True)
class Sent:
    count: int
    last_on: date | None


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


def business_day(day: date) -> bool:
    return day.weekday() < _SATURDAY  # holidays aren't modelled in v1


# The reminders already drafted or sent for requests: (request, due date then, sequence, when).
ReminderHistory = Callable[
    [TenantContext, Sequence[UUID]], Awaitable[Sequence[tuple[UUID, date, int, datetime]]]
]
_HISTORY: list[ReminderHistory] = []


def register_reminder_history(provider: ReminderHistory) -> None:
    """The agents module, which keeps the follow-ups, says what was already sent (R-01-T24
    security review M-a): communications checks a scheduled Reminder's sequence against it."""
    _HISTORY[:] = [provider]


async def reminder_history(
    tenant: TenantContext, item_ids: Sequence[UUID]
) -> Sequence[tuple[UUID, date, int, datetime]] | None:
    """None when no provider registered: the caller fails closed."""
    if not _HISTORY:
        return None
    return await _HISTORY[0](tenant, item_ids)


_READ = text(
    "SELECT cadence_days, max_reminders, send_local_time, weekdays_only, stop_on_binder_done, "
    "notify_preparer_after_max, cc_assigned_preparer, mode, version FROM follow_up_policies"
)


async def follow_up_policy(tenant: TenantContext) -> FollowUpPolicy:
    """The firm's policy, or the defaults (no row). Row-level security picks the firm."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_READ)).one_or_none()
    if row is None:
        return DEFAULT
    return FollowUpPolicy(
        cadence_days=row.cadence_days,
        max_reminders=row.max_reminders,
        send_local_time=row.send_local_time,
        weekdays_only=row.weekdays_only,
        stop_on_binder_done=row.stop_on_binder_done,
        notify_preparer_after_max=row.notify_preparer_after_max,
        cc_assigned_preparer=row.cc_assigned_preparer,
        mode=cast(Mode, row.mode),
        version=row.version,
    )


async def read_follow_up_policy(ctx: AuthContext) -> FollowUpPolicy:
    await authorise(ctx, "portal_settings.read", Resource.firm(ctx.tenant_id))
    return await follow_up_policy(ctx.tenant)


def _values(policy: FollowUpPolicy) -> dict[str, object]:
    return {
        "cadence_days": policy.cadence_days,
        "max_reminders": policy.max_reminders,
        "send_local_time": policy.send_local_time,
        "weekdays_only": policy.weekdays_only,
        "stop_on_binder_done": policy.stop_on_binder_done,
        "notify_preparer_after_max": policy.notify_preparer_after_max,
        "cc_assigned_preparer": policy.cc_assigned_preparer,
        "mode": policy.mode,
    }


async def save_follow_up_policy(
    ctx: AuthContext, policy: FollowUpPolicy, expected_version: int
) -> FollowUpPolicy:
    """Write the firm's policy (R-01-T26's portal-settings publish). 409 on a stale version."""
    await authorise(ctx, "portal_settings.manage", Resource.firm(ctx.tenant_id))
    async with uow(ctx.tenant) as tx:
        have = await tx.session.scalar(text("SELECT version FROM follow_up_policies FOR UPDATE"))
        current = int(have) if have is not None else 0
        if expected_version != current:
            raise FollowUpPolicyStale(facts={"version": current})
        values = {**_values(policy), "tenant": ctx.tenant_id, "by": ctx.user_id}
        if have is None:
            await tx.session.execute(
                text(
                    "INSERT INTO follow_up_policies (tenant_id, cadence_days, max_reminders, "
                    "send_local_time, weekdays_only, stop_on_binder_done, "
                    "notify_preparer_after_max, cc_assigned_preparer, mode, updated_by) VALUES "
                    "(:tenant, :cadence_days, :max_reminders, :send_local_time, :weekdays_only, "
                    ":stop_on_binder_done, :notify_preparer_after_max, :cc_assigned_preparer, "
                    ":mode, :by)"
                ),
                values,
            )
        else:
            await tx.session.execute(
                text(
                    "UPDATE follow_up_policies SET cadence_days = :cadence_days, "
                    "max_reminders = :max_reminders, send_local_time = :send_local_time, "
                    "weekdays_only = :weekdays_only, stop_on_binder_done = :stop_on_binder_done, "
                    "notify_preparer_after_max = :notify_preparer_after_max, "
                    "cc_assigned_preparer = :cc_assigned_preparer, mode = :mode, "
                    "version = version + 1, updated_by = :by, updated_at = clock_timestamp() "
                    "WHERE tenant_id = :tenant"
                ),
                values,
            )
        tx.record(
            "follow_up_policy.saved",
            target=Target("follow_up_policy", ctx.tenant_id),
            before=Ref(version=current) if current else None,
            after=Ref(version=current + 1),
        )
    return replace(policy, version=current + 1)
