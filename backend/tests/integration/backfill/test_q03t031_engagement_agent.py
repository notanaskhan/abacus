# ac-test-author: ayushkbhatia
"""Q-03-T031: back-fill of TASK-050 (SPEC-027 AC-1, AC-2, AC-6, AC-7: the engagement agent's
lifecycle, P-1, the pause switches and the activity feed) and the rest of TASK-051 (INV-1 and
DEC-74: every follow-up is sent by a person, never the agent). TASK-051's AC-3 to AC-5, AC-8 and
AC-9 are already back-filled on `main` (`test_follow_ups_and_due_dates.py`,
`test_due_dates_and_delegation.py`) and re-run unchanged.

Promises: an engagement's agent starts with it (by its relayed `engagement.created`) and ends at
archive; P-1 screens a new evidence version at Routine, once per version, and records `skipped`
with the reason at Advise or while paused; pausing (partner or manager per engagement, a firm
administrator with fresh MFA for the firm) stops every policy, and resuming screens what arrived
meanwhile once, without a burst; every automatic action is one insert-only feed row (policy and
version, outcome, reason, a record link, no client content) read by staff and never by clients.

Boundary: `create_app()` over HTTP for what people do; the relay's subscribers
(`agents.api.SUBSCRIPTIONS`) for events; a recording stand-in for the Temporal client, and the
agent's one activity (`handle`) per recorded signal, as its workflow runs it. Expectations come
from SPEC-027 §4 to §14, the matrix (`agents.yaml`, `identity.yaml`), TASK-050's design (agent
ID, flag `engagement_agent.enabled`, feed shape) and DEC-74 / DEC-220 (a person sends; SPEC-027's
"Routine sends" and the `drafted` feed outcome are superseded).
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Final, cast

import httpx
import pytest
import yaml
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from temporalio.client import Client

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.temporal import configure_temporal_client
from abacus.kernel.uow import Target, uow
from abacus.modules.agents.api import AgentEvent, HandleInput
from abacus.modules.agents.engagement_agent import TICK, handle, start_agents
from abacus.modules.agents.follow_ups import today_in
from abacus.modules.communications.transport import configure_transport
from abacus.modules.identity.api import Forbidden, Resource, agent_context_for_run, authorise

from .follow_up_template import import_reminder_template
from .q03_agent_support import REPO_MATRIX, Starts, World, make_world
from .support import Net, Person, Seeder

FLAG: Final = "engagement_agent.enabled"
ADVISE, ROUTINE = 0, 1
SCREENING: Final = "screening"  # the screener's workflow id prefix (SPEC-000; TASK-050 P-1)


@dataclass
class Mailbox:
    sent: list[str] = field(default_factory=list[str])

    def send(self, *, to: str, **_: object) -> None:
        self.sent.append(to)


@pytest.fixture(autouse=True)
def starts() -> Iterator[Starts]:
    made = Starts()
    configure_temporal_client(cast(Client, made))
    yield made
    configure_temporal_client(None)


@pytest.fixture(autouse=True)
def mailbox() -> Iterator[Mailbox]:
    box = Mailbox()
    configure_transport(box)
    yield box
    configure_transport(None)


@pytest.fixture
async def world(net: Net, seed: Seeder, starts: Starts) -> World:
    made = await make_world(net, seed, starts, "Halvorsen")
    await made.flag(FLAG)
    await made.level(ROUTINE)
    return made


async def _new_version(world: World) -> dict[str, object]:
    """A further evidence version on the engagement, and its `evidence_version.created`."""
    item = await world.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, $3, 'system', 'seed') RETURNING id",
        world.tenant_id,
        world.site.engagement_id,
        f"Statement {uuid.uuid4().hex[:6]}",
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = await world.seed.value(
        "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
        "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method) "
        "VALUES ($1, $2, $3, 1, $4, $5, 'v1', 10, 'application/pdf', 'upload', 'uploaded') "
        "RETURNING id",
        world.tenant_id,
        world.site.engagement_id,
        item,
        fingerprint,
        f"tenants/{world.tenant_id}/sha256/{fingerprint}",
    )
    return {
        "evidence_version_id": str(version),
        "evidence_item_id": str(item),
        "engagement_id": str(world.site.engagement_id),
        "requested_by": str(world.team["staff"].user_id),
    }


async def _evidence(world: World) -> str:
    """A new version reaches the agent; the agent handles it. Returns the version id."""
    payload = await _new_version(world)
    await world.relay("evidence_version.created", payload)
    await world.run_agent()
    return cast(str, payload["evidence_version_id"])


def _screens(world: World, version: str) -> list[str]:
    """Workflow ids of screening starts for this version (Temporal dedups one id)."""
    return [c.id for c in world.starts.to(SCREENING) if version in c.id]


def _rows(feed: list[dict[str, object]], version: str) -> list[dict[str, object]]:
    return [r for r in feed if r["record_id"] == version]


# --- AC-1: the agent's lifecycle --------------------------------------------------------------


async def test_ac1_creating_an_engagement_starts_its_agent(world: World) -> None:
    created = await world.net.call(
        "POST",
        "/v1/engagements",
        world.admin,
        body={
            "name": "FY2026 audit",
            "client_name": "Halvorsen Marine",
            "client_entity_name": "Halvorsen Marine",
            "fiscal_period_start": "2026-01-01",
            "fiscal_period_end": "2026-12-31",
            "confirm_new": True,
        },
    )
    assert created.status_code == 201, created.text
    engagement = created.json()["id"]
    assert await world.relay_outbox("engagement.created") == 1
    started = [c for c in world.starts.signals() if c.id.endswith(f":{engagement}")]
    assert [c.id for c in started] == [f"engagement-agent:{world.tenant_id}:{engagement}"]
    assert started[0].signal == "event"


async def test_ac1_with_the_flag_off_no_agent_starts(world: World) -> None:
    await world.flag(FLAG, on=False)
    await world.relay("engagement.created", {"engagement_id": str(world.site.engagement_id)})
    assert world.starts.signals() == []


async def test_ac1_existing_open_engagements_get_one_agent_each_and_archived_none(
    world: World, seed: Seeder
) -> None:
    archived = await seed.site(world.tenant_id, world.admin.user_id, "Archived")
    await seed.run(
        "UPDATE engagements SET status = 'archived' WHERE id = $1", archived.engagement_id
    )
    assert await start_agents(world.tenant_id) == 1
    assert await start_agents(world.tenant_id) == 1  # run again: the same signal
    ids = [c.id for c in world.starts.signals()]
    assert set(ids) == {f"engagement-agent:{world.tenant_id}:{world.site.engagement_id}"}
    events = {cast(AgentEvent, c.payload).event_id for c in world.starts.signals()}
    assert len(events) == 1  # once: the second start repeats the first event, not a new one
    await world.run_agent()
    once = await world.feed()
    await world.run_agent()  # nothing new: the repeat was already handled
    assert await world.feed() == once


async def test_ac1_the_agent_ends_when_its_engagement_is_archived(world: World) -> None:
    await world.seed.run(
        "UPDATE engagements SET status = 'archived' WHERE id = $1", world.site.engagement_id
    )
    await world.relay("evidence_version.created", await _new_version(world))
    assert await world.run_agent() == [True]
    assert world.starts.to(SCREENING) == []  # and nothing was screened on the way out


# --- AC-2: P-1 screens new evidence -----------------------------------------------------------


async def test_ac2_at_routine_p1_screens_a_new_version_once_and_feeds_it(world: World) -> None:
    payload = await _new_version(world)
    event = await world.relay("evidence_version.created", payload)
    await world.run_agent()
    version = cast(str, payload["evidence_version_id"])
    await world.relay("evidence_version.created", payload, event)  # delivered twice
    await world.run_agent()
    screens = _screens(world, version)
    assert len(set(screens)) == 1, screens  # one screening per version, whatever the replays
    rows = _rows(await world.feed(), version)
    assert [(r["policy"], r["outcome"]) for r in rows] == [("P-1", "done")]


@pytest.mark.parametrize("level", [ADVISE])
async def test_ac2_at_advise_p1_records_skipped_with_the_reason(world: World, level: int) -> None:
    await world.level(level)
    version = await _evidence(world)
    assert _screens(world, version) == []
    rows = _rows(await world.feed(), version)
    assert [(r["policy"], r["outcome"]) for r in rows] == [("P-1", "skipped")]
    assert rows[0]["reason"]


# --- AC-6: pause and resume -------------------------------------------------------------------


async def _pause(
    world: World, who: Person, reason: str | None = "Year-end freeze"
) -> httpx.Response:
    return await world.net.call("POST", f"{world.base}/agent/pause", who, body={"reason": reason})


async def test_ac6_a_paused_engagement_acts_on_nothing_and_resume_screens_once(
    world: World,
) -> None:
    partner = world.team["engagement_partner"]
    paused = await _pause(world, partner)
    assert paused.status_code == 200, paused.text
    state = paused.json()
    assert state["paused_at"] is not None and state["reason"] == "Year-end freeze"
    version = await _evidence(world)
    assert _screens(world, version) == []
    skipped = _rows(await world.feed(), version)
    assert [(r["policy"], r["outcome"]) for r in skipped] == [("P-1", "skipped")]
    assert skipped[0]["reason"]
    resumed = await world.net.call("POST", f"{world.base}/agent/resume", partner)
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["paused_at"] is None
    await world.run_agent()
    assert len(set(_screens(world, version))) == 1  # what arrived while paused, screened once
    count = len(world.starts.to(SCREENING))
    again = await world.net.call("POST", f"{world.base}/agent/resume", partner)
    assert again.status_code == 200
    await world.run_agent()
    assert len(world.starts.to(SCREENING)) == count  # no burst: nothing screened twice
    # SPEC-027 §14: pause and resume are audited with the person
    for action in ("engagement_agent.paused", "engagement_agent.resumed"):
        rows = await world.audit(action)
        assert rows, action
        assert {(r["actor_kind"], r["actor_id"]) for r in rows} == {
            ("human", str(partner.user_id))
        }


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        ("engagement_partner", True),
        ("manager", True),
        ("senior", False),
        ("staff", False),
        ("reviewer", False),
    ],
)
async def test_ac6_only_the_partner_and_managers_pause_an_engagement(
    world: World, role: str, allowed: bool
) -> None:
    response = await _pause(world, world.team[role], None)
    assert response.status_code == (200 if allowed else 403), response.text
    resumed = await world.net.call("POST", f"{world.base}/agent/resume", world.team[role])
    assert resumed.status_code == (200 if allowed else 403)


async def test_ac6_a_client_or_another_firm_cannot_pause(world: World, seed: Seeder) -> None:
    client = await seed.client_contact(world.site)
    refused = await _pause(world, client, None)
    assert refused.status_code in (403, 404)
    elsewhere = await make_world(world.net, seed, world.starts, "Granite")
    stranger = elsewhere.team["engagement_partner"]
    assert (await _pause(world, stranger, None)).status_code == 404  # DEC-43
    state = await world.net.call("GET", f"{world.base}/agent", world.team["manager"])
    assert state.json()["paused_at"] is None


async def test_ac6_the_firm_switch_needs_a_firm_administrator_with_fresh_mfa(
    world: World, seed: Seeder
) -> None:
    leader = await seed.person(world.tenant_id, "practice_leader")
    assert (await world.net.call("POST", "/v1/firm/agents/pause", leader)).status_code == 403
    partner = world.team["engagement_partner"]
    assert (await world.net.call("POST", "/v1/firm/agents/pause", partner)).status_code == 403
    stale = await world.net.call("POST", "/v1/firm/agents/pause", world.admin, mfa=False)
    assert stale.status_code == 403
    state = await world.net.call("GET", "/v1/firm/agents", world.admin)
    assert state.json()["paused_at"] is None


async def test_ac6_a_firm_pause_stops_every_engagement_and_resume_looks_once(
    world: World,
) -> None:
    paused = await world.net.call("POST", "/v1/firm/agents/pause", world.admin)
    assert paused.status_code == 200, paused.text
    assert paused.json()["paused_at"] is not None
    shown = await world.net.call("GET", f"{world.base}/agent", world.team["senior"])
    assert shown.json()["firm_paused_at"] is not None  # the header shows the firm's pause
    version = await _evidence(world)
    assert _screens(world, version) == []
    assert [r["outcome"] for r in _rows(await world.feed(), version)] == ["skipped"]
    resumed = await world.net.call("POST", "/v1/firm/agents/resume", world.admin)
    assert resumed.status_code == 200 and resumed.json()["paused_at"] is None
    assert await world.relay_outbox("firm.agents_resumed") == 1
    await world.run_agent()
    assert len(set(_screens(world, version))) == 1
    count = len(world.starts.to(SCREENING))
    await world.relay_outbox("firm.agents_resumed")  # the relay repeats itself
    await world.run_agent()
    assert len(world.starts.to(SCREENING)) == count


# --- AC-7: the activity feed ------------------------------------------------------------------


async def test_ac7_each_row_names_policy_version_outcome_and_link_without_content(
    world: World,
) -> None:
    version = await _evidence(world)
    response = await world.net.call("GET", f"{world.base}/activity", world.team["staff"])
    assert response.status_code == 200
    row = _rows(response.json(), version)[0]
    assert row["policy"] == "P-1"
    assert isinstance(row["policy_version"], int) and row["policy_version"] >= 1
    assert row["outcome"] in ("done", "skipped", "failed")
    assert row["record_type"] and row["record_id"] == version
    assert row["created_at"]
    assert world.site.marker not in response.text  # references only, never client content


async def test_ac7_the_feed_is_newest_first(world: World) -> None:
    first = await _evidence(world)
    second = await _evidence(world)
    feed = await world.feed()
    order = [r["record_id"] for r in feed if r["record_id"] in (first, second)]
    assert order == [second, first]


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior", "staff", "reviewer"])
async def test_ac7_every_staff_role_reads_the_feed(world: World, role: str) -> None:
    await _evidence(world)
    assert await world.feed(world.team[role])


async def test_ac7_firm_administrators_and_practice_leaders_read_it_clients_never(
    world: World, seed: Seeder
) -> None:
    await _evidence(world)
    assert await world.feed(world.admin)
    leader = await seed.person(world.tenant_id, "practice_leader")
    assert await world.feed(leader)
    for role in ("client_admin", "client_contributor"):
        client = await seed.client_contact(world.site, role)
        refused = await world.net.call("GET", f"{world.base}/activity", client)
        assert refused.status_code in (403, 404), role
    elsewhere = await make_world(world.net, seed, world.starts, "Granite")
    stranger = await world.net.call(
        "GET", f"{world.base}/activity", elsewhere.team["engagement_partner"]
    )
    assert stranger.status_code == 404  # DEC-43: another firm learns nothing


async def test_ac7_a_walled_member_reads_no_feed(world: World) -> None:
    await _evidence(world)
    walled = world.team["senior"]
    await world.net.wall(world.admin, walled, world.site)
    refused = await world.net.call("GET", f"{world.base}/activity", walled)
    assert refused.status_code in (403, 404)


async def test_ac7_the_feed_is_insert_only(world: World) -> None:
    await _evidence(world)
    app = TenantContext(world.tenant_id, "system", "agents.engagement_agent")
    for statement in (
        "UPDATE agent_activity SET reason = 'edited' WHERE engagement_id = :e",
        "DELETE FROM agent_activity WHERE engagement_id = :e",
    ):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with tenant_session(app) as session:
                await session.execute(text(statement), {"e": world.site.engagement_id})
    assert await world.feed()  # still there


# --- INV-1 / DEC-74: a person sends every follow-up -------------------------------------------


async def test_inv1_at_routine_the_tick_drafts_and_nothing_leaves_without_a_person(
    world: World, mailbox: Mailbox
) -> None:
    await import_reminder_template()
    await world.seed.client_contact(world.site)
    due = today_in("America/New_York", system_now()) - timedelta(days=9)
    await world.seed.run(
        "UPDATE request_items SET due_on = $2 WHERE id = $1", world.site.item_id, due
    )
    await world.relay("engagement.created", {"engagement_id": str(world.site.engagement_id)})
    await world.run_agent()
    await handle(  # the tick, as the workflow's timer sends it
        HandleInput(
            str(world.tenant_id), str(world.site.engagement_id), TICK, str(uuid.uuid4()), {}
        )
    )
    drafted = await world.seed.rows(
        "SELECT status, drafted_by_kind FROM follow_up_schedules WHERE engagement_id = $1",
        world.site.engagement_id,
    )
    assert drafted and {(r["status"], r["drafted_by_kind"]) for r in drafted} == {
        ("drafted", "agent")
    }
    assert mailbox.sent == []
    assert await world.audit("follow_up.sent") == []
    assert world.starts.to("follow-up") == []


async def test_inv1_the_agent_may_not_send_a_follow_up_even_holding_the_scope(
    world: World,
) -> None:
    agent = await agent_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="engagement.agent",
        engagement_id=world.site.engagement_id,
        task_scope=frozenset({"follow_up.draft", "follow_up.send"}),
        initiator_user_id=world.team["engagement_partner"].user_id,
    )
    resource = Resource.engagement(world.tenant_id, world.site.engagement_id, archived=False)
    await authorise(agent, "follow_up.draft", resource)  # it may draft
    with pytest.raises(Forbidden):
        await authorise(agent, "follow_up.send", resource)
    matrix = yaml.safe_load(REPO_MATRIX.joinpath("agents.yaml").read_text())
    assert matrix["actions"]["follow_up.send"]["agent"] == "deny"


async def test_inv1_the_database_refuses_a_follow_up_sent_by_an_agent(world: World) -> None:
    agent = TenantContext(world.tenant_id, "agent", "agent:engagement.agent:run", uuid.uuid4())
    with pytest.raises(Exception, match="human_only_action"):
        async with uow(agent) as tx:
            tx.record("follow_up.sent", target=Target("follow_up", uuid.uuid4()))


async def test_ac7_every_automatic_action_is_audited_as_well_as_fed(world: World) -> None:
    """SPEC-027 §14 asks for actor kind `agent`; TASK-050 D2 keeps P-1 to P-3 under today's
    authority (a system run), so the row is the platform's, never a person's (spec drift)."""
    for level in (ADVISE, ROUTINE):
        await world.level(level)
        await _evidence(world)
    fed = [r for r in await world.feed() if r["policy"] == "P-1"]
    audited = await world.audit("agent.activity")
    assert len(fed) == 2 and len(audited) == len(fed)
    assert {r["actor_kind"] for r in audited} == {"system"}
    assert {r["target_id"] for r in audited} == {str(world.site.engagement_id)}


# --- AC-6 (Q8) and SPEC-027 §4.3: P-3 records suggestions, and pausing stops it too -----------


async def _inbox_file(world: World) -> str:
    file_id = uuid.uuid4()
    await world.relay(
        "inbox_file.added",
        {
            "engagement_id": str(world.site.engagement_id),
            "inbox_file_id": str(file_id),
            "suggestions": 2,
        },
    )
    await world.run_agent()
    return str(file_id)


async def test_ac6_p3_records_suggestions_at_advise_and_skips_while_paused(world: World) -> None:
    await world.level(ADVISE)
    computed = await _inbox_file(world)
    rows = _rows(await world.feed(), computed)
    assert [(r["policy"], r["outcome"], r["item_count"]) for r in rows] == [("P-3", "done", 2)]
    paused = await _pause(world, world.team["manager"])
    assert paused.status_code == 200
    held = await _inbox_file(world)
    rows = _rows(await world.feed(), held)
    assert [(r["policy"], r["outcome"]) for r in rows] == [("P-3", "skipped")]
    started = [c for c in world.starts.calls if c.signal is None and held in c.id]
    assert started == []  # nothing automatic starts for it while paused
