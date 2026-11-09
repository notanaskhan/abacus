"""The loop harness (P-10-T25; SPEC-647 §3.3; ADR-234 proposed; DEC-3115). PROTECTED (agents).

One step of a v2 run, as a loop of model turns and tool calls. The workflow runs each turn and
each tool call as its own activity (`HarnessPorts`): this module holds only the loop's rules, so
it is deterministic given its ports and unit-testable without a model.

- **Hard limits** (the spec's `LimitsV2`): turns (`max_steps`), tool calls (`max_tool_calls`),
  cost (`max_cost_usd`), wall time (`max_seconds`) and identical repeats
  (`max_repeat_identical_calls`: the same tool with the same arguments). The first limit reached
  stops the step `failed` with that code (`max_repeat`, …), an actionable SHL-13 state 6 error.
- **Questions and plans are output fields**: the final turn's schema carries `question` or
  `plan`; the harness hands them back (`needs_input`, `plan_proposed`) and never acts on them.
- **Repair, then escalation, then needs_input**: `converse()` repairs one bad turn itself
  (ADR-234); an escalated turn stops the step `needs_input` with the failure code.
- **Provenance before emission (INV-2, DE-3)**: every block the step emits is validated against
  the run's facts and verified citations (`agents.blocks.validate_blocks`). A part that cites an
  unverified source or states a free number is replaced by "Unsupported" and recorded with its
  reason; it is never emitted as fact.
- **`active_ms`** sums the time spent in turns and tool calls only. Waits (a question, admission,
  a decision) happen outside the step or are reported by the port, and are excluded.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Awaitable, Callable, Mapping, Set
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final, Literal, Protocol, cast
from uuid import UUID

from abacus.modules.agents.blocks import BlocksRejected, Fact, validate_blocks

HarnessStatus = Literal["completed", "failed", "needs_input", "plan_proposed"]
LimitCode = Literal["max_steps", "max_tool_calls", "max_cost", "max_wall_time", "max_repeat"]
UNSUPPORTED: Final = "Unsupported"


@dataclass(frozen=True)
class Limits:
    max_steps: int
    max_seconds: int
    max_cost_usd: Decimal
    max_tool_calls: int | None = None
    max_repeat_identical_calls: int | None = None


@dataclass(frozen=True)
class ToolRequest:
    tool_use_id: str
    name: str
    arguments: Mapping[str, object]


@dataclass(frozen=True)
class TurnResult:
    """One `converse()` turn as the harness reads it."""

    status: Literal["ok", "tool_calls", "escalated"]
    cost_usd: Decimal
    tool_calls: tuple[ToolRequest, ...] = ()
    output: Mapping[str, object] | None = None  # the structured final turn
    failure: str | None = None
    waited_ms: int = 0  # admission and similar waits the port measured; excluded


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    code: str | None = None
    records_read: int = 0
    payload: Mapping[str, object] | None = None
    waited_ms: int = 0


class HarnessPorts(Protocol):
    async def turn(self, history: tuple[Mapping[str, object], ...]) -> TurnResult: ...

    async def tool(self, request: ToolRequest) -> ToolResult: ...


@dataclass(frozen=True)
class UnsupportedPart:
    index: int
    reason: str  # a BlocksRejected code: free_number, unknown_citation, …


@dataclass(frozen=True)
class HarnessOutcome:
    status: HarnessStatus
    turns: int
    tool_calls: int
    cost_usd: Decimal
    active_ms: int
    failure: str | None = None
    blocks: Mapping[str, object] | None = None
    unsupported: tuple[UnsupportedPart, ...] = ()
    question: Mapping[str, object] | None = None
    plan: Mapping[str, object] | None = None
    records_read: int = 0
    tool_log: tuple[str, ...] = field(default_factory=tuple)


def call_key(name: str, arguments: Mapping[str, object]) -> str:
    """Identical calls: the same tool and the same canonical arguments."""
    body = json.dumps({"name": name, "arguments": arguments}, sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()


def settle_blocks(
    payload: Mapping[str, object], facts: Mapping[str, Fact], citations: Set[UUID]
) -> tuple[dict[str, object], tuple[UnsupportedPart, ...]]:
    """Validate each part on its own; a part that fails is replaced by "Unsupported" and its
    reason recorded. Shape errors of the whole payload stay errors (the turn is repaired)."""
    raw = payload.get("parts")
    if not isinstance(raw, list):
        raise BlocksRejected("shape", "parts")
    parts = cast(list[object], raw)
    kept: list[object] = []
    unsupported: list[UnsupportedPart] = []
    for index, part in enumerate(parts):
        try:
            validate_blocks({"version": 1, "parts": [part]}, facts, citations)
        except BlocksRejected as rejected:
            if rejected.code == "shape":
                raise
            unsupported.append(UnsupportedPart(index, rejected.code))
            kept.append({"kind": "p", "segments": [{"kind": "text", "text": UNSUPPORTED}]})
            continue
        kept.append(part)
    return {"version": 1, "parts": kept}, tuple(unsupported)


Clock = Callable[[], float]


async def run_step(
    ports: HarnessPorts,
    limits: Limits,
    *,
    facts: Mapping[str, Fact],
    citations: Set[UUID],
    first_turn: Mapping[str, object],
    clock: Clock = time.monotonic,
    verified: Callable[[], Awaitable[Set[UUID]]] | None = None,
) -> HarnessOutcome:
    """Run one step's loop to its end (module docstring). `verified`, when given, answers the
    citations verified so far (tool reads add to them) before blocks are settled."""
    history: list[Mapping[str, object]] = [first_turn]
    started = clock()
    active = 0.0
    turns = calls = records = 0
    cost = Decimal("0")
    seen: dict[str, int] = {}
    log: list[str] = []

    def outcome(status: HarnessStatus, **extra: object) -> HarnessOutcome:
        return HarnessOutcome(
            status=status,
            turns=turns,
            tool_calls=calls,
            cost_usd=cost,
            active_ms=int(active * 1000),
            records_read=records,
            tool_log=tuple(log),
            **extra,  # type: ignore[arg-type]  # the remaining HarnessOutcome fields
        )

    while True:
        if turns >= limits.max_steps:
            return outcome("failed", failure="max_steps")
        if clock() - started > limits.max_seconds:
            return outcome("failed", failure="max_wall_time")
        t0 = clock()
        result = await ports.turn(tuple(history))
        active += max(0.0, clock() - t0 - result.waited_ms / 1000)
        turns += 1
        cost += result.cost_usd
        if cost > limits.max_cost_usd:
            return outcome("failed", failure="max_cost")
        if result.status == "escalated":
            return outcome("needs_input", failure=result.failure or "escalated")
        if result.status == "tool_calls":
            for request in result.tool_calls:
                key = call_key(request.name, request.arguments)
                seen[key] = seen.get(key, 0) + 1
                repeat = limits.max_repeat_identical_calls
                if repeat is not None and seen[key] >= repeat:
                    return outcome("failed", failure="max_repeat")
                if limits.max_tool_calls is not None and calls >= limits.max_tool_calls:
                    return outcome("failed", failure="max_tool_calls")
                t1 = clock()
                answered = await ports.tool(request)
                active += max(0.0, clock() - t1 - answered.waited_ms / 1000)
                calls += 1
                records += answered.records_read
                log.append(request.name if answered.ok else f"{request.name}:{answered.code}")
                history.append(
                    {
                        "tool_use_id": request.tool_use_id,
                        "name": answered.name,
                        "ok": answered.ok,
                        "code": answered.code,
                        "payload": dict(answered.payload or {}),
                    }
                )
            continue
        output = dict(result.output or {})
        if output.get("question"):
            return outcome("needs_input", question=dict(output["question"]))  # type: ignore[call-overload, arg-type]  # a JSON object
        if output.get("plan"):
            return outcome("plan_proposed", plan=dict(output["plan"]))  # type: ignore[call-overload, arg-type]  # a JSON object
        payload = output.get("blocks")
        if not isinstance(payload, dict):
            return outcome("completed")
        known: set[UUID] = set(citations)
        if verified is not None:
            known |= set(await verified())
        settled, unsupported = settle_blocks(payload, facts, known)  # type: ignore[arg-type]  # a JSON object
        return outcome("completed", blocks=settled, unsupported=unsupported)
