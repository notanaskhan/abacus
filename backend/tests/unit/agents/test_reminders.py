"""SPEC-027 P-4, P-5 (TASK-051): the reminder cadence, batching and recipients, the daily tick's
time, and what a tick sends, drafts or skips."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.agents import reminders
from abacus.modules.agents.reminders import (
    Sent,
    business_days_between,
    next_sequence,
    plan,
    seconds_to_next_tick,
)
from abacus.modules.requests.api import OverdueItem

MON, TUE, WED, THU, FRI = (date(2026, 10, d) for d in (12, 13, 14, 15, 16))
SAT, NEXT_MON = date(2026, 10, 17), date(2026, 10, 19)
ADMIN, ASSIGNEE = uuid.uuid4(), uuid.uuid4()


def test_business_days_skip_weekends() -> None:
    assert business_days_between(MON, WED) == 2
    assert business_days_between(FRI, NEXT_MON) == 1


@pytest.mark.parametrize(
    ("sent", "today", "expected"),
    [
        (Sent(0, None), MON, None),  # the due date itself: not yet
        (Sent(0, None), TUE, 1),  # the first business day after
        (Sent(1, TUE), THU, None),  # 2 business days later: not yet
        (Sent(1, TUE), FRI, 2),  # 3 business days later
        (Sent(2, FRI), NEXT_MON, None),  # the weekend doesn't count
        (Sent(3, MON), date(2026, 11, 30), None),  # at most 3
    ],
)
def test_ac3_the_cadence(sent: Sent, today: date, expected: int | None) -> None:
    assert next_sequence(MON, sent, today) == expected


def _item(due: date, assignee: uuid.UUID | None = None) -> OverdueItem:
    return OverdueItem(uuid.uuid4(), "Bank statements", due, assignee)


def test_ac3_one_batch_per_contact_assignee_else_client_admins() -> None:
    assigned, unassigned = _item(MON, ASSIGNEE), _item(MON)
    batches = plan([assigned, unassigned], [], [ADMIN], TUE, "America/New_York")
    assert batches == {ASSIGNEE: [(assigned, 1)], ADMIN: [(unassigned, 1)]}


def test_ac3_a_changed_due_date_starts_the_sequence_again() -> None:
    item = _item(TUE)
    reminded_for_old_date = [(item.id, MON, 3, datetime(2026, 10, 13, 13, tzinfo=UTC))]
    assert plan([item], reminded_for_old_date, [ADMIN], WED, "UTC") == {ADMIN: [(item, 1)]}


def test_ac3_an_item_reminded_today_isnt_reminded_again() -> None:
    item = _item(MON)
    today_ny = [(item.id, MON, 1, datetime(2026, 10, 13, 13, tzinfo=UTC))]
    assert plan([item], today_ny, [ADMIN], TUE, "America/New_York") == {}


@pytest.mark.parametrize(
    ("now", "zone", "hours"),
    [
        (datetime(2026, 10, 12, 12, 0, tzinfo=UTC), "America/New_York", 1.0),  # Mon 08:00 EDT
        (datetime(2026, 10, 12, 14, 0, tzinfo=UTC), "America/New_York", 23.0),  # Mon 10:00 EDT
        (datetime(2026, 10, 16, 14, 0, tzinfo=UTC), "America/New_York", 71.0),  # Fri -> Mon
        (datetime(2026, 10, 12, 7, 0, tzinfo=UTC), "Europe/London", 1.0),  # Mon 08:00 BST
    ],
)
def test_q3_the_tick_is_09_00_on_the_next_business_day(
    now: datetime, zone: str, hours: float
) -> None:
    assert seconds_to_next_tick(now, zone) == int(hours * 3600)


# --- a tick ---------------------------------------------------------------------------------


class _World:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.open = True
        self.level = 1
        self.partner: uuid.UUID | None = uuid.uuid4()
        self.overdue = [_item(date(2026, 1, 5))]
        self.drafted: list[object] = []
        self.sent: list[tuple[object, dict[uuid.UUID, object]]] = []
        self.digests: list[object] = []

        async def overdue_for(*_: object) -> list[OverdueItem]:
            return self.overdue

        async def require_open(*_: object) -> None:
            if not self.open:
                raise reminders.EngagementNotOpen("x")

        async def history(*_: object) -> list[object]:
            return []

        async def admins(*_: object) -> list[uuid.UUID]:
            return [ADMIN]

        async def draft(
            tenant: object, engagement: object, batches: dict[uuid.UUID, object]
        ) -> int:
            self.drafted.append(batches)
            return len(batches)

        async def digest(
            tenant: object, engagement: object, outcome: reminders.Outcome
        ) -> reminders.Outcome:
            self.digests.append(outcome)
            return outcome

        class _Session:
            async def __aenter__(self) -> object:
                return self

            async def __aexit__(self, *_: object) -> None:
                return None

        monkeypatch.setattr(reminders, "overdue_for", overdue_for)
        monkeypatch.setattr(reminders, "require_open", require_open)
        monkeypatch.setattr(reminders, "reminder_history", history)

        def session(tenant: object) -> _Session:
            return _Session()

        monkeypatch.setattr(reminders, "tenant_session", session)
        monkeypatch.setattr(reminders, "client_admins", admins)
        monkeypatch.setattr(reminders, "_draft", draft)
        monkeypatch.setattr(reminders, "_digest", digest)


async def _tick(world: _World) -> reminders.Outcome:
    tenant = TenantContext(uuid.uuid4(), "system", "test")
    return await reminders.remind(tenant, uuid.uuid4(), "America/New_York", uuid.uuid4())


async def test_dec74_the_agent_drafts_even_at_routine(monkeypatch: pytest.MonkeyPatch) -> None:
    """TASK-104 (the plan's DEC-74, superseding SPEC-027 AC-3's Routine send): a person sends."""
    world = _World(monkeypatch)
    outcome = await _tick(world)
    assert (outcome.sent, outcome.drafted, outcome.overdue) == (0, 1, 1)
    assert world.sent == []
    [batches] = world.drafted
    assert list(cast(dict[uuid.UUID, object], batches)) == [ADMIN]
    assert world.digests == [outcome]


async def test_ac4_advise_drafts_and_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    world = _World(monkeypatch)
    world.level = 0
    outcome = await _tick(world)
    assert (outcome.sent, outcome.drafted) == (0, 1)
    assert world.sent == []


async def test_ac5_nothing_client_facing_before_the_engagement_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(monkeypatch)
    world.open = False
    outcome = await _tick(world)
    assert outcome.reason == "not_open" and world.sent == [] and world.drafted == []
    assert world.digests == [outcome]  # the team still hears about overdue items


async def test_ac8_no_active_partner_still_drafts_and_sends_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = _World(monkeypatch)
    world.partner = None
    outcome = await _tick(world)
    assert world.sent == [] and outcome.drafted == 1  # drafting needs no partner to act for


async def test_nothing_overdue_is_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    world = _World(monkeypatch)
    world.overdue = []
    assert await _tick(world) == reminders.Outcome(0)
    assert world.digests == []
