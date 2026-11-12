"""The engagement run, `engagements.run` (P-10-T39; SPEC-647 §3.6 AC-E1 to AC-E4; ADR-005,
ADR-186; DEC-50, DEC-3404). PROTECTED (agents).

A deterministic workflow-shape run: code computes its plan, no model plans it, and every output
still waits for a person.

- **Code plan.** From the engagement's pinned methodology version: each program step with a level
  becomes one plan step on the run's five levels (Foundation 1 · Planning 2 · Sampling 3 ·
  Testing 4 · Completion 5), keeping its `depends_on` keys where they point to a lower level. A
  materiality step is a C3 decision card reserved to the engagement partner (AUD-02d: Planning
  holds on it). With no levelled program steps the plan falls back to the static EBP section list
  (chapter 05 §5.7.5; AC-E2): 14 = 1 + 5 + 1 + 4 + 3 (SHL-13 state 1).
- **Run steps.** A plan step names the run-step kind that executes it (`run_step.<kind>`);
  owning modules register handlers through `register_run_step` (ADR-106 slot, fail closed). A
  plan naming a kind with no handler is refused at start with 409 `run_step_unavailable` naming
  the kind, before any row is written. The built-in `workpaper` handler checks that the step's
  bound workpaper exists on the engagement (a readiness step); preparing it is its owner's
  handler's (A-04, A-05 and K-04 register theirs).
- **Start.** `POST /v1/engagements/{id}/runs`: a live person with `agent_run.start` (Senior and up
  on the team; a wall answers 404, AC-E4) writes the run's row (`engagements.run`, trigger
  `engagement_plan`, the plan in its inputs) and dispatches `AgentRunWorkflow`.
- **Auto mode.** `PUT /v1/engagements/{id}/auto-mode` (`engagement_ai.configure`, Manager and up;
  `{enabled, confirmed: true}`). The effective autonomy is forced off for a real firm until the
  capability is live (season 1, DEC-50): enabling it there is refused with 409
  `auto_mode_not_available`. On a synthetic firm the run is marked `mode: auto`; its outputs still
  wait for a person (AC-E3). Skipping `awaiting_plan_approval` needs ADR-186's standing approval
  record (a person's, bound to a schedule: W-03/K-04), so until then the plan still waits.
"""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.run_plan import PlanStep
from abacus.modules.agents.run_waits import run_workflow_id
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    authorise,
    is_synthetic_firm,
)
from abacus.modules.methodology.api import version_steps

AGENT_ID: Final = "engagements.run"
SPEC_VERSION: Final = 1
START: Final = "agent_run.start"
CONFIGURE: Final = "engagement_ai.configure"
TASK_SCOPE: Final = ("engagement.read", "workpaper.read", "evidence.read", "decision_card.raise")
# AUD-02d: Planning materiality is assurance's C3 kind, reserved to the engagement partner.
MATERIALITY_KIND: Final = "planning_materiality"
MAX_PARALLEL: Final = 3  # CLS-02 A "3 running at once"
LEVELS: Final = {"foundation": 1, "planning": 2, "sampling": 3, "testing": 4, "completion": 5}
LEVEL_NAMES: Final = ("Foundation", "Planning", "Sampling", "Testing", "Completion")
RUN_STEP_PREFIX: Final = "run_step."
_MATERIALITY: Final = re.compile(r"materiality", re.IGNORECASE)
_SAMPLING: Final = re.compile(r"sampl", re.IGNORECASE)

