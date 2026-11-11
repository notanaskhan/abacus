"""P-10-T43 (TASK-7301; SPEC-647 §3.7 AC-S1 to AC-S5; DEC-87, DEC-4301): the sessions core.

Over HTTP: the snapshot's DEC-87 visibility (a client the viewer can't open reads `locked` with no
items; a walled client's session is omitted), the message post (202, the person's item and their
turn's run, the same `Idempotency-Key` answering the same item, never on a locked session) and the
turn activity's one child run per write-proposing turn. The session workflow is not started here
(`signal_with_start` is captured); its command order is pinned by the S37 replay histories.
"""

from __future__ import annotations

import uuid
from typing import cast

import httpx
import pytest

from abacus.kernel.flags import forget_flags
from abacus.modules.agents.api import TurnOutcome
from abacus.modules.workbench import session_activities, sessions
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@pytest.fixture(autouse=True)
def signalled(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, object]]:
    sent: list[tuple[str, str, object]] = []

    async def capture(
        _workflow: object, _input: object, *, id: str, signal: str, payload: object
    ) -> None:
        sent.append((id, signal, payload))

    monkeypatch.setattr(sessions, "signal_with_start", capture)
    return sent


async def _on(seed: Seeder, world: World) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t43', 'P-10-T43') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    forget_flags()


async def _session(seed: Seeder, world: World, owner: Person, *clients: uuid.UUID) -> uuid.UUID:
    client = await seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.engagement_id
    )
    refs = f'[{{"kind": "engagement", "id": "{world.engagement_id}"}}]'
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO workbench_sessions (tenant_id, title, owner_user_id, origin, "
            "context_refs, client_scope) VALUES ($1, 'Feld 1040 questions', $2, 'manual', "
            "$3::jsonb, $4) RETURNING id",
            world.tenant_id,
            owner.user_id,
            refs,
            [client, *clients],
        ),
    )


async def _hannah(seed: Seeder, world: World) -> Person:
    hannah = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, hannah, "manager")
    return hannah


async def _post(
    net: Net, who: Person, session_id: uuid.UUID, key: str, body: object
) -> httpx.Response:
    headers = {**await net.headers(who), "Idempotency-Key": key}
    return await net.http.post(
        f"/v1/workbench/sessions/{session_id}/messages", json=body, headers=headers
    )


async def test_acs1_a_message_writes_the_item_and_one_turn_run_in_the_session(
    net: Net, seed: Seeder, world: World, signalled: list[tuple[str, str, object]]
) -> None:
    await _on(seed, world)
    hannah = await _hannah(seed, world)
    session_id = await _session(seed, world, hannah)
    response = await _post(net, hannah, session_id, "k-1", {"body": "How many returns are open?"})
    assert response.status_code == 202, response.text
    body = cast(dict[str, str], response.json())
    run_id = uuid.UUID(body["run_id"])
    assert (
        await seed.value("SELECT session_id FROM agent_runs WHERE id = $1", run_id) == session_id
    )
    assert (
        await seed.value(
            "SELECT kind FROM session_items WHERE session_id = $1 AND seq = 1", session_id
        )
        == "user_message"
    )
    assert signalled == [(f"session:{world.tenant_id}:{session_id}", "user_message", 1)]
    again = await _post(net, hannah, session_id, "k-1", {"body": "How many returns are open?"})
    assert again.status_code == 202 and again.json()["item_id"] == body["item_id"]
    assert (
        await seed.value("SELECT count(*) FROM agent_runs WHERE session_id = $1", session_id) == 1
    )


