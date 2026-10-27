"""R-01-T24 (TASK-1421; DEC-74, DEC-564): the P-4 plan under the firm's follow-up policy: the
cadence and maximum from the policy, P-06's per-binder override winning, nothing for a binder
the client marked done, and `follow_up.limit_reached` once, on the tick a further reminder would
have been due."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from abacus.modules.agents.follow_ups import PolicyPlan, plan_by_policy
from abacus.modules.communications.api import (
    FollowUpPolicy,
    Sent,
    first_tick_on_or_after,
    limit_reached_today,
    next_sequence_by_policy,
)
from abacus.modules.requests.api import OverdueItem

ZONE = "America/Chicago"
DUE = date(2026, 9, 1)
MON_14, FRI_18, MON_21 = date(2026, 9, 14), date(2026, 9, 18), date(2026, 9, 21)
SAT_19 = date(2026, 9, 19)
ADMIN, ASSIGNEE = uuid.uuid4(), uuid.uuid4()
BINDER = uuid.uuid4()
FIVE = FollowUpPolicy(cadence_days=5)


def _item(
    *,
    done: bool = False,
    override: dict[str, object] | None = None,
    binder: uuid.UUID = BINDER,
    sendable: bool = True,
) -> OverdueItem:
    return OverdueItem(
        uuid.uuid4(), "Bank statements", DUE, ASSIGNEE, binder, done, override, sendable
    )


def _sent_at(item: OverdueItem, *days: date) -> list[tuple[uuid.UUID, date, int, datetime]]:
    return [
        (item.id, DUE, n, datetime.combine(d, time(14, 0), tzinfo=UTC))
        for n, d in enumerate(days, start=1)
    ]


def test_ac_five_days_after_mon_sep_14_is_mon_sep_21() -> None:
    assert next_sequence_by_policy(DUE, Sent(1, MON_14), FRI_18, FIVE) is None
    assert next_sequence_by_policy(DUE, Sent(1, MON_14), MON_21, FIVE) == 2
    assert first_tick_on_or_after(SAT_19) == MON_21


def test_the_first_reminder_goes_on_the_first_tick_after_the_due_date() -> None:
    assert next_sequence_by_policy(DUE, Sent(0, None), DUE, FIVE) is None
    assert next_sequence_by_policy(DUE, Sent(0, None), MON_14, FIVE) == 1


def test_ac_a_marked_done_binder_gets_no_further_draft() -> None:
    item = _item(done=True)
    planned = plan_by_policy([item], _sent_at(item, MON_14), [ADMIN], MON_21, ZONE, FIVE)
    assert planned.batches == {} and planned.limits == ()
    # With the firm's stop rule off, the same binder is reminded.
    keep = FollowUpPolicy(cadence_days=5, stop_on_binder_done=False)
    planned = plan_by_policy([item], _sent_at(item, MON_14), [ADMIN], MON_21, ZONE, keep)
    assert planned.batches == {ASSIGNEE: [(item, 2)]}


def test_h1_a_request_no_client_may_be_written_to_about_is_never_planned() -> None:
    item = _item(sendable=False)  # internal, deleted, or not in an open Published binder
    four = _sent_at(item, date(2026, 8, 24), date(2026, 8, 31), date(2026, 9, 8), MON_14)
    assert plan_by_policy([item], [], [ADMIN], MON_21, ZONE, FIVE) == PolicyPlan({}, ())
    assert plan_by_policy([item], four, [ADMIN], MON_21, ZONE, FollowUpPolicy()).limits == ()


def test_the_binders_override_wins_over_the_firms_policy() -> None:
    item = _item(override={"every_days": 14, "max": 2})
    planned = plan_by_policy([item], _sent_at(item, MON_14), [ADMIN], MON_21, ZONE, FIVE)
    assert planned.batches == {}  # 14 days, not 5
    stopped = plan_by_policy(
        [item], _sent_at(item, date(2026, 8, 3), date(2026, 8, 17)), [ADMIN], MON_21, ZONE, FIVE
    )
    assert stopped.batches == {}  # at most 2 for this binder


def test_after_the_maximum_the_limit_is_raised_once_and_no_fifth_is_drafted() -> None:
    item = _item()
    four = _sent_at(item, date(2026, 8, 24), date(2026, 8, 31), date(2026, 9, 8), MON_14)
    policy = FollowUpPolicy()  # 7 days, at most 4
    on_the_day = plan_by_policy([item], four, [ADMIN], MON_21, ZONE, policy)
    assert on_the_day.batches == {} and on_the_day.limits == ((BINDER, ASSIGNEE, MON_14),)
    later = plan_by_policy([item], four, [ADMIN], date(2026, 9, 22), ZONE, policy)
    assert later.batches == {} and later.limits == ()
    quiet = FollowUpPolicy(notify_preparer_after_max=False)
    assert plan_by_policy([item], four, [ADMIN], MON_21, ZONE, quiet).limits == ()


def test_the_limit_day_is_the_tick_a_weekend_moves_it_to() -> None:
    weekends = FollowUpPolicy(cadence_days=5, max_reminders=1, weekdays_only=False)
    assert limit_reached_today(Sent(1, MON_14), MON_21, weekends)  # Sat 19 -> the Monday tick
    assert not limit_reached_today(Sent(1, MON_14), FRI_18, weekends)