# The static EBP section list (chapter 05 §5.7.5; SHL-13 state 1, AUD-02b "Ready to run 14
# workpapers across 5 levels"): (key, level, label, run-step kind or a C3 decision).
STATIC_EBP_SECTIONS: Final[tuple[tuple[str, int, str, str], ...]] = (
    ("workpapers.trial_balance", 1, "Run trial balance workpaper", "workpaper"),
    ("workpapers.materiality", 2, "Propose materiality", "decision"),
    ("workpapers.risk_assessment", 2, "Draft risk assessment", "workpaper"),
    ("workpapers.audit_planning", 2, "General audit planning", "workpaper"),
    ("workpapers.internal_control", 2, "Internal control", "workpaper"),
    ("planning_5", 2, "Planning", "workpaper"),
    ("sampling_1", 3, "Sampling", "workpaper"),
    ("testing_1", 4, "Testing", "workpaper"),
    ("testing_2", 4, "Testing", "workpaper"),
    ("testing_3", 4, "Testing", "workpaper"),
    ("testing_4", 4, "Testing", "workpaper"),
    ("completion_1", 5, "Completion", "workpaper"),
    ("completion_2", 5, "Completion", "workpaper"),
    ("completion_3", 5, "Completion", "workpaper"),
)


class RunStepUnavailable(DomainConflict):
    """A plan step names a run-step kind nobody registered (AC-E2): 409, the kind named."""

    code = "run_step_unavailable"


class AutoModeNotAvailable(DomainConflict):
    """Auto mode is forced off for a real firm until the capability is live (DEC-50)."""

    code = "auto_mode_not_available"


# --- the run-step slot (ADR-106) -----------------------------------------------------------------


@dataclass(frozen=True)
class RunStepFacts:
    """What a handler is told: the step and the run's engagement (identifiers and codes)."""

    run_id: UUID
    engagement_id: UUID
    step_key: str
    level: int
    arguments: dict[str, object]


@dataclass(frozen=True)
class RunStepResult:
    state: str  # succeeded · failed
    error_code: str | None = None
    records_read: int = 0


RunStepHandler = Callable[[AgentContext, RunStepFacts], Awaitable[RunStepResult]]
_HANDLERS: dict[str, RunStepHandler] = {}
_KIND: Final = re.compile(r"[a-z][a-z_]{0,39}")


def register_run_step(kind: str, handler: RunStepHandler) -> None:
    if not _KIND.fullmatch(kind):
        raise ValueError(f"run step kind {kind!r} must be snake_case")
    known = _HANDLERS.get(kind)
    if known is not None and known is not handler:
        raise ValueError(f"run step {kind!r} is already registered")
    _HANDLERS[kind] = handler


def run_step_handler(tool: str | None) -> RunStepHandler | None:
    """The handler a plan step's `tool` names (`run_step.<kind>`), or None for a C17 tool."""
    if tool is None or not tool.startswith(RUN_STEP_PREFIX):
        return None
    return _HANDLERS.get(tool.removeprefix(RUN_STEP_PREFIX))


def is_run_step(tool: str | None) -> bool:
    return tool is not None and tool.startswith(RUN_STEP_PREFIX)


# The `workpaper` step's handler is the workpapers module's (`workpapers/run_steps.py`; ADR-008:
# agents never reads another module's tables or imports it).


# --- the code plan (AC-E1, AC-E2) ----------------------------------------------------------------


def _step(key: str, level: int, label: str, kind: str, **extra: object) -> PlanStep:
    if kind == "decision":
        return PlanStep(
            key=key,
            label=label,
            level=level,
            kind="decision",
            arguments={"decision_kind": MATERIALITY_KIND, "question_key": "materiality"},
        )
    return PlanStep(
        key=key,
        label=label,
        level=level,
        kind="compute",
        tool=f"{RUN_STEP_PREFIX}{kind}",
        arguments=dict(extra),
    )


def static_plan() -> list[PlanStep]:
    """The static EBP section list (14 = 1 + 5 + 1 + 4 + 3)."""
    return [_step(k, lv, label, kind) for k, lv, label, kind in STATIC_EBP_SECTIONS]