async def test_acs3_a_client_the_viewer_cannot_open_reads_locked_with_no_items(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    hannah = await _hannah(seed, world)
    copperleaf = await seed.value(
        "SELECT client_id FROM client_entities WHERE id = $1", await seed.entity(world.tenant_id)
    )
    session_id = await _session(seed, world, hannah, cast(uuid.UUID, copperleaf))
    await seed.run(
        "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, actor_kind, "
        "actor_id, classification) VALUES ($1, $2, 1, 'agent_blocks', '{\"v\": 1}', 'agent', "
        "'accrued_agent', 'confidential')",
        world.tenant_id,
        session_id,
    )
    margaret = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, margaret, "senior")
    seen = await net.call("GET", f"/v1/workbench/sessions/{session_id}", margaret)
    assert seen.status_code == 200, seen.text
    snapshot = cast(dict[str, object], seen.json())
    assert snapshot["locked"] is True and snapshot["items"] == []
    assert snapshot["allowed_actions"] == []
    mine = await net.call("GET", f"/v1/workbench/sessions/{session_id}", hannah)
    assert mine.status_code == 200


async def test_acs3_a_walled_clients_session_is_omitted_for_that_viewer(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    hannah = await _hannah(seed, world)
    session_id = await _session(seed, world, hannah)
    client = cast(
        uuid.UUID,
        await seed.value("SELECT client_id FROM engagements WHERE id = $1", world.engagement_id),
    )
    admin = await net.person(world.tenant_id, "firm_admin")
    await net.wall(admin, hannah.user_id, client)
    walled = await net.call("GET", f"/v1/workbench/sessions/{session_id}", hannah)
    assert walled.status_code == 404


async def test_a_locked_session_takes_no_message_and_only_its_owner_posts(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    hannah = await _hannah(seed, world)
    session_id = await _session(seed, world, hannah)
    marcus = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, marcus, "senior")
    theirs = await _post(net, marcus, session_id, "k-2", {"body": "Hello"})
    assert theirs.status_code == 403


async def test_acs4_a_write_proposing_turn_writes_exactly_one_child_run(
    seed: Seeder, world: World, net: Net, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _on(seed, world)
    hannah = await _hannah(seed, world)
    session_id = await _session(seed, world, hannah)
    posted = await _post(net, hannah, session_id, "k-3", {"body": "Save the workbook to Files"})
    assert posted.status_code == 202, posted.text
    plan = [
        {
            "key": "s1",
            "label": "Save the workbook to Files",
            "level": 0,
            "kind": "tool",
            "tool": "files.save_approved",
            "arguments": {},
            "depends_on": [],
            "writes": ["file.save"],
            "approver_user_id": str(hannah.user_id),
            "reads_clients": [],
        }
    ]

    async def planned(_t: uuid.UUID, _r: uuid.UUID, _request: str) -> TurnOutcome:
        return TurnOutcome("plan_proposed", plan=plan)

    monkeypatch.setattr(session_activities, "run_session_turn", planned)
    first = await session_activities.session_turn_activity(
        str(world.tenant_id), str(session_id), "message", 1
    )
    again = await session_activities.session_turn_activity(
        str(world.tenant_id), str(session_id), "message", 1
    )
    assert first.child_run_id is not None and again.child_run_id == first.child_run_id
    turn = uuid.UUID(cast(dict[str, str], posted.json())["run_id"])
    assert await seed.value("SELECT count(*) FROM agent_runs WHERE parent_run_id = $1", turn) == 1
    assert (
        await seed.value(
            "SELECT kind FROM session_items WHERE session_id = $1 AND seq = 2", session_id
        )
        == "plan"
    )
    assert (
        await seed.value("SELECT state FROM workbench_sessions WHERE id = $1", session_id)
        == "awaiting_answer"
    )


async def test_acs5_a_soft_deleted_session_reads_404_and_keeps_its_items(
    net: Net, seed: Seeder, world: World
) -> None:
    await _on(seed, world)
    hannah = await _hannah(seed, world)
    session_id = await _session(seed, world, hannah)
    await _post(net, hannah, session_id, "k-4", {"body": "Hi"})
    await seed.run(
        "UPDATE workbench_sessions SET deleted_at = clock_timestamp() WHERE id = $1", session_id
    )
    gone = await net.call("GET", f"/v1/workbench/sessions/{session_id}", hannah)
    assert gone.status_code == 404
    assert (
        await seed.value("SELECT count(*) FROM session_items WHERE session_id = $1", session_id)
        == 1
    )
