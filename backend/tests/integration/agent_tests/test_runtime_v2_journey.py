"""P-10-T49 (SPEC-647 §1 outcomes 1, 2, 5 and 6; AC-W2, AC-W4, AC-W5, AC-S2, AC-S4, AC-P1, AC-P4;
INV-1 to INV-5): the runtime v2 journey at the API level, against Postgres.

Row acceptance: "The test runs in make check and fails on any agent-actor decision, uncited
approved change, walled read or wrong attribution."

Every human step goes over HTTP as the person (session messages, the answer, plan approval, the
proposal's approval, the counts, the run reads). The workflow's own steps run as the workflow runs
them, in its order, as activities against the same database (no Temporal server here; the
command order is pinned by the replay histories): load, validate and record the plan, the state
transitions, the step activity, the approved write after `not_before`. The model's turns are the
FakeModel's outcomes (`run_session_turn` answers the scripted turn), so nothing here is a model.

- **J11 b2-b3** (WB-01a/b, WB-03a/d/e): Hannah Leclerc asks "TY2025 season progress by office";
  the agent asks "Which returns should the report cover?"; she answers; the plan has one declared
  write and waits for her; she approves; the run builds the workbook and proposes Save to Files;
  she approves; the file is saved 10 seconds later as "Hannah Leclerc via Agent". The session is
  bound to the engagement: a firm-level Files store ("Files > Firm reports") is W-02's (P-10-T38
  partial).
- **J23 step 1** (SHL-13 states 3 and 4, AUD-02a/d): #4127 for Northwind is approved by Hannah,
  runs, and is blocked on Planning materiality, a decision reserved to the engagement partner
  Margaret Okonkwo, and only her "Waiting on you" counts it.
- **J13** (HOME-02 via C13): the plan awaiting approval and the run's proposal are counted in the
  approver's agent-outputs band, and leave it once she decides.
- **INV-1 to INV-5** over the journey's window: no agent or policy decision, every approved change
  cited and verified, a walled colleague reads nothing and leaves no read event, no portal read,
  and every audit row attributed to a person, "<person> via Agent", a policy or the platform.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Final, cast

import httpx
import pytest

from abacus.kernel.clock import frozen
from abacus.kernel.flags import forget_flags
from abacus.modules.agents import engagement_run
from abacus.modules.agents.api import TurnOutcome
from abacus.modules.agents.approved_write_workflow import ApprovedWriteInput
from abacus.modules.agents.approved_writes import execute_approved_write, rederive_run
from abacus.modules.agents.file_tools import SAVE_TOOL
from abacus.modules.agents.run_activities import (
    complete_run_activity,
    execute_step_activity,
    load_run_activity,
    record_plan_activity,
    set_state_activity,
)
from abacus.modules.agents.run_plan import PlanContext, PlanStep, validate_plan
from abacus.modules.agents.service import load_run_v2_context
from abacus.modules.agents.tools.runtime import ToolCallIn, call_tool
from abacus.modules.identity.api import GrantNotYetDue
from abacus.modules.review.api import rebuild_human_gates
from abacus.modules.workbench import session_activities, sessions
from abacus_tools.fakes.identity import FakeIdentityProvider
from abacus_tools.harness.invariants import AuditRow, check

from .support import Person, Seeder, World
from .walls_support import Net

Json = Any  # Any: a decoded JSON response body
Loose = Any  # Any: a role code or user id the seeder types loosely


pytestmark = pytest.mark.asyncio
T0 = datetime.fromisoformat("2026-09-14T09:27:00-05:00")  # Hannah approves Save to Files
REQUEST = "TY2025 season progress by office"
QUESTION = "Which returns should the report cover?"


# --- the cast and the world ----------------------------------------------------------------------


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@pytest.fixture(autouse=True)
def no_temporal(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """The session's and the runs' workflows are not started here; the journey runs their
    activities itself. The signals are captured, so the order of who woke what is checked."""
    sent: list[tuple[str, str]] = []

    async def signal_with_start(
        _workflow: object, _input: object, *, id: str, signal: str, payload: object
    ) -> None:
        del payload
        sent.append((id, signal))

    async def signal(workflow_id: str, name: str, *args: object) -> None:
        del args
        sent.append((workflow_id, name))

    async def dispatch(_workflow: object, _input: object, *, id: str, **_: object) -> None:
        sent.append((id, "start"))

    from abacus.modules.agents import commands, run_commands

    monkeypatch.setattr(sessions, "signal_with_start", signal_with_start)
    monkeypatch.setattr(commands, "signal_workflow", signal)
    monkeypatch.setattr(run_commands, "signal_workflow", signal)
    monkeypatch.setattr(engagement_run, "dispatch", dispatch)
    return sent


async def _on(seed: Seeder, world: World) -> None:
    # The runtime, the engagement run, and SHL-10's approval (off: the decision routes 404).
    for flag in ("agent_runtime.v2", "engagement_run.enabled", "review.approve_agent_output"):
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'p10-t49', 'P-10-T49') ON CONFLICT DO NOTHING",
            world.tenant_id,
            flag,
        )
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    forget_flags()


async def _named(seed: Seeder, world: World, name: str, role: str | None) -> Person:
    who = await seed.person(world.tenant_id)
    await seed.run("UPDATE users SET display_name = $2 WHERE id = $1", who.user_id, name)
    if role is not None:
        await seed.member(world.engagement_id, who, cast(Loose, role))
    return who


async def _client(seed: Seeder, world: World) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value("SELECT client_id FROM engagements WHERE id = $1", world.engagement_id),
    )


async def _since(seed: Seeder, world: World) -> int:
    return int(
        cast(
            int,
            await seed.value(
                "SELECT coalesce(max(seq), 0) FROM audit_events WHERE tenant_id = $1",
                world.tenant_id,
            ),
        )
    )


async def _write(
    net: Net, method: str, path: str, who: Person, body: object | None = None
) -> httpx.Response:
    """A write with its Idempotency-Key, as every run and session route requires."""
    headers = {**await net.headers(who), "Idempotency-Key": str(uuid.uuid4())}
    return await net.http.request(method, path, json=body, headers=headers)


async def _counts(net: Net, seed: Seeder, world: World, who: Person) -> dict[str, Json]:
    """The one count source (C13), after the projection is rebuilt from the owners' records
    (`rebuild_human_gates` is the same reconcile the outbox consumer runs per event)."""
    await rebuild_human_gates(world.tenant_id)
    found = await net.call("GET", "/v1/human-gates/counts", who)
    assert found.status_code == 200, found.text
    return cast(dict[str, Json], found.json())


async def _awaiting_approval(world: World, run_id: uuid.UUID) -> int:
    """What `AgentRunWorkflow.run` does before it waits: load, `planning`, code validation (the
    same `validate_plan` call), the plan as a `proposed` version, `awaiting_plan_approval`."""
    t, r = str(world.tenant_id), str(run_id)
    facts = await load_run_activity(t, r)
    await set_state_activity(t, r, "planning", None, None)
    assert facts.plan is not None
    steps = [PlanStep.parse(s) for s in facts.plan]
    problems = validate_plan(
        steps,
        PlanContext(
            declared_writes=frozenset(facts.declared_writes),
            client_scope=frozenset(facts.client_scope),
            approver_holds={pair: True for pair in facts.approver_holds},
            tool_actions=facts.tool_actions,
        ),
    )
    assert problems == [], problems  # AC-W1: the plan passes code validation before approval
    version = await record_plan_activity(t, r, [s.dump() for s in steps], problems)
    await set_state_activity(t, r, "awaiting_plan_approval", None, None)
    return version


async def _window(
    seed: Seeder, world: World, since: int
) -> tuple[list[AuditRow], frozenset[Loose]]:
    rows = await seed.rows(
        "SELECT seq, actor_kind, actor_id, action, on_behalf_of_user_id, policy_ref "
        "FROM audit_events WHERE tenant_id = $1 AND seq > $2 ORDER BY seq",
        world.tenant_id,
        since,
    )
    users = await seed.rows("SELECT id FROM users")
    return (
        [
            AuditRow(
                int(r["seq"]),
                str(r["actor_kind"]),
                cast(str | None, r["actor_id"]),
                str(r["action"]),
                cast(uuid.UUID | None, r["on_behalf_of_user_id"]),
                cast(str | None, r["policy_ref"]),
            )
            for r in rows
        ],
        frozenset(u["id"] for u in users),
    )


# The audit actions an approved write's executor records under the approver's grant.
_GRANT_EFFECTS: Final = frozenset({"file.saved"})
# INV-1 at the decision tables: a decided row whose decider is not a user (an agent or a policy).
_DECIDED_BY_AGENTS: Final = {
    "proposal_decisions": "SELECT count(*) FROM proposal_decisions t WHERE t.tenant_id = $1 "
    "AND t.decided_by IS NOT NULL AND t.decided_by NOT IN (SELECT id FROM users)",
    "agent_plans": "SELECT count(*) FROM agent_plans t WHERE t.tenant_id = $1 "
    "AND t.decided_by IS NOT NULL AND t.decided_by NOT IN (SELECT id FROM users)",
    "run_sign_offs": "SELECT count(*) FROM run_sign_offs t WHERE t.tenant_id = $1 "
    "AND t.signed_by IS NOT NULL AND t.signed_by NOT IN (SELECT id FROM users)",
}


async def _invariants(
    seed: Seeder,
    world: World,
    since: int,
    *,
    walled: Person | None = None,
    proposal_id: uuid.UUID | None = None,
) -> None:
    """INV-1 to INV-5 over the window's rows (the data-layer half of `assertInvariants`)."""
    rows, users = await _window(seed, world, since)
    # An approved write's effect (`file.saved`) is the agent executing a person's approval grant
    # ("Hannah via Agent"; P-10-T38, DEC-3402): the decision is the approval, which the decision
    # tables below hold to a person. INV-5 still checks the effect's attribution.
    effects = [r for r in rows if r.action in _GRANT_EFFECTS and r.actor_kind == "agent"]
    assert all(r.on_behalf_of_user_id in users for r in effects), effects
    violations = check([r for r in rows if r not in effects], users)
    violations += [v for v in check(effects, users) if v.invariant != "INV-1"]
    assert violations == [], [str(v) for v in violations]  # INV-1 and INV-5
    # INV-1, at the decision tables too: every decided row in the window is a person's.
    for table, query in _DECIDED_BY_AGENTS.items():
        agents = await seed.value(query, world.tenant_id)
        assert agents == 0, table
    if proposal_id is not None:
        # INV-2: every row of an approved proposal carries a code-verified citation.
        uncited = await seed.value(
            "SELECT count(*) FROM proposal_rows r WHERE r.proposal_id = $1 AND (r.unsupported "
            "OR cardinality(r.citation_ids) = 0 OR EXISTS (SELECT 1 FROM citations c WHERE "
            "c.id = ANY(r.citation_ids) AND NOT c.verified))",
            proposal_id,
        )
        assert uncited == 0
    if walled is not None:
        # INV-3: the walled colleague's reads left no read event of anything walled.
        reads = await seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND seq > $2 "
            "AND actor_id = $3 AND action LIKE '%.read%'",
            world.tenant_id,
            since,
            str(walled.user_id),
        )
        assert reads == 0
    # INV-4: no portal principal read anything in the window (no portal surface in this journey).
    portal = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND seq > $2 "
        "AND actor_kind = 'client'",
        world.tenant_id,
        since,
    )
    assert portal == 0