def plan_from_steps(
    steps: Sequence[tuple[str, str, str, tuple[str, ...], tuple[str, ...]]],
) -> list[PlanStep]:
    """A code plan from methodology steps `(key, level, text, depends_on, template_refs)`: a step
    without a run level is left out; a dependency on the same or a later level is dropped (the
    scheduler orders levels)."""
    levelled: list[tuple[str, int, str, tuple[str, ...], tuple[str, ...]]] = []
    for key, level, body, deps, refs in steps:
        run_level = LEVELS.get(level)
        if run_level is None:
            continue
        if run_level == LEVELS["testing"] and _SAMPLING.search(key + " " + body):
            run_level = LEVELS["sampling"]
        levelled.append((key, run_level, body, deps, refs))
    level_of = {key: lv for key, lv, *_ in levelled}
    plan: list[PlanStep] = []
    for key, lv, body, deps, refs in levelled:
        label = (body.splitlines()[0] if body else key)[:200] or key
        kind = (
            "decision"
            if lv == LEVELS["planning"] and _MATERIALITY.search(key + body)
            else "workpaper"
        )
        step = _step(key, lv, label, kind, **({"workpaper_code": refs[0]} if refs else {}))
        kept = tuple(d for d in deps if d in level_of and level_of[d] < lv)
        plan.append(
            PlanStep(
                key=step.key,
                label=step.label,
                level=step.level,
                kind=step.kind,
                tool=step.tool,
                arguments=step.arguments,
                depends_on=kept,
            )
        )
    return plan


async def code_plan(tenant: TenantContext, methodology_version_id: UUID | None) -> list[PlanStep]:
    """The engagement's plan: its pinned version's levelled steps, else the static list."""
    if methodology_version_id is not None:
        version = await version_steps(tenant, methodology_version_id)
        plan = plan_from_steps(
            [(s.step_key, s.level, s.text, s.depends_on, s.template_refs) for s in version.steps]
        )
        if plan:
            return plan
    return static_plan()


# --- the plan-provider slot (T-05-T31; DEC-4616) ---------------------------------------------
#
# A work item's owner may supply the run's code plan instead of the methodology: `tax` registers
# `tax.entity_workbook` (the entity return's ten steps). A provider is code, deterministic, and its
# steps still name registered run-step kinds (or decision and question steps); the start refuses a
# plan naming a kind with no handler exactly as for the methodology plan.


@dataclass(frozen=True)
class PlanRequest:
    """What the start asks a provider for: the whole plan, some groups, or some steps (each with
    its dependants), for one work item."""

    work_item_id: UUID
    scope: str  # all · group · task
    keys: tuple[str, ...] = ()


PlanProvider = Callable[[TenantContext, UUID, PlanRequest], Awaitable[list[PlanStep]]]
_PROVIDERS: dict[str, PlanProvider] = {}
_PROVIDER_KEY: Final = re.compile(r"[a-z][a-z_]{0,30}\.[a-z][a-z_]{0,40}")


def register_plan_provider(key: str, provider: PlanProvider) -> None:
    if not _PROVIDER_KEY.fullmatch(key):
        raise ValueError(f"plan provider {key!r} must be <module>.<name>")
    known = _PROVIDERS.get(key)
    if known is not None and known is not provider:
        raise ValueError(f"plan provider {key!r} is already registered")
    _PROVIDERS[key] = provider


def plan_provider(key: str) -> PlanProvider | None:
    return _PROVIDERS.get(key)


class PlanProviderUnavailable(DomainConflict):
    """No provider is registered under the key the start named (fail closed)."""

    code = "plan_provider_unavailable"


def projection(plan: Sequence[PlanStep]) -> list[int]:
    """Steps per run level, Foundation to Completion (AC-E1: [1, 5, 1, 4, 3])."""
    return [sum(1 for s in plan if s.level == n) for n in range(1, len(LEVEL_NAMES) + 1)]


def missing_handlers(plan: Sequence[PlanStep]) -> list[str]:
    return sorted(
        {
            (s.tool or "").removeprefix(RUN_STEP_PREFIX)
            for s in plan
            if is_run_step(s.tool) and run_step_handler(s.tool) is None
        }
    )


