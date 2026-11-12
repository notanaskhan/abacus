"""P-10-T52 (ADR-079; DEC-4402): runtime v2's mutation scopes, their floors, the p95 budgets, and
survivor triage for the pure rules the weekly run mutates first: plan validation (every code and
its boundary), the parallel cap, readiness, failure propagation, the aggregate state's order, the
schedule's retry and redirect, and the SSE frame's size boundary."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from abacus.kernel import realtime
from abacus.modules.agents.run_plan import (
    MAX_PARALLEL,
    PlanContext,
    PlanStep,
    Schedule,
    aggregate,
    blocked_by_failure,
    cap,
    ready,
    reserved,
    validate_plan,
)
from abacus_tools.loadtest import p10_budgets
from abacus_tools.quality import mutation
from abacus_tools.quality.mutation_floors import FILE, parse

HANNAH = "00000000-0000-4000-8000-00000000a001"
CLIENT = "00000000-0000-4000-8000-00000000c001"


def _step(key: str, level: int = 0, **extra: object) -> PlanStep:
    raw: dict[str, object] = {"key": key, "level": level, "kind": "tool", "tool": "t.read"}
    raw.update(extra)
    return PlanStep.parse(raw)


def _ctx(**extra: object) -> PlanContext:
    base: dict[str, object] = {
        "declared_writes": frozenset({"file.save"}),
        "client_scope": frozenset({CLIENT}),
        "approver_holds": {(HANNAH, "file.save"): True},
        "tool_actions": {"t.read": "engagement.read", "t.save": "file.save"},
    }
    base.update(extra)
    return PlanContext(**base)  # pyright: ignore[reportArgumentType] -- test fixture


# --- scopes, floors and budgets ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "scope"),
    [
        ("src/abacus/modules/agents/run_plan.py", "agents/runtime"),
        ("src/abacus/modules/agents/run_workflow.py", "agents/runtime"),
        ("src/abacus/modules/agents/run_activities.py", "agents/runtime"),
        ("src/abacus/modules/agents/run_waits.py", "agents/runtime"),
        ("src/abacus/modules/agents/commands.py", "agents/runtime"),
        ("src/abacus/modules/agents/approved_writes.py", "agents/runtime"),
        ("src/abacus/modules/agents/proposal_undo.py", "agents/runtime"),
        ("src/abacus/modules/agents/session_turns.py", "agents/runtime"),
        ("src/abacus/modules/agents/harness.py", "agents/runtime"),
        ("src/abacus/modules/agents/tools/runtime.py", "agents/runtime"),
        ("src/abacus/kernel/realtime.py", "kernel/realtime"),
        ("src/abacus/ai_gateway/converse.py", "ai_gateway"),
    ],
)
def test_the_runtime_files_are_red_scopes(path: str, scope: str) -> None:
    assert mutation.scope_of(path) == scope


def test_the_new_scopes_have_floors_and_files() -> None:
    floors = parse(FILE.read_text())
    assert {"agents/runtime", "kernel/realtime", "ai_gateway"} <= set(floors)
    red = mutation.red_files()
    assert "src/abacus/kernel/realtime.py" in red
    assert sum(1 for p in red if mutation.scope_of(p) == "agents/runtime") == 12


def test_the_budgets_and_their_breaches() -> None:
    assert {b.name: b.p95_ms for b in p10_budgets.BUDGETS} == {
        "plan_approve": Decimal(400),
        "stream_first_byte": Decimal(500),
    }
    ok = {b.name: b.p95_ms for b in p10_budgets.BUDGETS}
    assert p10_budgets.breaches(ok) == []
    slow = {**ok, "plan_approve": Decimal(401)}
    assert p10_budgets.breaches(slow) == ["plan_approve: p95 401 ms > 400 ms"]
    missing = p10_budgets.breaches({"plan_approve": Decimal(1)})
    assert missing == ["stream_first_byte: not measured"]


# --- validate_plan: every code, once, in step order ----------------------------------------------


def test_a_valid_plan_has_no_problems() -> None:
    steps = [
        _step("read", 0, reads_clients=[CLIENT]),
        _step(
            "save",
            1,
            tool="t.save",
            depends_on=["read"],
            writes=["file.save"],
            approver_user_id=HANNAH,
        ),
    ]
    assert validate_plan(steps, _ctx()) == []


def test_an_empty_plan_is_refused_alone() -> None:
    assert validate_plan([], _ctx()) == ["empty_plan"]


@pytest.mark.parametrize(
    ("steps", "code"),
    [
        ([_step("a"), _step("a")], "duplicate_step"),
        ([_step("a", kind="poem")], "unknown_kind:a"),
        ([_step("a", -1)], "negative_level:a"),
        ([PlanStep.parse({"key": "a", "kind": "tool"})], "no_tool:a"),
        ([PlanStep.parse({"key": "a", "kind": "compute"})], "no_tool:a"),
        ([_step("a", writes=["report.release"], approver_user_id=HANNAH)], "reserved_action:a"),
        ([_step("a", writes=["file.copy"], approver_user_id=HANNAH)], "undeclared_write:a"),
        ([_step("a", writes=["file.save"])], "approver_lacks_action:a"),
        ([_step("a", reads_clients=["elsewhere"])], "read_out_of_scope:a"),
        ([_step("a", depends_on=["ghost"])], "unknown_dependency:a"),
        ([_step("a", 1), _step("b", 1, depends_on=["a"])], "level_order:b"),
        ([_step("a", 0), _step("b", 0, depends_on=["a"])], "level_order:b"),
    ],
)
def test_each_problem_code(steps: list[PlanStep], code: str) -> None:
    assert code in validate_plan(steps, _ctx())


def test_a_reserved_tool_action_is_refused_even_with_no_write() -> None:
    ctx = _ctx(tool_actions={"t.read": "acceptance.decide"})
    assert "reserved_action:a" in validate_plan([_step("a")], ctx)
    assert reserved("acceptance.decide")
    assert not reserved("engagement.read")


def test_an_approval_step_may_name_a_reserved_write_for_a_person() -> None:
    step = PlanStep.parse(
        {
            "key": "a",
            "kind": "approval",
            "writes": ["report.release"],
            "approver_user_id": HANNAH,
        }
    )
    ctx = _ctx(
        declared_writes=frozenset({"report.release"}),
        approver_holds={(HANNAH, "report.release"): True},
    )
    assert "reserved_action:a" not in validate_plan([step], ctx)


def test_an_approver_who_lacks_the_action_or_another_approver_is_refused() -> None:
    other = "00000000-0000-4000-8000-00000000a002"
    holds_false = _ctx(approver_holds={(HANNAH, "file.save"): False})
    step = _step("a", writes=["file.save"], approver_user_id=HANNAH)
    assert validate_plan([step], holds_false) == ["approver_lacks_action:a"]
    someone = _step("a", writes=["file.save"], approver_user_id=other)
    assert validate_plan([someone], _ctx()) == ["approver_lacks_action:a"]


def test_a_cycle_is_refused_and_codes_are_not_repeated() -> None:
    steps = [_step("a", 0, depends_on=["b"]), _step("b", 1, depends_on=["a"])]
    found = validate_plan(steps, _ctx())
    assert "cycle" in found
    assert len(found) == len(set(found))
    twice = _step("a", writes=["file.copy", "file.move"], approver_user_id=HANNAH)
    assert validate_plan([twice], _ctx()).count("undeclared_write:a") == 1


# --- the cap, readiness and failure ---------------------------------------------------------


@pytest.mark.parametrize(
    ("given", "cap_of"),
    [(None, MAX_PARALLEL), (0, MAX_PARALLEL), (-2, MAX_PARALLEL), (1, 1), (2, 2), (3, 3), (9, 3)],
)
def test_the_parallel_cap(given: int | None, cap_of: int) -> None:
    assert MAX_PARALLEL == 3
    assert cap(given) == cap_of


def test_ready_takes_the_lowest_levels_within_the_free_slots() -> None:
    steps = [_step("c", 2), _step("a", 1), _step("b", 1), _step("d", 1)]
    states = {"z": "running"}
    found = ready(steps, states, 3)
    assert [s.key for s in found] == ["a", "b"]
    assert ready(steps, {"z": "dispatched", "y": "running", "x": "running"}, 3) == []
    assert ready(steps, {}, 3, paused=True) == []
    assert [s.key for s in ready(steps, {}, 1)] == ["a"]


def test_ready_waits_for_every_dependency_to_succeed() -> None:
    steps = [_step("a", 0), _step("b", 0), _step("c", 1, depends_on=["a", "b"])]
    assert "c" not in [s.key for s in ready(steps, {"a": "succeeded", "b": "running"}, 3)]
    assert [s.key for s in ready(steps, {"a": "succeeded", "b": "succeeded"}, 3)] == ["c"]
    assert ready(steps, {"a": "succeeded", "b": "skipped"}, 3) == []


def test_a_failure_skips_only_its_dependants_transitively() -> None:
    steps = [
        _step("a", 0),
        _step("b", 1, depends_on=["a"]),
        _step("c", 2, depends_on=["b"]),
        _step("x", 0),
        _step("y", 1, depends_on=["x"]),
    ]
    for dead in ("failed", "cancelled", "skipped"):
        assert blocked_by_failure(steps, {"a": dead}) == {"b", "c"}
    assert blocked_by_failure(steps, {"a": "failed", "b": "running"}) == set()
    assert blocked_by_failure(steps, {"a": "succeeded"}) == set()


@pytest.mark.parametrize(
    ("states", "state"),
    [
        ([], "dispatched"),
        (["running", "blocked", "failed"], "running"),
        (["dispatched", "succeeded"], "running"),
        (["blocked", "waiting_on_inputs"], "blocked_on_decision"),
        (["waiting_on_inputs", "succeeded"], "needs_input"),
        (["queued", "succeeded"], "dispatched"),
        (["cancelled", "cancelled"], "cancelled"),
        (["cancelled", "failed"], "failed"),
        (["succeeded", "failed"], "failed"),
        (["succeeded", "skipped"], "succeeded"),
        (["succeeded", "cancelled"], "succeeded"),
    ],
)
def test_the_aggregate_state_in_its_order(states: list[str], state: str) -> None:
    assert aggregate(states) == state


def test_the_schedule_never_runs_more_than_its_limit_and_records_the_peak() -> None:
    schedule = Schedule([_step(k, 1) for k in "abcde"], limit=3)
    assert [s.key for s in schedule.start()] == ["a", "b", "c"]
    assert schedule.peak == 3
    assert schedule.start() == []
    schedule.finish("a", "succeeded")
    assert [s.key for s in schedule.start()] == ["d"]
    assert schedule.peak == 3
    assert not schedule.done and not schedule.stalled


def test_a_retry_requeues_the_failed_step_and_what_its_failure_skipped() -> None:
    steps = [_step("ic", 3), _step("t1", 4, depends_on=["ic"]), _step("x", 3)]
    schedule = Schedule(steps, limit=3)
    schedule.start()
    schedule.finish("ic", "failed")
    schedule.finish("x", "succeeded")
    schedule.start()
    assert schedule.states["t1"] == "skipped"
    assert schedule.retry("x") is False
    assert schedule.retry("ic") is True
    assert (schedule.states["ic"], schedule.states["t1"]) == ("queued", "queued")


def test_a_redirect_cancels_dropped_queued_steps_and_keeps_started_ones() -> None:
    schedule = Schedule([_step("a", 0), _step("b", 1), _step("c", 1)], limit=1)
    schedule.start()  # a runs
    cancelled = schedule.replace([_step("a", 0), _step("c", 1), _step("d", 2)])
    assert cancelled == ["b"]
    assert schedule.states == {"a": "running", "b": "cancelled", "c": "queued", "d": "queued"}
    assert schedule.stop() == ["c", "d"]
    assert schedule.waiting == []


# --- the SSE frame -------------------------------------------------------------------------------


def test_a_frame_names_its_seq_and_type_and_sorts_its_body() -> None:
    body = realtime.frame(realtime.StreamEvent(7, "notice", {"b": 1, "a": "x"}))
    assert body == b'id: 7\nevent: notice\ndata: {"a":"x","b":1}\n\n'
    assert realtime.comment("hb") == b":hb\n\n"


def test_a_frame_over_64_kb_goes_by_reference_and_one_at_the_limit_does_not() -> None:
    limit = realtime.MAX_EVENT_BYTES
    assert limit == 64 * 1024
    overhead = len(json.dumps({"id": "r", "x": ""}, separators=(",", ":")))
    at: dict[str, object] = {"id": "r", "x": "y" * (limit - overhead)}
    assert len(json.dumps(at, separators=(",", ":"))) == limit
    assert b"ref_only" not in realtime.frame(realtime.StreamEvent(1, "run", at))
    over: dict[str, object] = {"id": "r", "x": "y" * (limit - overhead + 1)}
    sent = realtime.frame(realtime.StreamEvent(2, "run", over))
    assert sent == b'id: 2\nevent: run\ndata: {"id":"r","ref_only":true,"seq":2,"type":"run"}\n\n'
    no_id = realtime.frame(realtime.StreamEvent(3, "run", {"x": "y" * limit}))
    assert b'"id"' not in no_id and b"ref_only" in no_id