# --- J11 b2-b3 ---------------------------------------------------------------------------------


async def _session(seed: Seeder, world: World, owner: Person) -> uuid.UUID:
    refs = json.dumps([{"kind": "engagement", "id": str(world.engagement_id)}])
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO workbench_sessions (tenant_id, title, owner_user_id, origin, "
            "context_refs, client_scope) VALUES ($1, $2, $3, 'manual', $4::jsonb, $5) "
            "RETURNING id",
            world.tenant_id,
            REQUEST,
            owner.user_id,
            refs,
            [await _client(seed, world)],
        ),
    )


async def _cite(seed: Seeder, world: World) -> uuid.UUID:
    """A code-verified citation the workbook's figures rest on (INV-2)."""
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO citations (tenant_id, engagement_id, cited_from_type, cited_from_id, n, "
            "kind, source_type, source_id, locator, verified, verifier_version, created_by_kind, "
            "created_by_run_id) VALUES ($1, $2, 'proposal_probe', $3, 1, 'record_field', "
            '\'tax_return\', $3, \'{"record_type": "tax_return", "field": "line"}\', true, '
            "'v1', 'agent', $3) RETURNING id",
            world.tenant_id,
            world.engagement_id,
            uuid.uuid4(),
        ),
    )


def _j11_plan(hannah: Person) -> list[dict[str, object]]:
    """WB-03a: two steps, one declared write (Save to Files, Hannah its approver)."""
    return [
        {
            "key": "workbook",
            "label": "Build the TY2025 season progress workbook",
            "level": 0,
            "kind": "tool",
            "tool": "files.build_workbook",
            "arguments": {},
            "depends_on": [],
            "writes": [],
            "reads_clients": [],
        },
        {
            "key": "save",
            "label": "Save to Files",
            "level": 1,
            "kind": "tool",
            "tool": SAVE_TOOL,
            "arguments": {},
            "depends_on": ["workbook"],
            "writes": ["file.save"],
            "approver_user_id": str(hannah.user_id),
            "reads_clients": [],
        },
    ]


