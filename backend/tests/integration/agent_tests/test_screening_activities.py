"""AC-14, AC-16, AC-17: the screening activities (TASK-011b interface contract, "Workflow
`screening`") run with `ActivityEnvironment` against a real database, storage and `FakeModel`.

Errors cross to Temporal as `ApplicationError`s whose message and type are the exception's class
name only; terminal errors are non-retryable and the others retryable. A retry after the work was
done reports what was recorded. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterator
from typing import cast

import pytest
from pydantic import BaseModel
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from abacus.ai_gateway import (
    BudgetExceeded,
    ContextTooLarge,
    DatasetTooLarge,
    FakeModel,
    GatewayCall,
    GatewayRefused,
    GatewayResult,
    ModelRequest,
    ProviderError,
    configure_provider,
)
from abacus.kernel.errors import NotFound
from abacus.modules.agents import activities, service
from abacus.modules.agents.activities import (
    INITIATOR_INACTIVE,
    create_run_activity,
    fail_run_activity,
    screen_activity,
)
from abacus.modules.agents.api import (
    SCREEN_PROMPT,
    SCREENER,
    SheetLayoutError,
    fail_run,
    screening_responder,
    spec,
)
from abacus.modules.agents.workflow_types import (
    FailInput,
    RunInput,
    ScreeningInput,
    ScreeningOutcome,
)
from abacus.modules.identity.api import Forbidden

from .support import Seeder, World, retrieve, uploaded_version

LEAKED = "leak-marker-ledger-value-123456"
INVALID = "this is not json at all, and it is long enough to carry some tokens " * 3


class Model:
    """The configured provider: counts requests and answers through `reply` (default: stock)."""

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []
        self.reply: Callable[[ModelRequest], str] = screening_responder
        fake = FakeModel()
        fake.respond(SCREEN_PROMPT, self._respond)
        configure_provider(fake)

    def _respond(self, request: ModelRequest) -> str:
        self.requests.append(request)
        return self.reply(request)


@pytest.fixture
def model() -> Model:
    return Model()


@pytest.fixture(autouse=True)
def _reset_provider() -> Iterator[None]:
    yield
    configure_provider(None)


async def _run(
    activity_fn: Callable[[object], Awaitable[object]] | object, argument: object
) -> object:
    env = ActivityEnvironment()
    return await env.run(cast("Callable[[object], Awaitable[object]]", activity_fn), argument)


async def _expect_error(activity_fn: object, argument: object) -> ApplicationError:
    with pytest.raises(ApplicationError) as caught:
        await _run(activity_fn, argument)
    return caught.value


def _input(world: World, version_id: uuid.UUID, requested_by: uuid.UUID | None) -> ScreeningInput:
    return ScreeningInput(
        str(world.tenant_id),
        str(version_id),
        str(uuid.uuid4()),
        str(requested_by) if requested_by else None,
    )


async def _row(seed: Seeder, run_id: str) -> tuple[str, str | None]:
    [row] = await seed.rows(
        "SELECT status, failure_code FROM agent_runs WHERE id = $1", uuid.UUID(run_id)
    )
    return str(row["status"]), cast("str | None", row["failure_code"])


async def _created_run(world: World) -> tuple[uuid.UUID, RunInput]:
    result = await retrieve(world)
    made = await _run(
        create_run_activity, _input(world, result.evidence_version_id, world.requester.user_id)
    )
    assert isinstance(made, str)
    return result.evidence_version_id, RunInput(str(world.tenant_id), made)


# --- screening.create_run ------------------------------------------------------------------------


async def test_ac14_create_run_returns_the_run_id_and_is_idempotent_per_event(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    given = _input(world, result.evidence_version_id, world.requester.user_id)
    first = await _run(create_run_activity, given)
    second = await _run(create_run_activity, given)
    assert isinstance(first, str)
    assert uuid.UUID(first)
    assert second == first
    assert await seed.count("agent_runs", world.tenant_id) == 1
    assert await _row(seed, first) == ("running", None)


async def test_ac14_create_run_returns_none_without_a_requester(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    assert await _run(create_run_activity, _input(world, result.evidence_version_id, None)) is None
    assert await seed.count("agent_runs", world.tenant_id) == 0


async def test_ac14_create_run_returns_none_for_a_requester_without_an_active_membership(
    seed: Seeder, world: World
) -> None:
    result = await retrieve(world)
    await seed.revoke(world.requester)
    given = _input(world, result.evidence_version_id, world.requester.user_id)
    assert await _run(create_run_activity, given) is None
    assert await seed.count("agent_runs", world.tenant_id) == 0


async def test_ac14_create_run_returns_none_for_a_version_without_a_snapshot(
    seed: Seeder, world: World
) -> None:
    version_id = await uploaded_version(seed, world)
    given = _input(world, version_id, world.requester.user_id)
    assert await _run(create_run_activity, given) is None
    assert await seed.count("agent_runs", world.tenant_id) == 0


async def test_ac14_create_run_for_a_missing_version_is_a_non_retryable_not_found(
    seed: Seeder, world: World
) -> None:
    error = await _expect_error(
        create_run_activity, _input(world, uuid.uuid4(), world.requester.user_id)
    )
    assert (error.message, error.type, error.non_retryable) == ("NotFound", "NotFound", True)
    assert await seed.count("agent_runs", world.tenant_id) == 0


async def test_ac14_create_run_infrastructure_errors_are_retryable_and_carry_only_the_class(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(*args: object) -> uuid.UUID:
        raise ConnectionError(LEAKED)

    monkeypatch.setattr(activities, "create_screening_run", broken)
    error = await _expect_error(
        create_run_activity, _input(world, uuid.uuid4(), world.requester.user_id)
    )
    assert (error.message, error.type, error.non_retryable) == (
        "ConnectionError",
        "ConnectionError",
        False,
    )
    assert LEAKED not in str(error)


# --- screening.screen ----------------------------------------------------------------------------


async def test_ac14_screen_completes_with_the_recorded_result(
    seed: Seeder, world: World, model: Model
) -> None:
    version_id, run = await _created_run(world)
    outcome = await _run(screen_activity, run)
    assert isinstance(outcome, ScreeningOutcome)
    assert outcome.status == "completed"
    assert outcome.run_id == run.run_id
    assert outcome.code is None
    [result] = await seed.rows(
        "SELECT id, created_by_kind, evidence_version_id FROM screening_results "
        "WHERE tenant_id = $1",
        world.tenant_id,
    )
    assert outcome.screening_result_id == str(result["id"])
    assert (result["created_by_kind"], result["evidence_version_id"]) == ("agent", version_id)
    assert await _row(seed, run.run_id) == ("completed", None)
    assert len(model.requests) == 1


async def test_ac16_screen_records_one_usage_row_for_the_call(
    seed: Seeder, world: World, model: Model
) -> None:
    _, run = await _created_run(world)
    await _run(screen_activity, run)
    [usage] = await seed.rows(
        "SELECT outcome, agent_run_id, engagement_id FROM usage_records WHERE tenant_id = $1",
        world.tenant_id,
    )
    assert usage["outcome"] == "ok"
    assert str(usage["agent_run_id"]) == run.run_id
    assert usage["engagement_id"] == world.engagement_id


async def test_ac14_a_retry_after_completion_returns_the_recorded_outcome_without_a_model_call(
    seed: Seeder, world: World, model: Model
) -> None:
    _, run = await _created_run(world)
    first = await _run(screen_activity, run)
    second = await _run(screen_activity, run)
    assert second == first
    assert len(model.requests) == 1
    assert await seed.count("screening_results", world.tenant_id) == 1
    assert await seed.count("usage_records", world.tenant_id) == 1


async def test_ac14_screen_escalates_after_invalid_output_twice_and_a_retry_reports_it(
    seed: Seeder, world: World, model: Model
) -> None:
    model.reply = lambda request: INVALID
    _, run = await _created_run(world)
    outcome = await _run(screen_activity, run)
    assert outcome == ScreeningOutcome("escalated", run.run_id, None, None)
    assert len(model.requests) == 2  # the attempt and its one repair
    assert await seed.count("screening_results", world.tenant_id) == 0
    assert (await _row(seed, run.run_id))[0] == "escalated"
    assert await _run(screen_activity, run) == outcome
    assert len(model.requests) == 2


async def test_ac17_a_lost_initiator_ends_the_run_as_initiator_inactive_without_an_error(
    seed: Seeder, world: World, model: Model
) -> None:
    _, run = await _created_run(world)
    await seed.revoke(world.requester)
    outcome = await _run(screen_activity, run)
    assert INITIATOR_INACTIVE == "initiator_inactive"
    assert outcome == ScreeningOutcome("failed", run.run_id, "initiator_inactive", None)
    assert await _row(seed, run.run_id) == ("failed", "initiator_inactive")
    assert model.requests == []
    assert await seed.count("screening_results", world.tenant_id) == 0
    assert "agent_run.failed" in await seed.actions(world.tenant_id)


async def test_ac14_a_run_already_failed_reports_its_status_and_code(
    seed: Seeder, world: World, model: Model
) -> None:
    _, run = await _created_run(world)
    assert await fail_run(world.tenant_id, uuid.UUID(run.run_id), "internal_error") is True
    outcome = await _run(screen_activity, run)
    assert outcome == ScreeningOutcome("failed", run.run_id, "internal_error", None)
    assert model.requests == []


async def test_ac14_an_unknown_run_is_a_non_retryable_not_found(world: World) -> None:
    error = await _expect_error(screen_activity, RunInput(str(world.tenant_id), str(uuid.uuid4())))
    assert (error.message, error.type, error.non_retryable) == ("NotFound", "NotFound", True)


@pytest.mark.parametrize(
    "raised",
    [
        SheetLayoutError(LEAKED),
        DatasetTooLarge(LEAKED),
        ContextTooLarge(LEAKED),
        BudgetExceeded(LEAKED),
        GatewayRefused(LEAKED),
        Forbidden("evidence.read", "delegation"),
        NotFound(LEAKED),
    ],
    ids=lambda e: type(e).__name__,
)
async def test_ac14_terminal_errors_are_non_retryable_and_carry_only_the_class_name(
    world: World, model: Model, monkeypatch: pytest.MonkeyPatch, raised: Exception
) -> None:
    _, run = await _created_run(world)

    async def screen(agent: object) -> object:
        raise raised

    monkeypatch.setattr(activities, "screen", screen)
    error = await _expect_error(screen_activity, run)
    name = type(raised).__name__
    assert (error.message, error.type, error.non_retryable) == (name, name, True)
    assert LEAKED not in str(error)
    assert error.__cause__ is None or LEAKED not in str(error.__cause__)


@pytest.mark.parametrize(
    "raised",
    [ProviderError(LEAKED), RuntimeError(LEAKED), ConnectionError(LEAKED), ValueError(LEAKED)],
    ids=lambda e: type(e).__name__,
)
async def test_ac14_provider_and_other_errors_are_retryable_with_only_the_class_name(
    world: World, model: Model, monkeypatch: pytest.MonkeyPatch, raised: Exception
) -> None:
    _, run = await _created_run(world)

    async def screen(agent: object) -> object:
        raise raised

    monkeypatch.setattr(activities, "screen", screen)
    error = await _expect_error(screen_activity, run)
    name = type(raised).__name__
    assert (error.message, error.type, error.non_retryable) == (name, name, False)
    assert LEAKED not in str(error)


async def test_ac14_an_unexpected_error_loading_the_context_is_retryable(
    world: World, model: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run = await _created_run(world)

    async def broken(*args: object) -> object:
        raise ConnectionError(LEAKED)

    monkeypatch.setattr(activities, "load_agent_context", broken)
    error = await _expect_error(screen_activity, run)
    assert (error.message, error.type, error.non_retryable) == (
        "ConnectionError",
        "ConnectionError",
        False,
    )


async def test_ac17_a_real_forbidden_fails_the_run_and_is_non_retryable(
    seed: Seeder, world: World, model: Model
) -> None:
    _, run = await _created_run(world)
    # Still an active member of the firm, but no longer on the engagement.
    await seed.unmember(world.engagement_id, world.requester)
    error = await _expect_error(screen_activity, run)
    assert (error.message, error.type, error.non_retryable) == ("Forbidden", "Forbidden", True)
    assert await _row(seed, run.run_id) == ("failed", "forbidden")
    assert model.requests == []
    assert await seed.count("screening_results", world.tenant_id) == 0
    # A retry of the activity reports the recorded failure.
    again = await _run(screen_activity, run)
    assert again == ScreeningOutcome("failed", run.run_id, "forbidden", None)


async def test_ac14_a_real_provider_error_is_retryable_and_leaves_the_run_running(
    seed: Seeder, world: World, model: Model
) -> None:
    def down(request: ModelRequest) -> str:
        raise ProviderError(LEAKED)

    model.reply = down
    _, run = await _created_run(world)
    error = await _expect_error(screen_activity, run)
    assert (error.message, error.type, error.non_retryable) == (
        "ProviderError",
        "ProviderError",
        False,
    )
    assert await _row(seed, run.run_id) == ("running", None)
    [usage] = await seed.rows(
        "SELECT outcome FROM usage_records WHERE tenant_id = $1", world.tenant_id
    )
    assert usage["outcome"] == "provider_error"
    # The provider recovers: the retry completes the same run.
    model.reply = screening_responder
    outcome = await _run(screen_activity, run)
    assert isinstance(outcome, ScreeningOutcome)
    assert outcome.status == "completed"
    assert outcome.screening_result_id is not None


async def test_ac16_the_runs_budget_covers_every_attempt(
    seed: Seeder, world: World, model: Model
) -> None:
    _, run = await _created_run(world)
    await seed.run(
        "INSERT INTO usage_records (tenant_id, engagement_id, agent_id, agent_run_id, "
        "prompt_id, prompt_version, model, tier, input_tokens, output_tokens, cost_usd, "
        "outcome, inputs_hash) VALUES ($1, $2, $3, $4, 'evidence.screen', 'v0', 'fake-small', "
        "'small', 1, 1, $5, 'ok', $6)",
        world.tenant_id,
        world.engagement_id,
        SCREENER,
        uuid.UUID(run.run_id),
        spec(SCREENER).limits.max_cost_usd,
        "a" * 64,
    )
    error = await _expect_error(screen_activity, run)
    assert (error.message, error.type, error.non_retryable) == (
        "BudgetExceeded",
        "BudgetExceeded",
        True,
    )
    assert await _row(seed, run.run_id) == ("failed", "budget_exceeded")
    assert model.requests == []


async def test_ac14_screen_bounds_the_provider_call_by_the_specs_max_seconds(
    world: World, model: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[GatewayCall[BaseModel]] = []
    real = service.call

    async def spy(call: GatewayCall[BaseModel]) -> GatewayResult[BaseModel]:
        seen.append(call)
        return await real(call)

    monkeypatch.setattr(service, "call", spy)
    _, run = await _created_run(world)
    await _run(screen_activity, run)
    [sent] = seen
    assert sent.timeout_seconds == spec(SCREENER).limits.max_seconds
    assert sent.timeout_seconds > 0


# --- screening.fail_run --------------------------------------------------------------------------


@pytest.mark.parametrize("code", ["cancelled", "provider_unavailable", "internal_error"])
async def test_ac14_fail_run_ends_a_running_run_with_the_code(
    seed: Seeder, world: World, model: Model, code: str
) -> None:
    _, run = await _created_run(world)
    outcome = await _run(fail_run_activity, FailInput(run.tenant_id, run.run_id, code))
    assert outcome == ScreeningOutcome("failed", run.run_id, code, None)
    assert await _row(seed, run.run_id) == ("failed", code)
    assert "agent_run.failed" in await seed.actions(world.tenant_id)


@pytest.mark.parametrize("code", ["forbidden", "made_up", "", "x" * 300])
async def test_ac14_fail_run_records_internal_error_for_a_code_it_does_not_know(
    seed: Seeder, world: World, model: Model, code: str
) -> None:
    _, run = await _created_run(world)
    outcome = await _run(fail_run_activity, FailInput(run.tenant_id, run.run_id, code))
    assert outcome == ScreeningOutcome("failed", run.run_id, "internal_error", None)
    assert await _row(seed, run.run_id) == ("failed", "internal_error")


async def test_ac14_fail_run_on_a_finished_run_changes_nothing_and_reports_its_outcome(
    seed: Seeder, world: World, model: Model
) -> None:
    _, run = await _created_run(world)
    done = await _run(screen_activity, run)
    before = len(await seed.actions(world.tenant_id))
    again = await _run(fail_run_activity, FailInput(run.tenant_id, run.run_id, "cancelled"))
    assert again == done
    assert await _row(seed, run.run_id) == ("completed", None)
    assert len(await seed.actions(world.tenant_id)) == before


async def test_ac14_fail_run_twice_records_the_first_code(
    seed: Seeder, world: World, model: Model
) -> None:
    _, run = await _created_run(world)
    await _run(fail_run_activity, FailInput(run.tenant_id, run.run_id, "cancelled"))
    again = await _run(fail_run_activity, FailInput(run.tenant_id, run.run_id, "internal_error"))
    assert again == ScreeningOutcome("failed", run.run_id, "cancelled", None)
    failed = [a for a in await seed.actions(world.tenant_id) if a == "agent_run.failed"]
    assert len(failed) == 1


async def test_ac14_fail_run_for_an_unknown_run_is_a_non_retryable_not_found(
    world: World,
) -> None:
    error = await _expect_error(
        fail_run_activity, FailInput(str(world.tenant_id), str(uuid.uuid4()), "cancelled")
    )
    assert (error.message, error.type, error.non_retryable) == ("NotFound", "NotFound", True)


async def test_ac14_a_concurrent_attempt_is_a_retryable_agent_run_busy(
    seed: Seeder, world: World, model: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def busy(session: object, run_id: uuid.UUID) -> bool:
        return False

    monkeypatch.setattr(service, "try_lock_run", busy)
    _, run = await _created_run(world)
    error = await _expect_error(screen_activity, run)
    assert (error.message, error.type, error.non_retryable) == (
        "AgentRunBusy",
        "AgentRunBusy",
        False,
    )
    assert await _row(seed, run.run_id) == ("running", None)
    assert model.requests == []


async def test_ac14_database_errors_in_fail_run_cross_as_class_name_only_and_retryable(
    world: World, model: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run = await _created_run(world)

    async def broken(tenant_id: uuid.UUID, run_id: uuid.UUID) -> object:
        raise ConnectionError(LEAKED)

    monkeypatch.setattr(activities, "run_outcome", broken)
    error = await _expect_error(
        fail_run_activity, FailInput(run.tenant_id, run.run_id, "cancelled")
    )
    assert (error.message, error.type, error.non_retryable) == (
        "ConnectionError",
        "ConnectionError",
        False,
    )
    assert LEAKED not in str(error)


async def test_ac14_database_errors_inside_screen_cross_as_class_name_only_and_retryable(
    world: World, model: Model, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, run = await _created_run(world)

    async def broken(tenant_id: uuid.UUID, run_id: uuid.UUID) -> object:
        raise ConnectionError(LEAKED)

    monkeypatch.setattr(activities, "run_outcome", broken)
    await _run(screen_activity, run)  # completes
    error = await _expect_error(screen_activity, run)  # already ended: reads run_outcome
    assert (error.message, error.type, error.non_retryable) == (
        "ConnectionError",
        "ConnectionError",
        False,
    )
    assert LEAKED not in str(error)
