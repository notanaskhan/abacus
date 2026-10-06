"""AC-14, AC-16, AC-20: migration 0010, as `abacus_app` and as the superuser (TASK-011a interface
contract, "Database" under "Agents service").

`screening_results` and `usage_records` are insert-only for `abacus_app`; `agent_runs` is
forward-only (a finished run cannot be updated; `context_hash` and `output` are write-once).
Statements that must fail for `abacus_app` run through `tenant_session`; constraints are proven as
the superuser, who bypasses grants and row-level security. Expectations come from the contract.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import cast

import asyncpg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.ai_gateway import FakeModel
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.agents.api import (
    SCREENER,
    create_screening_run,
    load_agent_context,
    screen,
)

from .support import Seeder, World, retrieve


@dataclass(frozen=True)
class Screened:
    world: World
    version_id: uuid.UUID
    run_id: uuid.UUID
    result_id: uuid.UUID

    @property
    def ctx(self) -> TenantContext:
        return TenantContext(self.world.tenant_id, "system", "schema-test")


@pytest.fixture
async def screened(world: World, fake_model: FakeModel) -> Screened:
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    outcome = await screen(await load_agent_context(world.tenant_id, run_id))
    assert outcome.screening_result_id is not None
    return Screened(world, result.evidence_version_id, run_id, outcome.screening_result_id)


@pytest.fixture
async def running(world: World) -> Screened:
    """A run that has not been screened (its result id is a placeholder)."""
    result = await retrieve(world)
    run_id = await create_screening_run(
        world.tenant_id, result.evidence_version_id, uuid.uuid4(), world.requester.user_id
    )
    assert run_id is not None
    return Screened(world, result.evidence_version_id, run_id, uuid.uuid4())


async def _app_error(ctx: TenantContext, statement: str, **params: object) -> str:
    with pytest.raises(DBAPIError) as raised:
        async with tenant_session(ctx) as session:
            await session.execute(text(statement), params)
    return str(raised.value)


# --- tables are tenant tables with row-level security --------------------------------------------


@pytest.mark.parametrize("table", ["agent_runs", "screening_results", "usage_records"])
async def test_ac20_the_new_tables_force_row_level_security(seed: Seeder, table: str) -> None:
    [row] = await seed.rows(
        "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = $1", table
    )
    assert row["relrowsecurity"] is True
    assert row["relforcerowsecurity"] is True


@pytest.mark.parametrize(
    "query",
    [
        "SELECT count(*) FROM agent_runs WHERE id = :id",
        "SELECT count(*) FROM screening_results WHERE agent_run_id = :id",
        "SELECT count(*) FROM usage_records WHERE agent_run_id = :id",
    ],
)
async def test_ac20_another_firm_sees_none_of_the_rows(
    seed: Seeder, screened: Screened, query: str
) -> None:
    other_tenant = await seed.firm()
    async with tenant_session(TenantContext(other_tenant, "system", "intruder")) as session:
        assert (await session.execute(text(query), {"id": screened.run_id})).scalar_one() == 0
    async with tenant_session(screened.ctx) as session:
        assert (await session.execute(text(query), {"id": screened.run_id})).scalar_one() >= 1


async def test_ac20_a_firm_cannot_write_a_usage_record_for_another_firm(
    seed: Seeder, screened: Screened
) -> None:
    other_tenant = await seed.firm()
    message = await _app_error(
        TenantContext(other_tenant, "system", "intruder"),
        "INSERT INTO usage_records (id, tenant_id, agent_id, prompt_id, prompt_version, model, "
        "tier, input_tokens, output_tokens, cost_usd, outcome, inputs_hash) VALUES (:id, :t, "
        "'a.b', 'p.q', 'v0', 'm', 'small', 1, 1, 0, 'ok', :h)",
        id=uuid.uuid4(),
        t=screened.world.tenant_id,
        h="0" * 64,
    )
    assert "row-level security" in message


async def test_ac20_a_firm_cannot_write_an_agent_run_for_another_firm(
    seed: Seeder, running: Screened
) -> None:
    other_tenant = await seed.firm()
    message = await _app_error(
        TenantContext(other_tenant, "system", "intruder"),
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope) "
        "VALUES (:id, :t, 'a.b', 1, :e, :u, ARRAY['evidence.read'])",
        id=uuid.uuid4(),
        t=running.world.tenant_id,
        e=running.world.engagement_id,
        u=running.world.requester.user_id,
    )
    assert "row-level security" in message


# --- screening_results: insert-only, agent-attributed --------------------------------------------


async def test_ac14_screening_results_cannot_be_updated_by_the_app(screened: Screened) -> None:
    message = await _app_error(
        screened.ctx,
        "UPDATE screening_results SET action = 'needs_revision' WHERE id = :id",
        id=screened.result_id,
    )
    assert "permission denied" in message


async def test_ac14_screening_results_cannot_be_deleted_by_the_app(screened: Screened) -> None:
    message = await _app_error(
        screened.ctx, "DELETE FROM screening_results WHERE id = :id", id=screened.result_id
    )
    assert "permission denied" in message


async def test_ac14_the_app_cannot_set_who_created_a_screening_result(
    screened: Screened,
) -> None:
    message = await _app_error(
        screened.ctx,
        "INSERT INTO screening_results (id, tenant_id, engagement_id, evidence_version_id, "
        "agent_run_id, action, confidence, rationale, citations, unverified, created_by_kind) "
        "VALUES (:id, :t, :e, :v, :r, 'ready_for_review', 0.9, 'x', '[]', '[]', 'human')",
        id=uuid.uuid4(),
        t=screened.world.tenant_id,
        e=screened.world.engagement_id,
        v=screened.version_id,
        r=screened.run_id,
    )
    assert "permission denied" in message


async def test_ac14_a_screening_result_is_always_created_by_an_agent(
    seed: Seeder, running: Screened
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified, "
            "created_by_kind) VALUES ($1, $2, $3, $4, 'ready_for_review', 0.9, 'x', '[]', '[]', "
            "'human')",
            running.world.tenant_id,
            running.world.engagement_id,
            running.version_id,
            running.run_id,
        )


async def test_ac14_the_default_creator_of_a_screening_result_is_agent(
    seed: Seeder, screened: Screened
) -> None:
    assert (
        await seed.value(
            "SELECT created_by_kind FROM screening_results WHERE id = $1", screened.result_id
        )
        == "agent"
    )


async def test_ac14_a_run_has_at_most_one_screening_result(
    seed: Seeder, screened: Screened
) -> None:
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.run(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) "
            "VALUES ($1, $2, $3, $4, 'ready_for_review', 0.9, 'x', '[]', '[]')",
            screened.world.tenant_id,
            screened.world.engagement_id,
            screened.version_id,
            screened.run_id,
        )


@pytest.mark.parametrize(
    ("action", "confidence", "rationale"),
    [
        ("accepted", Decimal("0.9"), "fine"),
        ("ready_for_review", Decimal("1.5"), "fine"),
        ("ready_for_review", Decimal("-0.1"), "fine"),
        ("ready_for_review", Decimal("0.9"), ""),
        ("ready_for_review", Decimal("0.9"), "x" * 2001),
    ],
)
async def test_ac14_a_screening_result_must_be_a_valid_proposal(
    seed: Seeder, running: Screened, action: str, confidence: Decimal, rationale: str
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, '[]', '[]')",
            running.world.tenant_id,
            running.world.engagement_id,
            running.version_id,
            running.run_id,
            action,
            confidence,
            rationale,
        )


async def test_ac20_a_screening_result_must_belong_to_a_run_of_the_same_engagement(
    seed: Seeder, running: Screened
) -> None:
    other_engagement = await seed.engagement(
        running.world.tenant_id, running.world.entity_id, running.world.requester.user_id
    )
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run(
            "INSERT INTO screening_results (tenant_id, engagement_id, evidence_version_id, "
            "agent_run_id, action, confidence, rationale, citations, unverified) "
            "VALUES ($1, $2, $3, $4, 'ready_for_review', 0.9, 'x', '[]', '[]')",
            running.world.tenant_id,
            other_engagement,
            running.version_id,
            running.run_id,
        )


# --- usage_records: insert-only ------------------------------------------------------------------


async def test_ac16_usage_records_cannot_be_updated_by_the_app(screened: Screened) -> None:
    message = await _app_error(
        screened.ctx,
        "UPDATE usage_records SET cost_usd = 0 WHERE agent_run_id = :id",
        id=screened.run_id,
    )
    assert "permission denied" in message


async def test_ac16_usage_records_cannot_be_deleted_by_the_app(screened: Screened) -> None:
    message = await _app_error(
        screened.ctx, "DELETE FROM usage_records WHERE agent_run_id = :id", id=screened.run_id
    )
    assert "permission denied" in message


async def test_ac16_the_app_cannot_backdate_a_usage_record(screened: Screened) -> None:
    message = await _app_error(
        screened.ctx,
        "INSERT INTO usage_records (id, tenant_id, agent_id, prompt_id, prompt_version, model, "
        "tier, input_tokens, output_tokens, cost_usd, outcome, inputs_hash, created_at) "
        "VALUES (:id, :t, 'a.b', 'p.q', 'v0', 'm', 'small', 1, 1, 0, 'ok', :h, '2020-01-01')",
        id=uuid.uuid4(),
        t=screened.world.tenant_id,
        h="0" * 64,
    )
    assert "permission denied" in message


BAD_USAGE = [
    {"tier": "huge"},
    {"outcome": "maybe"},
    {"input_tokens": -1},
    {"output_tokens": -1},
    {"cost_usd": Decimal("-0.000001")},
    {"inputs_hash": "not-a-hash"},
    {"model": ""},
]


@pytest.mark.parametrize("change", BAD_USAGE, ids=[next(iter(c)) for c in BAD_USAGE])
async def test_ac16_a_usage_record_must_be_well_formed(
    seed: Seeder, world: World, change: dict[str, object]
) -> None:
    values: dict[str, object] = {
        "tier": "small",
        "outcome": "ok",
        "input_tokens": 1,
        "output_tokens": 1,
        "cost_usd": Decimal("0.1"),
        "inputs_hash": "a" * 64,
        "model": "fake-small",
        **change,
    }
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO usage_records (tenant_id, agent_id, prompt_id, prompt_version, model, "
            "tier, input_tokens, output_tokens, cost_usd, outcome, inputs_hash) VALUES ($1, "
            "'a.b', 'p.q', 'v0', $2, $3, $4, $5, $6, $7, $8)",
            world.tenant_id,
            values["model"],
            values["tier"],
            values["input_tokens"],
            values["output_tokens"],
            values["cost_usd"],
            values["outcome"],
            values["inputs_hash"],
        )


@pytest.mark.parametrize(
    "outcome", ["ok", "invalid", "repaired", "budget_refused", "provider_error"]
)
async def test_ac16_every_contract_outcome_is_storable(
    seed: Seeder, world: World, outcome: str
) -> None:
    await seed.run(
        "INSERT INTO usage_records (tenant_id, agent_id, prompt_id, prompt_version, model, "
        "tier, input_tokens, output_tokens, cost_usd, outcome, inputs_hash) VALUES ($1, 'a.b', "
        "'p.q', 'v0', 'fake-small', 'small', 0, 0, 0, $2, $3)",
        world.tenant_id,
        outcome,
        "a" * 64,
    )
    assert await seed.count("usage_records", world.tenant_id) == 1


# --- agent_runs: forward-only --------------------------------------------------------------------


async def test_ac14_agent_runs_cannot_be_deleted_by_the_app(running: Screened) -> None:
    message = await _app_error(
        running.ctx, "DELETE FROM agent_runs WHERE id = :id", id=running.run_id
    )
    assert "permission denied" in message


@pytest.mark.parametrize(
    "assignment",
    [
        "UPDATE agent_runs SET task_scope = ARRAY['evidence.accept'] WHERE id = :id",
        "UPDATE agent_runs SET initiator_user_id = gen_random_uuid() WHERE id = :id",
        "UPDATE agent_runs SET agent_id = 'evidence.other' WHERE id = :id",
        "UPDATE agent_runs SET spec_version = 99 WHERE id = :id",
        "UPDATE agent_runs SET engagement_id = gen_random_uuid() WHERE id = :id",
        "UPDATE agent_runs SET evidence_version_id = NULL WHERE id = :id",
        "UPDATE agent_runs SET tenant_id = gen_random_uuid() WHERE id = :id",
        "UPDATE agent_runs SET started_at = '2020-01-01' WHERE id = :id",
    ],
)
async def test_ac14_what_an_agent_run_was_allowed_cannot_be_changed_by_the_app(
    running: Screened, assignment: str
) -> None:
    message = await _app_error(running.ctx, assignment, id=running.run_id)
    assert "permission denied" in message


async def test_ac14_a_running_run_can_move_forward_to_completed(running: Screened) -> None:
    async with tenant_session(running.ctx) as session:
        row = (
            await session.execute(
                text(
                    "UPDATE agent_runs SET status = 'completed', finished_at = now(), "
                    "context_hash = :h, output = CAST(:o AS jsonb) WHERE id = :id "
                    "RETURNING status"
                ),
                {"id": running.run_id, "h": "b" * 64, "o": json.dumps({"action": "x"})},
            )
        ).scalar_one()
    assert row == "completed"


async def test_ac14_a_finished_run_cannot_be_updated(screened: Screened) -> None:
    message = await _app_error(
        screened.ctx,
        "UPDATE agent_runs SET failure_code = NULL, status = 'running', finished_at = NULL "
        "WHERE id = :id",
        id=screened.run_id,
    )
    assert "finished" in message


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE agent_runs SET status = 'escalated', finished_at = now() WHERE id = :id",
        "UPDATE agent_runs SET status = 'failed', finished_at = now(), "
        "failure_code = 'boom' WHERE id = :id",
        "UPDATE agent_runs SET status = 'completed', finished_at = now() WHERE id = :id",
    ],
    ids=["escalated", "failed", "completed"],
)
async def test_ac14_a_finished_run_cannot_change_to_another_final_state(
    screened: Screened, statement: str
) -> None:
    message = await _app_error(screened.ctx, statement, id=screened.run_id)
    assert "finished" in message


async def test_ac14_the_context_hash_is_write_once(running: Screened) -> None:
    with pytest.raises(DBAPIError) as raised:
        async with tenant_session(running.ctx) as session:
            await session.execute(
                text("UPDATE agent_runs SET context_hash = :h WHERE id = :id"),
                {"id": running.run_id, "h": "a" * 64},
            )
            await session.execute(
                text("UPDATE agent_runs SET context_hash = :h WHERE id = :id"),
                {"id": running.run_id, "h": "b" * 64},
            )
    assert "write-once" in str(raised.value)


async def test_ac14_the_output_is_write_once(running: Screened) -> None:
    with pytest.raises(DBAPIError) as raised:
        async with tenant_session(running.ctx) as session:
            await session.execute(
                text("UPDATE agent_runs SET output = CAST(:o AS jsonb) WHERE id = :id"),
                {"id": running.run_id, "o": json.dumps({"action": "ready_for_review"})},
            )
            await session.execute(
                text("UPDATE agent_runs SET output = CAST(:o AS jsonb) WHERE id = :id"),
                {"id": running.run_id, "o": json.dumps({"action": "needs_revision"})},
            )
    assert "write-once" in str(raised.value)


async def test_ac14_writing_the_same_context_hash_again_is_harmless(running: Screened) -> None:
    async with tenant_session(running.ctx) as session:
        for _ in range(2):
            await session.execute(
                text("UPDATE agent_runs SET context_hash = :h WHERE id = :id"),
                {"id": running.run_id, "h": "a" * 64},
            )


async def test_ac14_the_forward_only_rule_binds_the_owner_too(
    seed: Seeder, screened: Screened
) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run(
            "UPDATE agent_runs SET failure_code = 'late' WHERE id = $1", screened.run_id
        )


@pytest.mark.parametrize(
    "assignment",
    [
        "UPDATE agent_runs SET status = 'completed' WHERE id = $1",
        "UPDATE agent_runs SET status = 'failed', finished_at = now() WHERE id = $1",
        "UPDATE agent_runs SET status = 'running', finished_at = now() WHERE id = $1",
        "UPDATE agent_runs SET status = 'paused' WHERE id = $1",
        "UPDATE agent_runs SET context_hash = 'short' WHERE id = $1",
        "UPDATE agent_runs SET failure_code = 'Not A Code' WHERE id = $1",
    ],
)
async def test_ac14_an_agent_run_must_be_in_a_consistent_state(
    seed: Seeder, running: Screened, assignment: str
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(assignment, running.run_id)


async def test_ac14_one_agent_run_per_agent_and_source_event(
    seed: Seeder, running: Screened
) -> None:
    event_id = cast(
        uuid.UUID,
        await seed.value("SELECT source_event_id FROM agent_runs WHERE id = $1", running.run_id),
    )
    with pytest.raises(asyncpg.UniqueViolationError):
        await seed.run(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "evidence_version_id, initiator_user_id, source_event_id, task_scope) "
            "VALUES ($1, $2, 1, $3, $4, $5, $6, ARRAY['evidence.read'])",
            running.world.tenant_id,
            SCREENER,
            running.world.engagement_id,
            running.version_id,
            running.world.requester.user_id,
            event_id,
        )


async def test_ac14_the_initiator_must_be_a_member_of_the_firm(
    seed: Seeder, running: Screened
) -> None:
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await seed.run(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope) VALUES ($1, $2, 1, $3, $4, ARRAY['evidence.read'])",
            running.world.tenant_id,
            SCREENER,
            running.world.engagement_id,
            uuid.uuid4(),
        )


@pytest.mark.parametrize("agent_id", ["Evidence.Screener", "screener", "evidence.", ".screener"])
async def test_ac14_an_agent_id_must_look_like_an_agent_id(
    seed: Seeder, running: Screened, agent_id: str
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope) VALUES ($1, $2, 1, $3, $4, ARRAY['evidence.read'])",
            running.world.tenant_id,
            agent_id,
            running.world.engagement_id,
            running.world.requester.user_id,
        )
