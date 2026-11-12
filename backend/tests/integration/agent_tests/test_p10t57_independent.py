"""P-10-T57 (ADR-078): independent acceptance tests for the sessions core (T43), durable run
records (T44) and the capability endpoint (T45), written from SPEC-647 §3.7 and §3.9,
`docs/contracts/agent-runs.md` §9 and DEC-4301 to DEC-4303, not from the implementation.

Row acceptance: "Tests pass and fail if a locked viewer receives a figure, a pruned run loses its
tool calls, or the capability endpoint calls a model."

The model's turns are scripted (`run_session_turn` answers a FakeModel outcome); the session's
workflow is not started (its signal is captured).
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Final, cast

import httpx
import pytest

from abacus.ai_gateway import FakeModel, configure_provider
from abacus.ai_gateway.providers import (
    ConverseRequest,
    ConverseResponse,
    ModelRequest,
    ModelResponse,
)
from abacus.kernel.flags import forget_flags
from abacus.modules.agents import trace_records
from abacus.modules.agents.api import TurnOutcome
from abacus.modules.evidence.retention import RECORD_TYPES
from abacus.modules.workbench import session_activities, sessions
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder, World
from .walls_support import Net

pytestmark = pytest.mark.asyncio
FIGURE: Final = "2,625 records read"  # a figure only a viewer who may open the client may see
MARKER: Final = "TB-FIGURE-0081234"


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@pytest.fixture(autouse=True)
def signals(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    sent: list[tuple[str, str]] = []

    async def capture(
        _workflow: object, _input: object, *, id: str, signal: str, payload: object
    ) -> None:
        del payload
        sent.append((id, signal))

    monkeypatch.setattr(sessions, "signal_with_start", capture)
    return sent


async def _flags(seed: Seeder, world: World) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'agent_runtime.v2', 'true', 'p10-t57', 'P-10-T57') ON CONFLICT DO NOTHING",
        world.tenant_id,
    )
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    forget_flags()


async def _member(seed: Seeder, world: World, role: str) -> Person:
    who = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, who, cast(Any, role))
    return who


async def _client(seed: Seeder, world: World) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value("SELECT client_id FROM engagements WHERE id = $1", world.engagement_id),
    )


async def _other_client(seed: Seeder, world: World) -> uuid.UUID:
    """A client of another entity: nobody on this engagement may open it."""
    return cast(
        uuid.UUID,
        await seed.value(
            "SELECT client_id FROM client_entities WHERE id = $1",
            await seed.entity(world.tenant_id),
        ),
    )


async def _session(
    seed: Seeder, world: World, owner: Person, clients: list[uuid.UUID]
) -> uuid.UUID:
    refs = json.dumps([{"kind": "engagement", "id": str(world.engagement_id)}])
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO workbench_sessions (tenant_id, title, owner_user_id, origin, "
            "context_refs, client_scope) VALUES ($1, 'Season questions', $2, 'manual', "
            "$3::jsonb, $4) RETURNING id",
            world.tenant_id,
            owner.user_id,
            refs,
            clients,
        ),
    )


async def _item(
    seed: Seeder, world: World, session_id: uuid.UUID, seq: int, kind: str, payload: object
) -> None:
    await seed.run(
        "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, actor_kind, "
        "actor_id, classification) VALUES ($1, $2, $3, $4, $5::jsonb, 'agent', "
        "'accrued_agent', 'confidential')",
        world.tenant_id,
        session_id,
        seq,
        kind,
        json.dumps(payload),
    )
    await seed.run(
        "UPDATE workbench_sessions SET item_seq = greatest(item_seq, $2) WHERE id = $1",
        session_id,
        seq,
    )


async def _post(net: Net, who: Person, session_id: uuid.UUID, body: object) -> httpx.Response:
    headers = {**await net.headers(who), "Idempotency-Key": str(uuid.uuid4())}
    return await net.http.post(
        f"/v1/workbench/sessions/{session_id}/messages", json=body, headers=headers
    )


# --- sessions (T43; AC-S2 to AC-S5) --------------------------------------------------------------


async def test_ac_s2_a_message_while_a_question_is_open_is_answered_first(
    net: Net, seed: Seeder, world: World, signals: list[tuple[str, str]]
) -> None:
    await _flags(seed, world)
    hannah = await _member(seed, world, "manager")
    session_id = await _session(seed, world, hannah, [await _client(seed, world)])
    question = {"v": 1, "question": {"prompt": "Which returns should the report cover?"}}
    await _item(seed, world, session_id, 1, "question", question)
    response = await _post(net, hannah, session_id, {"body": "Before that: how many are open?"})
    assert response.status_code == 202, response.text
    kinds = await seed.rows(
        "SELECT seq, kind FROM session_items WHERE session_id = $1 ORDER BY seq", session_id
    )
    assert [(r["seq"], r["kind"]) for r in kinds] == [(1, "question"), (2, "user_message")]
    assert [s for _, s in signals] == ["user_message"]  # a message, not the question's answer
    answer = await _post(net, hannah, session_id, {"body": "All of them", "answers_seq": 1})
    assert answer.status_code == 202, answer.text
    assert [s for _, s in signals] == ["user_message", "answer"]


async def test_ac_s2_an_answer_must_name_an_open_question(
    net: Net, seed: Seeder, world: World
) -> None:
    await _flags(seed, world)
    hannah = await _member(seed, world, "manager")
    session_id = await _session(seed, world, hannah, [await _client(seed, world)])
    await _item(seed, world, session_id, 1, "agent_blocks", {"v": 1})
    refused = await _post(net, hannah, session_id, {"body": "Yes", "answers_seq": 1})
    assert refused.status_code in (404, 409, 422), refused.text
    missing = await _post(net, hannah, session_id, {"body": "Yes", "answers_seq": 99})
    assert missing.status_code in (404, 409, 422), missing.text
    assert (
        await seed.value("SELECT count(*) FROM session_items WHERE session_id = $1", session_id)
        == 1
    )


async def test_ac_s4_each_write_proposing_turn_writes_exactly_one_child_run(
    net: Net, seed: Seeder, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _flags(seed, world)
    hannah = await _member(seed, world, "manager")
    session_id = await _session(seed, world, hannah, [await _client(seed, world)])
    plan: list[dict[str, object]] = [
        {
            "key": "save",
            "label": "Save to Files",
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
    children: list[str] = []
    for n, text in enumerate(("Save the workbook", "And save the memo"), start=1):
        posted = await _post(net, hannah, session_id, {"body": text})
        assert posted.status_code == 202, posted.text
        seq = await seed.value(
            "SELECT seq FROM session_items WHERE id = $1", uuid.UUID(posted.json()["item_id"])
        )
        done = await session_activities.session_turn_activity(
            str(world.tenant_id), str(session_id), "message", int(cast(int, seq))
        )
        again = await session_activities.session_turn_activity(
            str(world.tenant_id), str(session_id), "message", int(cast(int, seq))
        )
        assert done.child_run_id is not None and again.child_run_id == done.child_run_id, n
        children.append(str(done.child_run_id))
    assert len(set(children)) == 2
    rows = await seed.rows(
        "SELECT parent_run_id FROM agent_runs WHERE session_id = $1 AND parent_run_id IS NOT NULL",
        session_id,
    )
    assert len(rows) == 2 and len({r["parent_run_id"] for r in rows}) == 2


async def test_ac_s3_a_locked_viewer_receives_no_figure(
    net: Net, seed: Seeder, world: World
) -> None:
    await _flags(seed, world)
    hannah = await _member(seed, world, "manager")
    margaret = await _member(seed, world, "engagement_partner")
    clients = [await _client(seed, world), await _other_client(seed, world)]
    session_id = await _session(seed, world, hannah, clients)
    blocks = {"v": 1, "blocks": [{"kind": "text", "text": f"{FIGURE} · {MARKER}"}]}
    await _item(seed, world, session_id, 1, "agent_blocks", blocks)
    seen = await net.call("GET", f"/v1/workbench/sessions/{session_id}", margaret)
    assert seen.status_code == 200, seen.text
    snapshot = cast(dict[str, Any], seen.json())
    assert snapshot["locked"] is True
    assert snapshot["items"] == [] and snapshot["allowed_actions"] == []
    assert MARKER not in seen.text and FIGURE not in seen.text


async def test_ac_s3_a_locked_session_takes_no_message(
    net: Net, seed: Seeder, world: World
) -> None:
    await _flags(seed, world)
    hannah = await _member(seed, world, "manager")
    clients = [await _client(seed, world), await _other_client(seed, world)]
    session_id = await _session(seed, world, hannah, clients)
    seen = await net.call("GET", f"/v1/workbench/sessions/{session_id}", hannah)
    assert seen.status_code == 200 and seen.json()["locked"] is True
    refused = await _post(net, hannah, session_id, {"body": "Hello"})
    assert refused.status_code == 409, refused.text
    assert "session_locked" in refused.text
    assert (
        await seed.value("SELECT count(*) FROM session_items WHERE session_id = $1", session_id)
        == 0
    )


async def test_ac_s3_a_walled_viewer_reads_404_with_nothing_about_the_session(
    net: Net, seed: Seeder, world: World
) -> None:
    await _flags(seed, world)
    hannah = await _member(seed, world, "manager")
    lena = await _member(seed, world, "senior")
    client = await _client(seed, world)
    session_id = await _session(seed, world, hannah, [client])
    await _item(seed, world, session_id, 1, "agent_blocks", {"v": 1, "text": MARKER})
    admin = await net.person(world.tenant_id, "firm_admin")
    await net.wall(admin, lena.user_id, client)
    walled = await net.call("GET", f"/v1/workbench/sessions/{session_id}", lena)
    assert walled.status_code == 404
    assert MARKER not in walled.text and "Season questions" not in walled.text


# --- run records (T44; AC-RR2 to AC-RR4) ---------------------------------------------------------

TOOLS: Final = ("ledger.read_trial_balance", "evidence.search", "files.build_workbook")


async def _ended_run(seed: Seeder, world: World, who: Person, days: int) -> uuid.UUID:
    run_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, "
            "runs_as_user_id, inputs, started_at) VALUES ($1, 'runtime.conformance', 2, $2, $3, "
            "'{}', 'queued', 'run', 'manual', 4118, $3, '{}', "
            "clock_timestamp() - make_interval(days => $4)) RETURNING id",
            world.tenant_id,
            world.engagement_id,
            who.user_id,
            days,
        ),
    )
    for seq, tool in enumerate(TOOLS, start=1):
        await seed.run(
            "INSERT INTO agent_run_steps (tenant_id, run_id, seq, plan_step_key, level, kind, "
            "tool_name, state, started_at, ended_at, records_read) VALUES ($1, $2, $3, $4, 0, "
            "'tool', $5, 'succeeded', clock_timestamp() - make_interval(days => $6), "
            "clock_timestamp() - make_interval(days => $6), 10)",
            world.tenant_id,
            run_id,
            seq,
            f"s{seq}",
            tool,
            days,
        )
    for state in ("running", "succeeded"):
        await seed.run("UPDATE agent_runs SET state = $2 WHERE id = $1", run_id, state)
    for seq, age in enumerate((days, 31, 29), start=1):
        await seed.run(
            "INSERT INTO run_events (tenant_id, run_id, run_seq, type, payload, created_at) "
            "VALUES ($1, $2, $3, 'step.state', '{}', "
            "clock_timestamp() - make_interval(days => $4))",
            world.tenant_id,
            run_id,
            seq,
            age,
        )
    return run_id


async def _export(net: Net, who: Person, run_id: uuid.UUID) -> dict[str, Any]:
    headers = {**await net.headers(who), "Idempotency-Key": str(uuid.uuid4())}
    found = await net.http.post(f"/v1/agent-runs/{run_id}/trace-exports", json={}, headers=headers)
    assert found.status_code in (200, 201), found.text
    return cast(dict[str, Any], found.json())


async def test_ac_rr2_a_pruned_run_keeps_every_tool_call_in_its_trace(
    net: Net, seed: Seeder, world: World
) -> None:
    hannah = await _member(seed, world, "manager")
    run_id = await _ended_run(seed, world, hannah, 90)
    await trace_records.prune_firm(world.tenant_id)
    left = await seed.rows(
        "SELECT run_seq FROM run_events WHERE run_id = $1 ORDER BY run_seq", run_id
    )
    assert [r["run_seq"] for r in left] == [3]  # only past the 30-day horizon is pruned
    trace = await net.call("GET", f"/v1/agent-runs/{run_id}/trace", hannah)
    assert trace.status_code == 200, trace.text
    for tool in TOOLS:
        assert tool in trace.text or f"s{TOOLS.index(tool) + 1}" in trace.text, tool
    exported = await _export(net, hannah, run_id)
    for n in range(1, len(TOOLS) + 1):
        assert f"s{n}" in str(exported["content"]) or TOOLS[n - 1] in str(exported["content"])


async def test_ac_rr3_the_export_and_its_manifest_are_byte_identical_after_the_prune(
    net: Net, seed: Seeder, world: World
) -> None:
    hannah = await _member(seed, world, "manager")
    run_id = await _ended_run(seed, world, hannah, 90)
    first = await _export(net, hannah, run_id)
    await trace_records.prune_firm(world.tenant_id)
    second = await _export(net, hannah, run_id)
    assert first["content"] == second["content"]
    assert first["sha256"] == second["sha256"]
    for key in ("manifest", "signature"):
        if key in first:
            assert first[key] == second[key], key
    # The rows moved (a later step): the next export is a new frozen version, never a rewrite.
    await seed.run(
        "UPDATE agent_run_steps SET records_read = 11 WHERE run_id = $1 AND seq = 1", run_id
    )
    await seed.run("UPDATE agent_runs SET state = 'approved' WHERE id = $1", run_id)
    third = await _export(net, hannah, run_id)
    assert third["sha256"] != first["sha256"]
    versions = await seed.rows(
        "SELECT version FROM agent_run_traces WHERE run_id = $1 ORDER BY version", run_id
    )
    assert [v["version"] for v in versions][-1] >= 2


async def test_ac_rr4_run_records_are_a_retention_type_and_frozen_traces_are_insert_only(
    net: Net, seed: Seeder, world: World
) -> None:
    assert "agent_run_records" in RECORD_TYPES
    hannah = await _member(seed, world, "manager")
    run_id = await _ended_run(seed, world, hannah, 90)
    await _export(net, hannah, run_id)
    with pytest.raises(Exception):  # noqa: B017 (any refusal: the trigger or the grant)
        await seed.run("UPDATE agent_run_traces SET version = 9 WHERE run_id = $1", run_id)
    with pytest.raises(Exception):  # noqa: B017
        await seed.run("DELETE FROM agent_run_traces WHERE run_id = $1", run_id)
    assert await seed.value("SELECT count(*) FROM agent_run_traces WHERE run_id = $1", run_id) == 1


# --- capabilities (T45; DEC-4303) ----------------------------------------------------------------


class _NoModel(FakeModel):
    """A provider that fails the test on any model call (the endpoint must never call one)."""

    async def complete(self, request: ModelRequest) -> ModelResponse:
        raise AssertionError(f"the capability endpoint called the model ({request.prompt_ref})")

    async def converse(self, request: ConverseRequest) -> ConverseResponse:
        raise AssertionError("the capability endpoint called the model (converse)")


async def test_the_capability_endpoint_calls_no_model_and_writes_no_usage(
    net: Net, seed: Seeder, world: World
) -> None:
    await _flags(seed, world)
    hannah = await _member(seed, world, "manager")
    configure_provider(_NoModel())
    try:
        usage = await seed.value("SELECT count(*) FROM usage_records")
        calls = await seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'model.called'",
            world.tenant_id,
        )
        for path in (
            f"/v1/agents/capabilities?engagement_id={world.engagement_id}",
            "/v1/agents/capabilities",
        ):
            response = await net.call("GET", path, hannah)
            assert response.status_code == 200, (path, response.text)
            items = cast(list[dict[str, Any]], response.json()["items"])
            assert items and all(set(i) >= {"capability", "available", "reason"} for i in items)
        assert await seed.value("SELECT count(*) FROM usage_records") == usage
        assert (
            await seed.value(
                "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
                "AND action = 'model.called'",
                world.tenant_id,
            )
            == calls
        )
    finally:
        configure_provider(None)


async def test_the_first_reason_wins_in_the_documented_order(
    net: Net, seed: Seeder, world: World
) -> None:
    """DEC-4303's order: paused, ai_policy_off, ai_excluded, consent_7216, not_on_team. A staff
    member on the team may read but not start a run: a capability with no earlier reason reads
    `not_on_team`; a tax (`tri`) capability without §7216 consent reads `consent_7216` first."""
    await _flags(seed, world)
    staff = await _member(seed, world, "staff")
    response = await net.call(
        "GET", f"/v1/agents/capabilities?engagement_id={world.engagement_id}", staff
    )
    assert response.status_code == 200, response.text
    items = {i["capability"]: i for i in cast(list[dict[str, Any]], response.json()["items"])}
    for tax in ("tax.return_drafter", "tax.return_analyst"):
        assert (items[tax]["available"], items[tax]["reason"]) == (False, "consent_7216")
    others = [i for name, i in items.items() if not name.startswith("tax.")]
    assert others and all(i["reason"] == "not_on_team" for i in others)
    allowed = {"paused", "ai_policy_off", "ai_excluded", "consent_7216", "not_on_team", None}
    assert {i["reason"] for i in items.values()} <= allowed
