"""SPEC-003 AC-6, AC-14: the slot wait loop and the release of both workflows (TASK-018 interface
contract 018b, "Workflows", and contract revision 1; ADR-017, ADR-090).

The loop is copied into each module's `workflows.py` (workflows may not share code across modules,
ADR-017), so a test keeps the two identical. Its behaviour is checked offline by replacing the
`workflow` module of each file with a fake clock: asks, durable sleeps, jitter and the maximum wait
are driven without a server. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import ModuleType, SimpleNamespace
from typing import Any, cast

import pytest
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError
from temporalio.workflow import ActivityCancellationType

from abacus.modules.agents import workflows as screening
from abacus.modules.agents.workflow_types import RunInput
from abacus.modules.agents.workflow_types import SlotGrant as ScreeningGrant
from abacus.modules.connections import workflows as retrieval
from abacus.modules.connections.workflow_types import RetrievalInput
from abacus.modules.connections.workflow_types import SlotGrant as RetrievalGrant

MODULES = [retrieval, screening]
IDS = ["retrieval", "screening"]
Wait = Callable[[str, object], Awaitable[bool]]


def _function(module: ModuleType, name: str) -> ast.AsyncFunctionDef:
    tree = ast.parse(inspect.getsource(module))
    [found] = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == name]
    return found


def _without_docstring(node: ast.AsyncFunctionDef) -> str:
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return "\n".join(ast.dump(statement) for statement in body)


# --- the two loops are the same code -------------------------------------------------------------


def test_ac6_the_two_modules_wait_for_slot_bodies_are_identical() -> None:
    first, second = (_function(m, "wait_for_slot") for m in MODULES)
    assert ast.dump(first.args) == ast.dump(second.args)
    assert first.returns is not None
    assert second.returns is not None
    assert ast.dump(first.returns) == ast.dump(second.returns)
    assert _without_docstring(first) == _without_docstring(second)


def test_ac6_the_two_modules_release_bodies_are_identical() -> None:
    first, second = (_function(m, "_release") for m in MODULES)
    assert ast.dump(first.args) == ast.dump(second.args)
    assert _without_docstring(first) == _without_docstring(second)


def test_ac6_the_ast_comparison_would_notice_a_difference() -> None:
    one = ast.parse("async def f():\n    return 1\n").body[0]
    two = ast.parse("async def f():\n    return 2\n").body[0]
    assert isinstance(one, ast.AsyncFunctionDef)
    assert isinstance(two, ast.AsyncFunctionDef)
    assert _without_docstring(one) != _without_docstring(two)


# --- a fake of the parts of `temporalio.workflow` the loop uses ----------------------------------


@dataclass
class Clock:
    """Asks answer from `grants` (the last repeats); sleeps advance the clock."""

    grants: list[object]
    jitter: float = 0.5
    start: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    now: datetime = field(init=False)
    asks: list[dict[str, Any]] = field(default_factory=lambda: [])  # a recorded call
    sleeps: list[float] = field(default_factory=lambda: [])

    def __post_init__(self) -> None:
        self.now = self.start

    def namespace(self) -> SimpleNamespace:
        async def execute_activity(activity: str, arg: object, **kwargs: object) -> object:
            self.asks.append({"activity": activity, "arg": arg, **kwargs})
            return self.grants.pop(0) if len(self.grants) > 1 else self.grants[0]

        async def sleep(duration: timedelta) -> None:
            self.sleeps.append(duration.total_seconds())
            self.now += duration

        return SimpleNamespace(
            now=lambda: self.now,
            execute_activity=execute_activity,
            sleep=sleep,
            random=lambda: SimpleNamespace(random=lambda: self.jitter),
        )


def _wait(module: ModuleType, clock: Clock, monkeypatch: pytest.MonkeyPatch) -> Wait:
    monkeypatch.setattr(module, "workflow", clock.namespace())
    return cast(Wait, module.wait_for_slot)


def _grant(module: ModuleType, granted: bool, max_wait: int) -> object:
    cls = RetrievalGrant if module is retrieval else ScreeningGrant
    return cls(granted, max_wait)


def _arg(module: ModuleType) -> object:
    return RetrievalInput("t", "r") if module is retrieval else RunInput("t", "r")


# --- asking and sleeping -------------------------------------------------------------------------


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_a_granted_first_ask_returns_at_once_without_sleeping(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([_grant(module, True, 120)])
    assert await _wait(module, clock, monkeypatch)("x.acquire_slot", _arg(module)) is True
    assert len(clock.asks) == 1
    assert clock.sleeps == []


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_it_asks_the_given_activity_with_the_given_argument(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([_grant(module, True, 120)])
    argument = _arg(module)
    await _wait(module, clock, monkeypatch)("some.acquire_slot", argument)
    [ask] = clock.asks
    assert (ask["activity"], ask["arg"]) == ("some.acquire_slot", argument)
    assert ask["result_type"] in (RetrievalGrant, ScreeningGrant)


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_asks_wait_for_cancellation_to_complete_so_the_release_follows_them(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([_grant(module, True, 120)])
    await _wait(module, clock, monkeypatch)("x", _arg(module))
    [ask] = clock.asks
    assert ask["cancellation_type"] == ActivityCancellationType.WAIT_CANCELLATION_COMPLETED


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_asks_do_not_count_waiting_as_failed_attempts_but_are_bounded(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([_grant(module, True, 120)])
    await _wait(module, clock, monkeypatch)("x", _arg(module))
    [ask] = clock.asks
    policy = ask["retry_policy"]
    assert isinstance(policy, RetryPolicy)
    assert policy.maximum_attempts >= 1
    assert ask["start_to_close_timeout"] <= timedelta(minutes=10)


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_the_backoff_starts_at_one_second_doubles_and_is_capped_at_sixty(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    waiting = _grant(module, False, 100_000)
    clock = Clock([waiting] * 12 + [_grant(module, True, 100_000)], jitter=0.5)  # factor 1.0
    assert await _wait(module, clock, monkeypatch)("x", _arg(module)) is True
    assert clock.sleeps[:7] == [1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 60.0]
    assert max(clock.sleeps) == 60.0
    assert clock.sleeps[6:] == [60.0] * (len(clock.sleeps) - 6)


@pytest.mark.parametrize("module", MODULES, ids=IDS)
@pytest.mark.parametrize(("jitter", "factor"), [(0.0, 0.5), (0.5, 1.0), (1.0, 1.5)])
async def test_ac6_each_sleep_is_jittered_by_half_to_one_and_a_half(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch, jitter: float, factor: float
) -> None:
    clock = Clock(
        [_grant(module, False, 100_000)] * 3 + [_grant(module, True, 100_000)], jitter=jitter
    )
    await _wait(module, clock, monkeypatch)("x", _arg(module))
    assert clock.sleeps == pytest.approx([1.0 * factor, 2.0 * factor, 4.0 * factor])


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_a_waiting_run_asks_again_after_each_sleep_until_granted(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([_grant(module, False, 600)] * 4 + [_grant(module, True, 600)])
    assert await _wait(module, clock, monkeypatch)("x", _arg(module)) is True
    assert len(clock.asks) == 5
    assert len(clock.sleeps) == 4


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac14_it_gives_up_once_the_max_wait_has_passed_since_the_first_ask(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([_grant(module, False, 10)], jitter=0.5)
    assert await _wait(module, clock, monkeypatch)("x", _arg(module)) is False
    waited = sum(clock.sleeps)
    assert waited >= 10  # never gives up early
    assert waited - clock.sleeps[-1] < 10  # and not a sleep later than needed
    assert len(clock.asks) == len(clock.sleeps) + 1  # the last ask is the one that saw the limit


@pytest.mark.parametrize("module", MODULES, ids=IDS)
@pytest.mark.parametrize("max_wait", [1, 2, 120, 600])
async def test_ac14_the_wait_ends_within_one_backoff_of_the_max_wait(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch, max_wait: int
) -> None:
    clock = Clock([_grant(module, False, max_wait)], jitter=0.5)
    assert await _wait(module, clock, monkeypatch)("x", _arg(module)) is False
    waited = sum(clock.sleeps)
    assert max_wait <= waited <= max_wait + 60


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac14_a_slot_granted_on_the_last_ask_is_still_a_grant(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([_grant(module, False, 3), _grant(module, False, 3), _grant(module, True, 3)])
    assert await _wait(module, clock, monkeypatch)("x", _arg(module)) is True


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac14_the_max_wait_comes_from_each_answer_so_a_changed_setting_applies(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([_grant(module, False, 100_000), _grant(module, False, 1)], jitter=0.5)
    assert await _wait(module, clock, monkeypatch)("x", _arg(module)) is False
    assert len(clock.asks) == 2


# --- release -------------------------------------------------------------------------------------


def _release(module: ModuleType, monkeypatch: pytest.MonkeyPatch, clock: Clock) -> Wait:
    monkeypatch.setattr(module, "workflow", clock.namespace())
    return cast(Wait, module._release)


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_release_makes_at_most_five_attempts_within_an_hour(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([None])
    await _release(module, monkeypatch, clock)("x.release_slot", _arg(module))
    [call] = clock.asks
    assert call["activity"] == "x.release_slot"
    assert call["retry_policy"].maximum_attempts == 5
    assert call["schedule_to_close_timeout"] <= timedelta(hours=1)


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_a_release_that_fails_is_swallowed_and_never_changes_the_outcome(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([None])
    namespace = clock.namespace()

    async def failing(activity: str, arg: object, **kwargs: object) -> object:
        raise ActivityError(
            "failed",
            scheduled_event_id=1,
            started_event_id=2,
            identity="x",
            activity_type=activity,
            activity_id="1",
            retry_state=None,
        )

    namespace.execute_activity = failing
    monkeypatch.setattr(module, "workflow", namespace)
    assert await module._release("x.release_slot", _arg(module)) is None


@pytest.mark.parametrize("module", MODULES, ids=IDS)
async def test_ac6_a_release_does_not_swallow_other_errors(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = Clock([None])
    namespace = clock.namespace()

    async def failing(activity: str, arg: object, **kwargs: object) -> object:
        raise RuntimeError("a bug in the workflow, not the activity")

    namespace.execute_activity = failing
    monkeypatch.setattr(module, "workflow", namespace)
    with pytest.raises(RuntimeError):
        await module._release("x.release_slot", _arg(module))