async def test_ac_j11_b2_b3_question_plan_workbook_and_save_to_files_as_hannah_via_agent(
    net: Net,
    seed: Seeder,
    world: World,
    object_store: str,
    monkeypatch: pytest.MonkeyPatch,
    no_temporal: list[tuple[str, str]],
) -> None:
    del object_store
    await _on(seed, world)
    hannah = await _named(seed, world, "Hannah Leclerc", "manager")
    lena = await _named(seed, world, "Lena Park", "senior")
    admin = await net.person(world.tenant_id, "firm_admin")
    await net.wall(admin, lena.user_id, await _client(seed, world))
    session_id = await _session(seed, world, hannah)
    since = await _since(seed, world)

    turns: list[TurnOutcome] = [
        TurnOutcome(
            "needs_input",
            question={
                "prompt": QUESTION,
                "step": "1 of 2",
                "options": [
                    {"key": "all", "label": "All TY2025 returns"},
                    {"key": "open", "label": "Open returns only"},
                ],
            },
        ),
        TurnOutcome("plan_proposed", plan=_j11_plan(hannah)),
    ]

    async def scripted(_tenant: uuid.UUID, _run: uuid.UUID, _request: str) -> TurnOutcome:
        return turns.pop(0)

    monkeypatch.setattr(session_activities, "run_session_turn", scripted)
    base = f"/v1/workbench/sessions/{session_id}"

    # WB-01a: the request; the turn asks one question and the session waits on her answer.
    asked = await _write(net, "POST", f"{base}/messages", hannah, {"body": REQUEST})
    assert asked.status_code == 202, asked.text
    first = await session_activities.session_turn_activity(
        str(world.tenant_id), str(session_id), "message", 1
    )
    assert first.child_run_id is None
    snapshot = cast(dict[str, Json], (await net.call("GET", base, hannah)).json())
    question = [i for i in snapshot["items"] if i["kind"] == "question"]
    assert len(question) == 1
    assert question[0]["payload"]["question"]["prompt"] == QUESTION

    # WB-01b: her answer; the turn proposes a plan with one declared write: exactly one child.
    answered = await _write(
        net,
        "POST",
        f"{base}/messages",
        hannah,
        {"body": "All TY2025 returns", "answers_seq": int(question[0]["seq"])},
    )
    assert answered.status_code == 202, answered.text
    answer_seq = await seed.value(
        "SELECT seq FROM session_items WHERE id = $1", uuid.UUID(answered.json()["item_id"])
    )
    second = await session_activities.session_turn_activity(
        str(world.tenant_id), str(session_id), "answer", int(cast(int, answer_seq))
    )
    assert second.child_run_id is not None
    child = uuid.UUID(str(second.child_run_id))
    assert (
        await seed.value(
            "SELECT count(*) FROM agent_runs WHERE session_id = $1 AND parent_run_id IS NOT NULL",
            session_id,
        )
        == 1
    )

    # WB-03a: the child validates its plan and waits for Hannah; J13 counts it for her.
    version = await _awaiting_approval(world, child)
    waiting = await _counts(net, seed, world, hannah)
    assert waiting["bands"]["agent_outputs"] >= 1
    plan_gates = await seed.value(
        "SELECT count(*) FROM human_gates WHERE tenant_id = $1 AND subkind = 'agent_run_plan' "
        "AND state = 'open' AND assignee_user_id = $2",
        world.tenant_id,
        hannah.user_id,
    )
    assert plan_gates == 1
    approved = await _write(
        net, "POST", f"/v1/agent-runs/{child}/plan/approve", hannah, {"expected_version": version}
    )
    assert approved.status_code == 200, approved.text
    assert cast(dict[str, Json], approved.json())["decided_by"] == "Hannah Leclerc"
    assert (f"agent_run:{world.tenant_id}:{child}", "plan_decided") in no_temporal
    after_plan = await _counts(net, seed, world, hannah)
    assert after_plan["bands"]["agent_outputs"] == waiting["bands"]["agent_outputs"] - 1
    await set_state_activity(str(world.tenant_id), str(child), "dispatched", None, None)
    await set_state_activity(str(world.tenant_id), str(child), "running", None, None)

    # WB-03d: the run builds the workbook and proposes Save to Files through C17.
    agent = await load_run_v2_context(world.tenant_id, child)
    built = await call_tool(
        agent,
        ToolCallIn(
            run_id=child,
            step_seq=1,
            attempt=1,
            name="files.build_workbook",
            arguments={
                "name": "TY2025 Season Progress — by office",
                "sheets": [{"title": "Summary", "rows": [["Office", "Open"], ["Chicago", 82]]}],
                "citation_ids": [str(await _cite(seed, world))],
            },
        ),
    )
    assert built.ok, built.code
    artifact = cast(dict[str, object], built.result)["artifact_id"]
    proposed = await call_tool(
        agent,
        ToolCallIn(
            run_id=child,
            step_seq=2,
            attempt=1,
            name="files.propose_save",
            arguments={"artifact_id": artifact, "folder": "deliverables"},
        ),
    )
    assert proposed.ok, proposed.code
    proposal = uuid.UUID(str(cast(dict[str, object], proposed.result)["proposal_id"]))
    await complete_run_activity(str(world.tenant_id), str(child), "succeeded", None)

    # J13: the run's proposal is in Hannah's "Waiting on you" agent outputs.
    queued = await _counts(net, seed, world, hannah)
    assert queued["bands"]["agent_outputs"] == after_plan["bands"]["agent_outputs"] + 1
    assert (
        await seed.value(
            "SELECT count(*) FROM human_gates WHERE tenant_id = $1 AND subkind = 'run_proposal' "
            "AND state = 'open' AND subject_ref ->> 'id' = $2",
            world.tenant_id,
            str(proposal),
        )
        == 1
    )
    # INV-3: Lena, walled from the client, sees neither the session, the run nor a count.
    assert (await net.call("GET", base, lena)).status_code == 404
    assert (await net.call("GET", f"/v1/agent-runs/{child}", lena)).status_code == 404
    walled_counts = await _counts(net, seed, world, lena)
    assert walled_counts["bands"]["agent_outputs"] == 0

    # WB-03e: Hannah approves; the copy lands only after `not_before`, as "Hannah via Agent".
    with frozen(T0):
        decided = await _write(
            net, "POST", f"/v1/proposals/{proposal}/approve", hannah, {"seen_version": 1}
        )
    assert decided.status_code == 200, decided.text
    grant = cast(
        uuid.UUID,
        await seed.value(
            "SELECT approval_grant_id FROM proposal_decisions WHERE proposal_id = $1", proposal
        ),
    )
    held = ApprovedWriteInput(
        str(world.tenant_id), str(child), str(proposal), str(grant), SAVE_TOOL
    )
    saved_before = await seed.value(
        "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1 AND source = 'agent_run'",
        world.tenant_id,
    )
    with frozen(T0.replace(second=5)), pytest.raises(GrantNotYetDue):
        await execute_approved_write(held)
    with frozen(T0.replace(second=11)):
        assert await execute_approved_write(held) == "saved"
        assert await rederive_run(world.tenant_id, child) == "approved"
    assert (
        await seed.value(
            "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1 AND source = 'agent_run'",
            world.tenant_id,
        )
        == cast(int, saved_before) + 1
    )
    saved = await seed.rows(
        "SELECT actor_kind, on_behalf_of_user_id FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'file.saved' AND seq > $2",
        world.tenant_id,
        since,
    )
    assert [(r["actor_kind"], r["on_behalf_of_user_id"]) for r in saved] == [
        ("agent", hannah.user_id)
    ]
    done = await _counts(net, seed, world, hannah)
    assert done["bands"]["agent_outputs"] == after_plan["bands"]["agent_outputs"]

    await _invariants(seed, world, since, walled=lena, proposal_id=proposal)