# --- auto mode (AC-E3) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AutoMode:
    enabled: bool
    changed_by: UUID | None
    changed_at: datetime | None


_SETTINGS: Final = text(
    "SELECT auto_mode, auto_mode_set_by, auto_mode_set_at FROM engagement_ai_settings "
    "WHERE engagement_id = :e"
)


async def effective_auto_mode(tenant: TenantContext, engagement_id: UUID) -> AutoMode:
    """The engagement's Auto mode as it applies now: off for a real firm whatever is stored."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_SETTINGS, {"e": engagement_id})).first()
    if row is None:
        return AutoMode(False, None, None)
    stored = AutoMode(bool(row.auto_mode), row.auto_mode_set_by, row.auto_mode_set_at)
    if stored.enabled and not await is_synthetic_firm(tenant):
        return AutoMode(False, stored.changed_by, stored.changed_at)
    return stored


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def set_auto_mode(ctx: AuthContext, engagement_id: UUID, enabled: bool) -> AutoMode:
    _person(ctx, CONFIGURE)
    ref = await get_ref(ctx, engagement_id)  # a wall answers 404
    await authorise(ctx, CONFIGURE, ref.resource())
    if enabled and not await is_synthetic_firm(ctx.tenant):
        raise AutoModeNotAvailable(facts={"reason": "real_firm"})
    now = await clock.now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO engagement_ai_settings (tenant_id, engagement_id, auto_mode, "
                "auto_mode_set_by, auto_mode_set_at) VALUES (:t, :e, :on, :by, :at) "
                "ON CONFLICT (tenant_id, engagement_id) DO UPDATE SET auto_mode = EXCLUDED."
                "auto_mode, auto_mode_set_by = EXCLUDED.auto_mode_set_by, auto_mode_set_at = "
                "EXCLUDED.auto_mode_set_at"
            ),
            {"t": ctx.tenant_id, "e": engagement_id, "on": enabled, "by": ctx.user_id, "at": now},
        )
        tx.record(
            "engagement_ai.auto_mode_set",
            target=Target("engagement", engagement_id),
            after=Ref(enabled=int(enabled)),
            scope=Scope(engagement_id=engagement_id),
        )
    return AutoMode(enabled, ctx.user_id, now)


# --- start (AC-E4) -------------------------------------------------------------------------------

_SEED: Final = text(
    "INSERT INTO tenant_counters (tenant_id, name, value) SELECT CAST(:t AS uuid), 'agent_run', "
    "COALESCE(max(run_number), 0) FROM agent_runs ON CONFLICT (tenant_id, name) DO NOTHING"
)
_NEXT: Final = text(
    "UPDATE tenant_counters SET value = value + 1 WHERE name = 'agent_run' RETURNING value"
)
_RUN: Final = text(
    "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
    "initiator_user_id, task_scope, state, mode, trigger_kind, run_number, runs_as_user_id, "
    "inputs, work_item_ref, client_scope, auto_mode) VALUES (:t, :agent, :version, :eng, :by, "
    ":scope, 'queued', :mode, 'engagement_plan', :number, :by, CAST(:inputs AS jsonb), "
    ":work_item, ARRAY[CAST(:client AS uuid)], :auto) RETURNING id"
)


@dataclass(frozen=True)
class StartedRun:
    run_id: UUID
    run_number: int
    levels: list[int]


async def start_engagement_run(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    work_item_ref: str | None = None,
    provider: str | None = None,
    request: PlanRequest | None = None,
) -> StartedRun:
    """The engagement run for a person (module docstring); the workflow is dispatched here. With
    `provider` (T-05-T31) the plan is the registered provider's for `request`, not the
    methodology's."""
    from abacus.modules.agents.run_workflow import AgentRunInput, AgentRunWorkflow

    _person(ctx, START)
    ref = await get_ref(ctx, engagement_id)  # a wall answers 404
    await authorise(ctx, START, ref.resource())
    if provider is not None:
        supplier = plan_provider(provider)
        if supplier is None or request is None:
            raise PlanProviderUnavailable(facts={"provider": provider})
        plan = await supplier(ctx.tenant, engagement_id, request)
    else:
        plan = await code_plan(ctx.tenant, ref.methodology_version_id)
    missing = missing_handlers(plan)
    if missing:
        raise RunStepUnavailable(facts={"kind": missing[0]})
    auto = await effective_auto_mode(ctx.tenant, engagement_id)
    inputs: dict[str, object] = {
        "plan": [s.dump() for s in plan],
        "max_parallel_steps": MAX_PARALLEL,
    }
    if provider is not None and request is not None:
        inputs |= {
            "plan_provider": provider,
            "scope": request.scope,
            "keys": list(request.keys),
            "work_item_id": str(request.work_item_id),
        }
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_SEED, {"t": ctx.tenant_id})
        number = cast(int, await tx.session.scalar(_NEXT))
        run_id = cast(
            UUID,
            await tx.session.scalar(
                _RUN,
                {
                    "t": ctx.tenant_id,
                    "agent": AGENT_ID,
                    "version": SPEC_VERSION,
                    "eng": engagement_id,
                    "by": ctx.user_id,
                    "scope": list(TASK_SCOPE),
                    "mode": "auto" if auto.enabled else "run",
                    "number": number,
                    "inputs": json.dumps(inputs, sort_keys=True, default=str),
                    "work_item": work_item_ref,
                    "client": str(ref.client_id),
                    "auto": auto.enabled,
                },
            ),
        )
        tx.record(
            "agent_run.started",
            target=Target("agent_run", run_id),
            after=Ref(initiator=ctx.user_id, run_number=number),
            scope=Scope(engagement_id=engagement_id),
        )
    await dispatch(
        AgentRunWorkflow,
        AgentRunInput(str(ctx.tenant_id), str(run_id)),
        id=run_workflow_id(str(ctx.tenant_id), str(run_id)),
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return StartedRun(run_id, number, projection(plan))


async def engagement_of_run(tenant: TenantContext, run_id: UUID) -> UUID:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT engagement_id FROM agent_runs WHERE id = :r"), {"r": run_id}
        )
    if found is None:
        raise NotFound("agent_run")
    return cast(UUID, found)


