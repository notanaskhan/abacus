"""The run's plan rules, deterministic and free of I/O (P-10-T29; SPEC-647 §3.4 AC-W1, AC-W3,
AC-W8; DE-5; ADR-005). PROTECTED (agents). `run_workflow.py` calls these from inside the workflow,
so they must stay pure: no clock, no randomness, no database.

- **Validation before approval (AC-W1).** A plan is refused before `awaiting_plan_approval` when a
  step's action is reserved to a person (`HUMAN_ONLY_ACTIONS` or a final verb), a write is not
  declared by the run's spec, a write's approver does not hold its action, a read names a client
  outside the run's pinned `client_scope`, a step depends on an unknown step, or the steps form a
  cycle. The codes are identifiers; the dock words them.
- **Dispatch by level (AC-W3).** Steps run when every step they depend on has succeeded, lower
  levels first, at most `min(max_parallel_steps, 3)` at once. A failed step skips only the steps
  that depend on it; independent branches keep running.
- **The aggregate state** of a run from its steps' states, and the pause boundary (AC-W8): a pause
  stops new dispatches at the next step boundary; steps already running finish.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final, Literal, cast

from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS
from abacus.modules.agents.tools.registry import has_never_verb

MAX_PARALLEL: Final = 3
StepKind = Literal["tool", "compute", "model", "question", "decision", "approval", "narration"]
StepState = Literal[
    "queued", "dispatched", "running", "waiting_on_inputs", "blocked", "succeeded", "failed",
    "cancelled", "skipped",
]  # fmt: skip
TERMINAL_STEP: Final = frozenset({"succeeded", "failed", "cancelled", "skipped"})


@dataclass(frozen=True)
class PlanStep:
    """One step of a plan version (`agent_plans.steps[]`)."""

    key: str
    label: str
    level: int
    kind: StepKind
    tool: str | None = None
    arguments: Mapping[str, object] = field(default_factory=dict[str, object])
    depends_on: tuple[str, ...] = ()
    # A write the step would make, and who approves it (a person; never the agent).
    writes: tuple[str, ...] = ()
    approver_user_id: str | None = None
    # The clients a read names (resolved by the planner from its arguments).
    reads_clients: tuple[str, ...] = ()
    # W-02-T19 (WB-03a "Data it will read"): the sources a read step will reach and how many
    # records each holds, counted by the planner's code before approval (no bulk read).
    reads: tuple[tuple[str, int], ...] = ()

    @classmethod
    def parse(cls, raw: Mapping[str, object]) -> PlanStep:
        def strs(key: str) -> tuple[str, ...]:
            value = raw.get(key) or ()
            return tuple(str(v) for v in value) if isinstance(value, list | tuple) else ()  # pyright: ignore[reportUnknownVariableType,reportUnknownArgumentType] -- JSON list

        arguments = raw.get("arguments")
        return cls(
            key=str(raw["key"]),
            label=str(raw.get("label") or raw["key"]),
            level=int(str(raw.get("level", 0))),
            kind=str(raw.get("kind", "tool")),  # pyright: ignore[reportArgumentType] -- checked by validate_plan
            tool=str(raw["tool"]) if raw.get("tool") else None,
            arguments=dict(arguments) if isinstance(arguments, dict) else {},  # pyright: ignore[reportUnknownArgumentType] -- JSON object
            depends_on=strs("depends_on"),
            writes=strs("writes"),
            approver_user_id=str(raw["approver_user_id"]) if raw.get("approver_user_id") else None,
            reads_clients=strs("reads_clients"),
            reads=_reads(raw.get("reads")),
        )

    def dump(self) -> dict[str, object]:
        out: dict[str, object] = {
            "key": self.key,
            "label": self.label,
            "level": self.level,
            "kind": self.kind,
            "tool": self.tool,
            "arguments": dict(self.arguments),
            "depends_on": list(self.depends_on),
            "writes": list(self.writes),
            "approver_user_id": self.approver_user_id,
            "reads_clients": list(self.reads_clients),
        }
        if self.reads:
            out["reads"] = [{"source": s, "count": n} for s, n in self.reads]
        return out


def _reads(raw: object) -> tuple[tuple[str, int], ...]:
    """`[{source, count}]` as the planner wrote it; a malformed entry is kept as count -1 so
    validation refuses the plan rather than dropping what it would read."""
    if not isinstance(raw, list):
        return ()
    found: list[tuple[str, int]] = []
    for item in cast(list[object], raw):
        if not isinstance(item, dict):
            found.append(("", -1))
            continue
        entry = cast(dict[str, object], item)
        count = entry.get("count")
        found.append((str(entry.get("source") or ""), count if isinstance(count, int) else -1))
    return tuple(found)


# W-02-T19: the sources a plan may declare it reads, with the words WB-03a shows (code's, never
# the model's). A source outside this table refuses the plan (`unknown_read_source`).
READ_SOURCES: Final[Mapping[str, str]] = {
    "tax_returns": "Tax returns",
    "tax_engagements": "Tax engagements",
    "binders": "Binders",
    "offices": "Offices",
    "engagements": "Engagements",
    "requests": "Requests",
    "evidence": "Documents",
    "workpapers": "Workpapers",
}


KINDS: Final = frozenset(
    {"tool", "compute", "model", "question", "decision", "approval", "narration"}
)


@dataclass(frozen=True)
class PlanContext:
    """What validation needs to know about the run, read by an activity before it runs."""

    declared_writes: frozenset[str]  # the spec's propose and approved_write actions
    client_scope: frozenset[str]  # the run's pinned clients
    # Whether a person holds an action now (`identity.could`), answered per (user, action).
    approver_holds: Mapping[tuple[str, str], bool] = field(
        default_factory=dict[tuple[str, str], bool]
    )
    tool_actions: Mapping[str, str] = field(default_factory=dict[str, str])  # tool -> action


def reserved(action: str) -> bool:
    """An action no agent may take or plan (INV-1): human-only, or a final verb."""
    return action in HUMAN_ONLY_ACTIONS or has_never_verb(action)


def validate_plan(steps: Sequence[PlanStep], ctx: PlanContext) -> list[str]:
    """AC-W1: every problem code, in step order; empty means the plan may await approval."""
    found: list[str] = []
    keys = [s.key for s in steps]
    if not steps:
        return ["empty_plan"]
    if len(set(keys)) != len(keys):
        found.append("duplicate_step")
    known = set(keys)
    for s in steps:
        if s.kind not in KINDS:
            found.append(f"unknown_kind:{s.key}")
        if s.level < 0:
            found.append(f"negative_level:{s.key}")
        if s.kind in ("tool", "compute") and not s.tool:
            found.append(f"no_tool:{s.key}")
        action = ctx.tool_actions.get(s.tool or "", "")
        if action and reserved(action):
            found.append(f"reserved_action:{s.key}")
        for write in s.writes:
            if reserved(write) and s.kind != "approval":
                found.append(f"reserved_action:{s.key}")
            if write not in ctx.declared_writes:
                found.append(f"undeclared_write:{s.key}")
            if s.approver_user_id is None or not ctx.approver_holds.get(
                (s.approver_user_id, write), False
            ):
                found.append(f"approver_lacks_action:{s.key}")
        if any(c not in ctx.client_scope for c in s.reads_clients):
            found.append(f"read_out_of_scope:{s.key}")
        for source, count in s.reads:
            if source not in READ_SOURCES or count < 0:
                found.append(f"unknown_read_source:{s.key}")
        for dep in s.depends_on:
            if dep not in known:
                found.append(f"unknown_dependency:{s.key}")
            else:
                parent = next(p for p in steps if p.key == dep)
                if parent.level >= s.level:
                    found.append(f"level_order:{s.key}")
    if _cycle(steps):
        found.append("cycle")
    return list(dict.fromkeys(found))


def _cycle(steps: Sequence[PlanStep]) -> bool:
    graph = {s.key: set(s.depends_on) for s in steps}
    seen: set[str] = set()
    on_path: set[str] = set()

    def visit(key: str) -> bool:
        if key in on_path:
            return True
        if key in seen or key not in graph:
            return False
        on_path.add(key)
        hit = any(visit(d) for d in graph[key])
        on_path.discard(key)
        seen.add(key)
        return hit

    return any(visit(k) for k in graph)


def cap(max_parallel_steps: int | None) -> int:
    """At most 3 steps at once, fewer when the spec says so (CLS-02 A "3 running at once")."""
    if max_parallel_steps is None or max_parallel_steps < 1:
        return MAX_PARALLEL
    return min(max_parallel_steps, MAX_PARALLEL)


def _ancestors(steps: Sequence[PlanStep], key: str) -> set[str]:
    """Every step `key` depends on, directly or not."""
    by_key = {s.key: s for s in steps}
    found: set[str] = set()
    todo = list(by_key[key].depends_on) if key in by_key else []
    while todo:
        k = todo.pop()
        if k in found:
            continue
        found.add(k)
        todo.extend(by_key[k].depends_on if k in by_key else ())
    return found


def blocked_by_failure(steps: Sequence[PlanStep], states: Mapping[str, str]) -> set[str]:
    """Steps that can never run: they depend, directly or not, on a failed, cancelled or skipped
    step."""
    dead = {k for k, v in states.items() if v in ("failed", "cancelled", "skipped")}
    changed = True
    while changed:
        changed = False
        for s in steps:
            waiting = states.get(s.key, "queued") == "queued"
            if s.key not in dead and waiting and any(d in dead for d in s.depends_on):
                dead.add(s.key)
                changed = True
    return {k for k in dead if states.get(k, "queued") == "queued"}


def ready(
    steps: Sequence[PlanStep], states: Mapping[str, str], limit: int, *, paused: bool = False
) -> list[PlanStep]:
    """The queued steps to dispatch now (AC-W3, AC-W8): their dependencies succeeded, lowest
    level first, within the free slots. A pause dispatches nothing new."""
    if paused:
        return []
    running = sum(1 for v in states.values() if v in ("dispatched", "running"))
    free = max(0, limit - running)
    if free == 0:
        return []
    waiting = [
        s
        for s in steps
        if states.get(s.key, "queued") == "queued"
        and all(states.get(d) == "succeeded" for d in s.depends_on)
    ]
    waiting.sort(key=lambda s: (s.level, s.key))
    return waiting[:free]


RunState = Literal[
    "dispatched", "running", "needs_input", "blocked_on_decision", "waiting_on_inputs",
    "succeeded", "failed", "cancelled",
]  # fmt: skip


def aggregate(states: Iterable[str]) -> RunState:
    """The run's state from its steps' (the aggregate rule): running while any runs; blocked or
    waiting while one waits and none runs; failed when every step is terminal and one failed;
    succeeded when every step succeeded or was skipped for no failure."""
    found = list(states)
    if not found:
        return "dispatched"
    if any(s in ("dispatched", "running") for s in found):
        return "running"
    if any(s == "blocked" for s in found):
        return "blocked_on_decision"
    if any(s == "waiting_on_inputs" for s in found):
        return "needs_input"
    if any(s == "queued" for s in found):
        return "dispatched"
    if all(s == "cancelled" for s in found):
        return "cancelled"
    if any(s == "failed" for s in found):
        return "failed"
    return "succeeded"


@dataclass
class Schedule:
    """The dispatch loop's bookkeeping, replayable: the workflow holds one and asks it what to
    start next after every step outcome."""

    steps: Sequence[PlanStep]
    limit: int
    states: dict[str, str] = field(default_factory=dict[str, str])
    peak: int = 0  # the most steps that ran at once (AC-W3)

    def __post_init__(self) -> None:
        for s in self.steps:
            self.states.setdefault(s.key, "queued")

    def start(self, *, paused: bool = False) -> list[PlanStep]:
        for dead in blocked_by_failure(self.steps, self.states):
            self.states[dead] = "skipped"
        found = ready(self.steps, self.states, self.limit, paused=paused)
        for s in found:
            self.states[s.key] = "running"
        running = sum(1 for v in self.states.values() if v == "running")
        self.peak = max(self.peak, running)
        return found

    def finish(self, key: str, state: str) -> None:
        self.states[key] = state

    # --- part 2 (P-10-T32): waits, retries, redirects and stop ---------------------------------

    @property
    def waiting(self) -> list[str]:
        """Steps held on a person: a question (`waiting_on_inputs`) or a decision (`blocked`)."""
        return [k for k, v in self.states.items() if v in ("waiting_on_inputs", "blocked")]

    def retry(self, key: str) -> bool:
        """A person retried a failed step (AC-W6): it runs again as a new row, and the steps a
        failure had skipped below it are queued again. False when the step had not failed."""
        if self.states.get(key) != "failed":
            return False
        self.states[key] = "queued"
        changed = True
        while changed:
            changed = False
            for s in self.steps:
                if self.states.get(s.key) == "skipped" and key in _ancestors(self.steps, s.key):
                    self.states[s.key] = "queued"
                    changed = True
        return True

    def replace(self, steps: Sequence[PlanStep]) -> list[str]:
        """A redirect (AC-W10): a new plan version. Steps already started keep their state; a
        queued step the new version drops is cancelled; new steps are queued. Returns the keys
        cancelled."""
        keep = {s.key for s in steps}
        cancelled = [k for k, v in self.states.items() if v == "queued" and k not in keep]
        for k in cancelled:
            self.states[k] = "cancelled"
        started = {s.key: s for s in self.steps if self.states.get(s.key, "queued") != "queued"}
        merged = list(started.values()) + [s for s in steps if s.key not in started]
        self.steps = merged
        for s in merged:
            self.states.setdefault(s.key, "queued")
        return cancelled

    def stop(self) -> list[str]:
        """Stop (AC-W8's sibling): nothing new starts; queued and held steps are cancelled.
        Returns the keys cancelled; running steps finish or are cancelled by the workflow."""
        cancelled = [
            k for k, v in self.states.items() if v in ("queued", "waiting_on_inputs", "blocked")
        ]
        for k in cancelled:
            self.states[k] = "cancelled"
        return cancelled

    @property
    def done(self) -> bool:
        return all(v in TERMINAL_STEP for v in self.states.values())

    @property
    def stalled(self) -> bool:
        """Nothing runs and nothing can start: the rest wait on a person or a pause."""
        return not any(v == "running" for v in self.states.values()) and not ready(
            self.steps, self.states, self.limit
        )