async def test_ac_j11_an_agent_context_never_decides_the_plan_or_the_proposal(
    seed: Seeder, world: World, monkeypatch: pytest.MonkeyPatch, net: Net
) -> None:
    """INV-1 at the API: the agent's own context is refused plan approval and the proposal's
    approval, and no decided row is written (the journey test above would fail on one)."""
    await _on(seed, world)
    hannah = await _named(seed, world, "Hannah Leclerc", "manager")
    session_id = await _session(seed, world, hannah)

    async def planned(_t: uuid.UUID, _r: uuid.UUID, _request: str) -> TurnOutcome:
        return TurnOutcome("plan_proposed", plan=_j11_plan(hannah))

    monkeypatch.setattr(session_activities, "run_session_turn", planned)
    posted = await _write(
        net, "POST", f"/v1/workbench/sessions/{session_id}/messages", hannah, {"body": REQUEST}
    )
    assert posted.status_code == 202, posted.text
    turned = await session_activities.session_turn_activity(
        str(world.tenant_id), str(session_id), "message", 1
    )
    assert turned.child_run_id is not None
    child = uuid.UUID(str(turned.child_run_id))
    version = await _awaiting_approval(world, child)
    from abacus.modules.agents import commands
    from abacus.modules.identity.api import AuthContext, Forbidden

    agent = await load_run_v2_context(world.tenant_id, child)
    with pytest.raises(Forbidden):
        await commands.approve_plan(cast(AuthContext, agent), child, version)
    assert (
        await seed.value(
            "SELECT count(*) FROM agent_plans WHERE run_id = $1 AND decided_by IS NOT NULL", child
        )
        == 0
    )