# --- a work item's engagement runs (T-05-T31: TXP-00's Run history and the in-progress guard) ----

_TERMINAL: Final = frozenset({"succeeded", "approved", "partially_approved", "rejected", "failed"})
_TERMINAL_ALL: Final = _TERMINAL | {"cancelled"}


@dataclass(frozen=True)
class WorkItemRun:
    run_id: UUID
    run_number: int
    initiator_user_id: UUID | None
    created_at: datetime
    state: str

    @property
    def active(self) -> bool:
        return self.state not in _TERMINAL_ALL


_WORK_ITEM_RUNS: Final = text(
    "SELECT id, run_number, initiator_user_id, created_at, state FROM agent_runs "
    "WHERE agent_id = :agent AND work_item_ref = :ref ORDER BY created_at DESC LIMIT :limit"
)


async def work_item_runs(
    tenant: TenantContext, work_item_ref: str, limit: int = 50
) -> list[WorkItemRun]:
    """The engagement runs started for one work item (`tax_return:<id>`), newest first."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _WORK_ITEM_RUNS, {"agent": AGENT_ID, "ref": work_item_ref, "limit": limit}
        )
        return [
            WorkItemRun(
                UUID(str(r.id)),
                int(r.run_number),
                None if r.initiator_user_id is None else UUID(str(r.initiator_user_id)),
                r.created_at,
                str(r.state),
            )
            for r in rows
        ]
