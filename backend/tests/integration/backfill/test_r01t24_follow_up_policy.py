"""R-01-T24 against Postgres (TASK-1421; DEC-74; migration 0221): the firm's follow-up policy.

Acceptance: with a 5-day cadence the next reminder after Mon Sep 14 is Mon Sep 21 (the pure
rule, `tests/unit/communications/test_follow_up_policy.py`), a marked-done binder gets no further
draft, and the pre-change P-4 history replays (`tests/workflows/test_engagement_agent_replay.py`).
Here: the GET answers the defaults and the next send, a save is versioned (409 on a stale one)
and audited, another firm sees only its own policy, the P-4 tick under the policy marker leaves a
marked-done binder alone, and without the marker it keeps the old rules.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext
from abacus.modules.agents.follow_ups import chase_overdue, today_in
from abacus.modules.communications.api import (
    FollowUpPolicy,
    follow_up_policy,
    save_follow_up_policy,
)
from abacus.modules.communications.follow_up_policy import FollowUpPolicyStale
from abacus.modules.identity.api import AuthContext, Forbidden

from .follow_up_template import import_reminder_template
from .support import Net, Person, Seeder, Site

ZONE = "America/Chicago"


@pytest.fixture(autouse=True)
async def reminder_template(engines: None) -> None:
    await import_reminder_template()


def _ctx(who: Person, role: str | None) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=role,  # pyright: ignore[reportArgumentType] -- a seeded role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


async def _firm(seed: Seeder) -> tuple[uuid.UUID, Person, Site, Person]:
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "policy")
    contact = await seed.client_contact(site)
    await seed.run("UPDATE firms SET time_zone = $2 WHERE tenant_id = $1", tenant, ZONE)
    # A Published binder: the policy chases nothing else (security review H1).
    await seed.run(
        "UPDATE request_lists SET status = 'published', published_at = now() "
        "WHERE engagement_id = $1",
        site.engagement_id,
    )
    return tenant, admin, site, contact


async def test_get_answers_the_defaults_and_the_next_send(net: Net, seed: Seeder) -> None:
    _, admin, _, _ = await _firm(seed)
    response = await net.call("GET", "/v1/firm/follow-up-policy", admin)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == 0
    assert body["policy"] == {
        "cadence_days": 7,
        "max_reminders": 4,
        "send_local_time": "09:00",
        "weekdays_only": True,
        "stop_on_binder_done": True,
        "notify_preparer_after_max": True,
        "cc_assigned_preparer": False,
        "mode": "draft_for_person",
    }
    nxt = datetime.fromisoformat(body["next_send"]["next_send_at"]).astimezone(ZoneInfo(ZONE))
    last = datetime.fromisoformat(body["next_send"]["last_sent_at"]).astimezone(ZoneInfo(ZONE))
    assert nxt.time() == time(9, 0) and nxt.weekday() < 5
    assert 7 <= (nxt.date() - last.date()).days <= 9  # a weekend moves it to the Monday


async def test_staff_cannot_read_the_policy(net: Net, seed: Seeder) -> None:
    tenant, _, _, _ = await _firm(seed)
    staff = await seed.person(tenant)
    response = await net.call("GET", "/v1/firm/follow-up-policy", staff)
    assert response.status_code == 403


async def test_a_save_is_versioned_audited_and_the_firms_own(seed: Seeder) -> None:
    tenant, admin, _, _ = await _firm(seed)
    other_tenant, other_admin, _, _ = await _firm(seed)
    ctx = _ctx(admin, "firm_admin")
    saved = await save_follow_up_policy(ctx, FollowUpPolicy(cadence_days=5), 0)
    assert saved.version == 1
    with pytest.raises(FollowUpPolicyStale):
        await save_follow_up_policy(ctx, FollowUpPolicy(cadence_days=6), 0)
    again = await save_follow_up_policy(ctx, FollowUpPolicy(cadence_days=6, max_reminders=2), 1)
    assert again.version == 2
    mine = await follow_up_policy(ctx.tenant)
    assert (mine.cadence_days, mine.max_reminders, mine.version) == (6, 2, 2)
    theirs = await follow_up_policy(_ctx(other_admin, "firm_admin").tenant)
    assert (theirs.cadence_days, theirs.version) == (7, 0)  # forced RLS: their defaults
    actions = await seed.actions(tenant)
    assert actions.count("follow_up_policy.saved") == 2
    assert "follow_up_policy.saved" not in await seed.actions(other_tenant)
    leader = _ctx(admin, "practice_leader")
    with pytest.raises(Forbidden):
        await save_follow_up_policy(leader, FollowUpPolicy(), 2)


async def _tick(tenant: uuid.UUID, site: Site, *, policy_v1: bool) -> int:
    system = TenantContext(tenant, "system", "agents.engagement_agent")
    outcome = await chase_overdue(
        system, site.engagement_id, ZONE, uuid.uuid4(), policy_v1=policy_v1
    )
    return outcome.drafted


async def test_ac_a_marked_done_binder_gets_no_further_draft(seed: Seeder) -> None:
    tenant, _, site, _ = await _firm(seed)
    due = today_in(ZONE, system_now()) - timedelta(days=10)
    await seed.item(site, "Bank statement", due_on=due)
    await seed.run(
        "UPDATE request_lists SET marked_done_at = now() WHERE engagement_id = $1",
        site.engagement_id,
    )
    assert await _tick(tenant, site, policy_v1=True) == 0
    # Without the policy marker (a recorded history) the old rules stand: it is chased.
    assert await _tick(tenant, site, policy_v1=False) == 1


async def test_the_policy_tick_drafts_for_an_open_binder_and_reads_its_override(
    seed: Seeder,
) -> None:
    tenant, _, site, _ = await _firm(seed)
    due = today_in(ZONE, system_now()) - timedelta(days=10)
    await seed.item(site, "Bank statement", due_on=due)
    assert await _tick(tenant, site, policy_v1=True) == 1  # the first tick after the due date
    assert await _tick(tenant, site, policy_v1=True) == 0  # not again until the cadence
    await seed.run(
        'UPDATE request_lists SET follow_up_override = \'{"every_days": 1, "max": 1}\'::jsonb '
        "WHERE engagement_id = $1",
        site.engagement_id,
    )
    assert await _tick(tenant, site, policy_v1=True) == 0  # the binder's maximum of one