# --- J23 step 1 --------------------------------------------------------------------------------


async def test_ac_j23_1_northwind_4127_runs_on_a_persons_plan_approval(
    net: Net, seed: Seeder, world: World, no_temporal: list[tuple[str, str]]
) -> None:
    """J23 step 1 before anyone proposes materiality: the step fails closed with
    `materiality_not_proposed` (DEC-4417; the agent may not propose, a person does)."""
    await _j23(net, seed, world, no_temporal, through_decision=False)


async def test_ac_j23_1_northwind_4127_runs_then_blocks_on_margaret_okonkwos_decision(
    net: Net, seed: Seeder, world: World, no_temporal: list[tuple[str, str]]
) -> None:
    """J23 step 1 after Marcus proposes: the run holds on the card reserved to Margaret."""
    await _j23(net, seed, world, no_temporal, through_decision=True)


async def _proposed_materiality(world: World, marcus: Person) -> uuid.UUID:
    """What Marcus's `POST …/materiality/proposals` leaves for the run (A-04-T12): the awaiting
    `planning_materiality` card on the engagement's assurance item, raised by him through review
    with assurance's computed options (the provider refuses any other caller), reserved to the
    engagement partner."""
    from datetime import UTC, datetime, timedelta

    from abacus.kernel.db import TenantContext
    from abacus.modules.assurance import materiality
    from abacus.modules.engagements.api import assurance_item_id
    from abacus.modules.identity.api import AuthContext
    from abacus.modules.review.api import CardOption, ComputedCard, raise_decision_card

    ctx = AuthContext(
        TenantContext(world.tenant_id, "human", str(marcus.user_id)),
        marcus.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC) - timedelta(minutes=1),
    )
    item = await assurance_item_id(ctx.tenant, world.engagement_id)
    card = ComputedCard(options=(CardOption("rate_1_0", "1.0% of total assets"),))
    with materiality._computed(card):  # pyright: ignore[reportPrivateUsage]  # propose's own context
        return await raise_decision_card(
            ctx,
            engagement_id=world.engagement_id,
            kind=materiality.PROPOSE_KIND,
            question_key="materiality.total_assets",
            work_item_id=item,
        )


