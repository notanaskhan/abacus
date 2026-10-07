"""AC-14, AC-15, AC-16, AC-17, AC-20: run lifecycle, terminal errors, forced downgrades and the
per-run budget (TASK-011a interface contract, "Agents service" and "Gateway `call`").

Where the real pipeline cannot produce the input (an unbalanced trial balance is refused at
retrieval), the seam `abacus.modules.agents.service.facts` or `.call` is replaced. Expectations
come from the contract, not the implementation.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import replace
from decimal import Decimal
from typing import Literal, cast

import asyncpg
import pytest
from pydantic import BaseModel

from abacus.ai_gateway import (
    Attribution,
    BudgetExceeded,
    ContextBuilder,
    ContextTooLarge,
    DatasetTooLarge,
    FakeModel,
    GatewayCall,
    GatewayRefused,
    ModelRequest,
    ProviderError,
    call,
    configure_provider,
    cost,
    estimate_tokens,
    prompt,
)
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.agents import service
from abacus.modules.agents.api import (
    AGENTS,
    SCREENER,
    AgentRunNotRunning,
    SheetLayoutError,
    create_screening_run,
    fail_run,
    load_agent_context,
    screen,
)
from abacus.modules.agents.citations import SheetFacts, facts
from abacus.modules.identity.api import AgentContext

from .support import Seeder, World, retrieve, uploaded_version

PROMPT = "evidence.screen@v0"


class Script:
    def __init__(self, *replies: str) -> None:
        self.replies = replies
        self.requests: list[ModelRequest] = []

    def __call__(self, request: ModelRequest) -> str:
        self.requests.append(request)
        return self.replies[min(len(self.requests), len(self.replies)) - 1]


def reply(
    *,
    action: str = "ready_for_review",
    confidence: float = 0.9,
    citations: list[dict[str, object]] | None = None,
) -> str:
    return json.dumps(
        {
            "action": action,
            "confidence": confidence,
            "rationale": "Looks complete.",
            "citations": citations or [],
            "unverified": [],
        }
    )


@pytest.fixture
async def ready(world: World) -> tuple[uuid.UUID, uuid.UUID]:
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    return result.evidence_version_id, run_id


async def _agent(world: World, run_id: uuid.UUID) -> AgentContext:
    return await load_agent_context(world.tenant_id, run_id)


async def _insert_run(
    seed: Seeder,
    world: World,
    *,
    version_id: uuid.UUID | None,
    spec_version: int = 1,
    task_scope: tuple[str, ...] = ("evidence.read", "screening.run"),
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "evidence_version_id, initiator_user_id, task_scope) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING id",
            world.tenant_id,
            SCREENER,
            spec_version,
            world.engagement_id,
            version_id,
            world.requester.user_id,
            list(task_scope),
        ),
    )


async def _spend(seed: Seeder, world: World, run_id: uuid.UUID, amount: str) -> None:
    await seed.run(
        "INSERT INTO usage_records (tenant_id, engagement_id, agent_id, agent_run_id, "
        "prompt_id, prompt_version, model, tier, input_tokens, output_tokens, cost_usd, "
        "outcome, inputs_hash) VALUES ($1, $2, $3, $4, 'evidence.screen', 'v0', 'fake-small', "
        "'small', 1, 1, $5, 'ok', $6)",
        world.tenant_id,
        world.engagement_id,
        SCREENER,
        run_id,
        Decimal(amount),
        "a" * 64,
    )


async def _status(seed: Seeder, run_id: uuid.UUID) -> tuple[str, str | None]:
    [row] = await seed.rows("SELECT status, failure_code FROM agent_runs WHERE id = $1", run_id)
    return str(row["status"]), cast("str | None", row["failure_code"])


# --- create_screening_run ------------------------------------------------------------------------


async def test_ac17_a_requester_from_another_firm_gets_no_run_and_nothing_is_written(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    other_firm = await seed.firm()
    stranger = await seed.person(other_firm)
    events = await seed.count("audit_events", world.tenant_id)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), stranger.user_id
    )
    assert run_id is None
    assert await seed.count("agent_runs", world.tenant_id) == 0
    assert await seed.count("audit_events", world.tenant_id) == events


async def test_ac17_an_unknown_requester_gets_no_run(seed: Seeder, world: World) -> None:
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), uuid.uuid4()
    )
    assert run_id is None
    assert await seed.count("agent_runs", world.tenant_id) == 0


async def test_ac17_a_requester_whose_membership_was_revoked_gets_no_run(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    await seed.revoke(world.requester)
    events = await seed.count("audit_events", world.tenant_id)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is None
    assert await seed.count("agent_runs", world.tenant_id) == 0
    assert await seed.count("audit_events", world.tenant_id) == events


async def test_ac14_agent_run_started_is_recorded_by_the_agents_module_actor(
    seed: Seeder, world: World, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    started = [e for e in await seed.events(world.tenant_id) if e.action == "agent_run.started"]
    assert [e.target_id for e in started] == [str(run_id)]
    assert started[0].actor_id == f"agents:{SCREENER}"


# --- fail_run ------------------------------------------------------------------------------------


async def test_ac14_fail_run_ends_a_running_run_as_failed_and_records_it(
    seed: Seeder, world: World, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    before = len(await seed.actions(world.tenant_id))
    assert await fail_run(world.tenant_id, run_id, "gateway_refused") is True
    assert await _status(seed, run_id) == ("failed", "gateway_refused")
    [row] = await seed.rows("SELECT finished_at FROM agent_runs WHERE id = $1", run_id)
    assert row["finished_at"] is not None
    events = (await seed.events(world.tenant_id))[before:]
    assert [e.action for e in events] == ["agent_run.failed"]
    assert events[0].target_id == str(run_id)


async def test_ac14_fail_run_on_a_run_that_already_ended_returns_false_and_writes_nothing(
    seed: Seeder, world: World, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    assert await fail_run(world.tenant_id, run_id, "forbidden") is True
    events = await seed.count("audit_events", world.tenant_id)
    assert await fail_run(world.tenant_id, run_id, "not_found") is False
    assert await _status(seed, run_id) == ("failed", "forbidden")
    assert await seed.count("audit_events", world.tenant_id) == events


async def test_ac14_fail_run_does_not_touch_a_completed_run(
    seed: Seeder, world: World, fake_model: FakeModel, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    await screen(await _agent(world, run_id))
    events = await seed.count("audit_events", world.tenant_id)
    assert await fail_run(world.tenant_id, run_id, "forbidden") is False
    assert await _status(seed, run_id) == ("completed", None)
    assert await seed.count("audit_events", world.tenant_id) == events


async def test_ac14_a_failed_run_cannot_be_loaded(
    world: World, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    await fail_run(world.tenant_id, run_id, "forbidden")
    with pytest.raises(AgentRunNotRunning) as raised:
        await load_agent_context(world.tenant_id, run_id)
    assert raised.value.status == "failed"


# --- load_agent_context: spec version and scope --------------------------------------------------


async def test_ac17_a_run_from_another_spec_version_is_failed_and_not_loaded(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    run_id = await _insert_run(
        seed,
        world,
        version_id=result.evidence_version_id,
        spec_version=AGENTS[SCREENER].version + 1,
    )
    with pytest.raises(AgentRunNotRunning) as raised:
        await load_agent_context(world.tenant_id, run_id)
    assert raised.value.status == "failed"
    assert await _status(seed, run_id) == ("failed", "spec_version_changed")
    assert "agent_run.failed" in await seed.actions(world.tenant_id)


async def test_ac17_the_loaded_scope_is_the_runs_scope_within_the_current_spec(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    run_id = await _insert_run(
        seed,
        world,
        version_id=result.evidence_version_id,
        task_scope=("evidence.read", "screening.run", "follow_up.draft"),
    )
    agent = await _agent(world, run_id)
    assert agent.task_scope == AGENTS[SCREENER].task_scope


async def test_ac17_a_narrower_run_scope_narrows_the_loaded_agent(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    run_id = await _insert_run(
        seed, world, version_id=result.evidence_version_id, task_scope=("evidence.read",)
    )
    agent = await _agent(world, run_id)
    assert agent.task_scope == frozenset({"evidence.read"})


# --- screen: terminal errors fail the run and re-raise -------------------------------------------


async def _failed(seed: Seeder, world: World, run_id: uuid.UUID, code: str) -> None:
    assert await _status(seed, run_id) == ("failed", code)
    assert "agent_run.failed" in await seed.actions(world.tenant_id)
    assert await seed.count("screening_results", world.tenant_id) == 0


async def test_ac14_a_sheet_that_is_not_a_trial_balance_fails_the_run_as_unreadable(
    seed: Seeder,
    world: World,
    fake_model: FakeModel,
    monkeypatch: pytest.MonkeyPatch,
    ready: tuple[uuid.UUID, uuid.UUID],
) -> None:
    _, run_id = ready

    def refuse(content: bytes) -> SheetFacts:
        raise SheetLayoutError("two Total rows")

    monkeypatch.setattr(service, "facts", refuse)
    with pytest.raises(SheetLayoutError):
        await screen(await _agent(world, run_id))
    await _failed(seed, world, run_id, "unreadable_evidence")
    assert await seed.count("usage_records", world.tenant_id) == 0


@pytest.mark.parametrize(
    "error",
    [DatasetTooLarge("rows"), ContextTooLarge("size")],
    ids=["dataset_too_large", "context_too_large"],
)
async def test_ac14_an_oversized_context_fails_the_run_as_context_too_large(
    seed: Seeder,
    world: World,
    fake_model: FakeModel,
    monkeypatch: pytest.MonkeyPatch,
    ready: tuple[uuid.UUID, uuid.UUID],
    error: Exception,
) -> None:
    _, run_id = ready

    async def refuse(c: object) -> object:
        raise error

    monkeypatch.setattr(service, "call", refuse)
    with pytest.raises(type(error)):
        await screen(await _agent(world, run_id))
    await _failed(seed, world, run_id, "context_too_large")


async def test_ac14_a_refused_gateway_call_fails_the_run_as_gateway_refused(
    seed: Seeder,
    world: World,
    fake_model: FakeModel,
    monkeypatch: pytest.MonkeyPatch,
    ready: tuple[uuid.UUID, uuid.UUID],
) -> None:
    _, run_id = ready

    async def refuse(c: object) -> object:
        raise GatewayRefused("refused")

    monkeypatch.setattr(service, "call", refuse)
    with pytest.raises(GatewayRefused):
        await screen(await _agent(world, run_id))
    await _failed(seed, world, run_id, "gateway_refused")


async def test_ac14_a_missing_evidence_version_fails_the_run_as_not_found(
    seed: Seeder, world: World, fake_model: FakeModel
) -> None:
    await retrieve(world)
    run_id = await _insert_run(seed, world, version_id=None)
    with pytest.raises(NotFound):
        await screen(await _agent(world, run_id))
    await _failed(seed, world, run_id, "not_found")


async def test_ac14_a_provider_error_leaves_the_run_running_so_it_can_be_retried(
    seed: Seeder, world: World, fake_model: FakeModel, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    configure_provider(FakeModel())  # no responder: ProviderError
    with pytest.raises(ProviderError):
        await screen(await _agent(world, run_id))
    assert await _status(seed, run_id) == ("running", None)
    assert await seed.count("screening_results", world.tenant_id) == 0
    [usage] = await seed.rows(
        "SELECT outcome FROM usage_records WHERE tenant_id = $1", world.tenant_id
    )
    assert usage["outcome"] == "provider_error"
    configure_provider(fake_model)
    outcome = await screen(await _agent(world, run_id))
    assert outcome.status == "completed"
    assert await _status(seed, run_id) == ("completed", None)


# --- the per-run budget (ADR-070) ----------------------------------------------------------------


async def test_ac16_a_run_whose_budget_is_already_spent_is_refused_before_the_provider(
    seed: Seeder, world: World, fake_model: FakeModel, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    script = Script(reply())
    fake_model.respond(PROMPT, script)
    await _spend(seed, world, run_id, str(AGENTS[SCREENER].limits.max_cost_usd))
    with pytest.raises(BudgetExceeded):
        await screen(await _agent(world, run_id))
    assert script.requests == []
    await _failed(seed, world, run_id, "budget_exceeded")
    outcomes = [
        r["outcome"]
        for r in await seed.rows(
            "SELECT outcome FROM usage_records WHERE agent_run_id = $1 ORDER BY created_at",
            run_id,
        )
    ]
    assert outcomes == ["ok", "budget_refused"]


async def test_ac16_earlier_spend_for_the_run_counts_against_the_remaining_budget(
    seed: Seeder, world: World, fake_model: FakeModel, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    script = Script(reply())
    fake_model.respond(PROMPT, script)
    await _spend(seed, world, run_id, "0.029999")
    with pytest.raises(BudgetExceeded):
        await screen(await _agent(world, run_id))
    assert script.requests == []


async def test_ac16_modest_earlier_spend_leaves_room_for_the_screening(
    seed: Seeder, world: World, fake_model: FakeModel, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    await _spend(seed, world, run_id, "0.001")
    outcome = await screen(await _agent(world, run_id))
    assert outcome.status == "completed"


class Verdict(BaseModel):
    action: Literal["ready", "revise"]


async def test_ac16_the_gateway_counts_a_runs_earlier_usage_but_not_other_runs(
    seed: Seeder, world: World, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    version_id, run_id = ready
    other_run = await _insert_run(seed, world, version_id=version_id)
    fake = FakeModel()
    script = Script(json.dumps({"action": "ready"}))
    fake.respond(PROMPT, script)
    configure_provider(fake)
    context = ContextBuilder().task({"balanced": True}).build()
    estimate = cost("small", estimate_tokens(prompt(PROMPT).text + context.render()), 200)
    budget = estimate + Decimal("0.001")

    def gateway_call(for_run: uuid.UUID) -> GatewayCall[Verdict]:
        return GatewayCall(
            purpose="screen",
            prompt=PROMPT,
            tier="small",
            output_schema=Verdict,
            work_class="time_sensitive",  # SPEC-003 018c: every call declares its class
            routes=("bedrock", "direct"),  # SPEC-010: the fake route serves synthetic runs
            essential=True,
            budget_usd=budget,
            attribution=Attribution(
                TenantContext(world.tenant_id, "agent", f"agent:{SCREENER}:{for_run}"),
                world.engagement_id,
                SCREENER,
                for_run,
            ),
            context=context,
            max_output_tokens=200,
        )

    try:
        await _spend(seed, world, run_id, "0.0011")
        with pytest.raises(BudgetExceeded):
            await call(gateway_call(run_id))
        assert script.requests == []
        result = await call(gateway_call(other_run))
        assert result.status == "ok"
    finally:
        configure_provider(None)


# --- forced downgrades: code has the last word (ADR-066) -----------------------------------------


def _facts_with(change: Callable[[SheetFacts], SheetFacts]) -> Callable[[bytes], SheetFacts]:
    def patched(content: bytes) -> SheetFacts:
        return change(facts(content))

    return patched


async def _screen_saying_ready(
    seed: Seeder, world: World, fake_model: FakeModel, run_id: uuid.UUID
) -> tuple[str, list[str]]:
    fake_model.respond(PROMPT, Script(reply(action="ready_for_review", confidence=0.95)))
    outcome = await screen(await _agent(world, run_id))
    assert outcome.status == "completed"
    [row] = await seed.rows(
        "SELECT action, unverified FROM screening_results WHERE tenant_id = $1", world.tenant_id
    )
    return str(row["action"]), cast("list[str]", json.loads(row["unverified"]))


async def test_ac15_a_failed_citation_forces_needs_revision_whatever_the_model_proposed(
    seed: Seeder, world: World, fake_model: FakeModel, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    fake_model.respond(
        PROMPT,
        Script(reply(action="ready_for_review", confidence=0.99, citations=[{"cell": "Z9999"}])),
    )
    await screen(await _agent(world, run_id))
    [row] = await seed.rows(
        "SELECT action FROM screening_results WHERE tenant_id = $1", world.tenant_id
    )
    assert row["action"] == "needs_revision"


async def test_ac15_a_fabricated_value_forces_needs_revision(
    seed: Seeder, world: World, fake_model: FakeModel, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    fake_model.respond(
        PROMPT,
        Script(
            reply(
                action="ready_for_review",
                confidence=0.99,
                citations=[{"cell": "C2", "value": "123456789.01"}],
            )
        ),
    )
    await screen(await _agent(world, run_id))
    [row] = await seed.rows(
        "SELECT action FROM screening_results WHERE tenant_id = $1", world.tenant_id
    )
    assert row["action"] == "needs_revision"


async def test_ac15_verified_citations_keep_the_proposed_action(
    seed: Seeder, world: World, fake_model: FakeModel, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    action, unverified = await _screen_saying_ready(seed, world, fake_model, run_id)
    assert action == "ready_for_review"
    assert unverified == []


async def test_ac14_debits_that_differ_from_credits_force_needs_revision_with_a_note(
    seed: Seeder,
    world: World,
    fake_model: FakeModel,
    monkeypatch: pytest.MonkeyPatch,
    ready: tuple[uuid.UUID, uuid.UUID],
) -> None:
    _, run_id = ready
    monkeypatch.setattr(
        service, "facts", _facts_with(lambda f: replace(f, total_credit=f.total_credit + 1))
    )
    action, unverified = await _screen_saying_ready(seed, world, fake_model, run_id)
    assert action == "needs_revision"
    assert unverified


async def test_ac14_a_total_row_that_differs_from_its_lines_forces_needs_revision_with_a_note(
    seed: Seeder,
    world: World,
    fake_model: FakeModel,
    monkeypatch: pytest.MonkeyPatch,
    ready: tuple[uuid.UUID, uuid.UUID],
) -> None:
    _, run_id = ready
    monkeypatch.setattr(
        service, "facts", _facts_with(lambda f: replace(f, total_row_matches=False))
    )
    action, unverified = await _screen_saying_ready(seed, world, fake_model, run_id)
    assert action == "needs_revision"
    assert unverified


async def test_ac14_a_trimmed_account_list_is_noted_and_the_action_is_kept(
    seed: Seeder, world: World, fake_model: FakeModel
) -> None:
    def long_names(document: dict[str, object]) -> None:
        for line in cast("list[dict[str, object]]", document["lines"]):
            line["name"] = "<" * 200  # "<" is escaped to six characters in the context

    world.write_document(long_names)
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    script = Script(reply(action="ready_for_review", confidence=0.95))
    fake_model.respond(PROMPT, script)
    await screen(await _agent(world, run_id))
    [row] = await seed.rows(
        "SELECT action, unverified FROM screening_results WHERE tenant_id = $1", world.tenant_id
    )
    assert row["action"] == "ready_for_review"
    assert json.loads(row["unverified"])
    user = script.requests[0].user
    assert user.count("\\u003c" * 200) < 32
    assert "\n</untrusted>" in user


# --- composite foreign keys (AC-20) --------------------------------------------------------------


async def test_ac20_a_usage_record_cannot_name_another_engagement_than_its_runs(
    seed: Seeder, world: World, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    other = await seed.engagement(world.tenant_id, world.entity_id, world.requester.user_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run(
            "INSERT INTO usage_records (tenant_id, engagement_id, agent_id, agent_run_id, "
            "prompt_id, prompt_version, model, tier, input_tokens, output_tokens, cost_usd, "
            "outcome, inputs_hash) VALUES ($1, $2, $3, $4, 'p.q', 'v0', 'm', 'small', 1, 1, 0, "
            "'ok', $5)",
            world.tenant_id,
            other,
            SCREENER,
            run_id,
            "a" * 64,
        )


async def test_ac20_a_screening_result_must_name_its_runs_evidence_version(
    seed: Seeder, world: World, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    _, run_id = ready
    other_version = await uploaded_version(seed, world)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) "
            "VALUES ($1, $2, $3, $4, 'ready_for_review', 0.9, 'x', '[]', '[]')",
            world.tenant_id,
            world.engagement_id,
            other_version,
            run_id,
        )


async def test_ac20_an_agent_run_must_name_an_evidence_version_of_its_own_engagement(
    seed: Seeder, world: World, ready: tuple[uuid.UUID, uuid.UUID]
) -> None:
    version_id, _ = ready
    other = await seed.engagement(world.tenant_id, world.entity_id, world.requester.user_id)
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "evidence_version_id, initiator_user_id, task_scope) "
            "VALUES ($1, $2, 1, $3, $4, $5, ARRAY['evidence.read'])",
            world.tenant_id,
            SCREENER,
            other,
            version_id,
            world.requester.user_id,
        )