async def _j23(
    net: Net,
    seed: Seeder,
    world: World,
    no_temporal: list[tuple[str, str]],
    *,
    through_decision: bool,
) -> None:
    await _on(seed, world)
    marcus = await _named(seed, world, "Marcus Delaney", "senior")
    hannah = await _named(seed, world, "Hannah Leclerc", "manager")
    margaret = await _named(seed, world, "Margaret Okonkwo", "engagement_partner")
    since = await _since(seed, world)

    # SHL-13 state 1 → 2: the run is started and its code plan waits for approval.
    started = await _write(net, "POST", f"/v1/engagements/{world.engagement_id}/runs", marcus, {})
    assert started.status_code == 202, started.text
    run_id = uuid.UUID(cast(dict[str, str], started.json())["run_id"])
    assert any(signal == "start" for _, signal in no_temporal)
    version = await _awaiting_approval(world, run_id)
    runs_as = await seed.value(
        "SELECT coalesce(runs_as_user_id, initiator_user_id) FROM agent_runs WHERE id = $1",
        run_id,
    )
    assert (await _counts(net, seed, world, _person_of(world, runs_as)))["bands"][
        "agent_outputs"
    ] >= 1

    # AC-W2: Hannah approves; one `agent_run.plan_approved`, hers; SHL-13 state 3, Running.
    approved = await _write(
        net, "POST", f"/v1/agent-runs/{run_id}/plan/approve", hannah, {"expected_version": version}
    )
    assert approved.status_code == 200, approved.text
    t, r = str(world.tenant_id), str(run_id)
    await set_state_activity(t, r, "dispatched", None, None)
    await set_state_activity(t, r, "running", None, None)
    running = cast(
        dict[str, Json], (await net.call("GET", f"/v1/agent-runs/{run_id}", hannah)).json()
    )
    assert cast(dict[str, Json], running["run"])["state"] == "running"
    approvals = await seed.rows(
        "SELECT actor_kind, actor_id FROM audit_events WHERE tenant_id = $1 AND seq > $2 "
        "AND action = 'agent_run.plan_approved'",
        world.tenant_id,
        since,
    )
    assert [(a["actor_kind"], a["actor_id"]) for a in approvals] == [
        ("human", str(hannah.user_id))
    ]

    # SHL-13 state 4: Planning materiality raises a card reserved to the engagement partner.
    plan = await seed.value(
        "SELECT steps FROM agent_plans WHERE run_id = $1 ORDER BY version DESC LIMIT 1", run_id
    )
    steps = cast(list[dict[str, Json]], json.loads(str(plan)))
    materiality = next(s for s in steps if s.get("kind") == "decision")
    seq = 1 + steps.index(materiality)
    if not through_decision:
        outcome = await execute_step_activity(t, r, seq, materiality)
        assert (outcome.state, outcome.error_code) == ("failed", "materiality_not_proposed")
        await _invariants(seed, world, since)
        return
    card = await _proposed_materiality(world, marcus)
    outcome = await execute_step_activity(t, r, seq, materiality)
    assert outcome.state == "blocked" and outcome.wait_ref == str(card)
    await set_state_activity(
        t, r, "blocked_on_decision", None, {"kind": "decision", "step_seq": seq}
    )
    view = cast(
        dict[str, Json], (await net.call("GET", f"/v1/agent-runs/{run_id}", hannah)).json()
    )
    blocked = cast(dict[str, Json], view["header"])  # v2's 14 states (C6 v1's `run` maps them)
    assert blocked["state"] == "blocked_on_decision"
    assert blocked["blocked_on"]["kind"] == "decision"

    # "Blocked on a partner decision (Margaret Okonkwo)": the held card waits on the engagement
    # partner's role, which Margaret holds and Hannah does not. (C3 decision cards are not yet a
    # C13 gate source, so the Home bands do not count them; DEC-4417 records the gap.)
    held = await seed.rows("SELECT status, reserved_role FROM decision_cards WHERE id = $1", card)
    assert [(h["status"], h["reserved_role"]) for h in held] == [
        ("awaiting_role", "engagement_partner")
    ]
    roles = {
        r["user_id"]: r["role"]
        for r in await seed.rows(
            "SELECT user_id, role FROM engagement_members WHERE engagement_id = $1",
            world.engagement_id,
        )
    }
    assert roles[margaret.user_id] == "engagement_partner"
    assert roles[hannah.user_id] != "engagement_partner"
    await _invariants(seed, world, since)


def _person_of(world: World, user_id: object) -> Person:
    return Person(tenant_id=world.tenant_id, user_id=cast(uuid.UUID, user_id))
