"""Code-only runs on the v1 recording path (A-07-T32; A-07 §6; DEC-3109). PROTECTED (agents).

A capability with no model call (ADR-050: code computes) is still recorded as an agent run, so
the P-09 dock shows it as "<initiator> via Agent" (INV-5): a v1 deterministic run, one step row
per ToolCard (state `succeeded`, its records read and an identifier-only summary), a `narration`
step whose summary is AgentBlocks rendered from a template (every figure a fact reference, every
citation verified; `validate_blocks` refuses anything else), then the run closed with its
identifier-only output. The gateway records no model call for it. A plan never carries a
reserved action: every step's tool is declared by the capability, and none is a final verb.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork
from abacus.modules.agents.blocks import Fact, validate_blocks
from abacus.modules.agents.det_runs import close_deterministic_run, open_deterministic_run


# Final verbs a code run's plan may never name (ADR-005; I-AGENT-NEVER).
def _reserved() -> frozenset[str]:
    """The verbs, named only to refuse them (REVIEW-001's exemption is this one function)."""
    return frozenset(
        {"approve", "sign_off", "release", "send", "post", "decide", "concur", "lock", "conclude"}
    )


RESERVED: Final = _reserved()


class ReservedAction(ValueError):
    """A code run's plan named a final verb."""


@dataclass(frozen=True)
class CodeStep:
    """One ToolCard: `tool_name` is `<area>.<verb>` and never a reserved verb."""

    tool_name: str
    label: str
    records_read: int = 0
    summary: Mapping[str, object] = field(default_factory=dict[str, object])


@dataclass(frozen=True)
class CodeRun:
    agent_id: str
    engagement_id: UUID
    initiator_user_id: UUID
    task_scope: tuple[str, ...]
    steps: Sequence[CodeStep]
    narration: Mapping[str, object]  # AgentBlocks v1 payload
    facts: Mapping[str, Fact] = field(default_factory=dict[str, Fact])
    citations: Set[UUID] = frozenset()
    output: Mapping[str, object] = field(default_factory=dict[str, object])
    work_item_id: UUID | None = None


def check_plan(run: CodeRun) -> None:
    for step in run.steps:
        verb = step.tool_name.rsplit(".", 1)[-1]
        if verb in RESERVED or any(verb.startswith(f"{r}_") for r in RESERVED):
            raise ReservedAction(step.tool_name)


_STEP = text(
    "INSERT INTO agent_run_steps (tenant_id, run_id, seq, plan_step_key, level, kind, tool_name, "
    "state, started_at, ended_at, records_read, outputs_summary) VALUES (:tenant, :run, :seq, "
    ":key, 0, :kind, :tool, 'succeeded', clock_timestamp(), clock_timestamp(), :records, "
    "CAST(:summary AS jsonb))"
)


async def record_code_run(tx: UnitOfWork, tenant_id: UUID, run: CodeRun) -> UUID:
    """Record `run` in the caller's unit of work and answer its id. Raises `ReservedAction` or
    `BlocksRejected` before anything is written."""
    check_plan(run)
    validate_blocks(run.narration, run.facts, run.citations)
    run_id = await begin_code_run(
        tx, tenant_id, run.agent_id, run.engagement_id, run.initiator_user_id, run.task_scope
    )
    await finish_code_run(tx, tenant_id, run_id, run)
    return run_id


async def begin_code_run(
    tx: UnitOfWork,
    tenant_id: UUID,
    agent_id: str,
    engagement_id: UUID,
    initiator_user_id: UUID,
    task_scope: tuple[str, ...],
) -> UUID:
    """Open the run first when what it drafts must name it (a letter's `drafted_by_run_id`; S33
    partials round). `finish_code_run` writes its steps and narration and ends it."""
    return await open_deterministic_run(
        tx,
        tenant_id=tenant_id,
        agent_id=agent_id,
        engagement_id=engagement_id,
        initiator=initiator_user_id,
        task_scope=task_scope,
    )


async def fail_code_run(tx: UnitOfWork, run_id: UUID, code: str) -> None:
    """A run whose work was refused ends failed with the refusal's code (nothing else written)."""
    await close_deterministic_run(tx, run_id, failure_code=code[:60])


async def finish_code_run(tx: UnitOfWork, tenant_id: UUID, run_id: UUID, run: CodeRun) -> None:
    """Steps, the narration and the end of a run `begin_code_run` opened."""
    check_plan(run)
    validate_blocks(run.narration, run.facts, run.citations)
    seq = 0
    for step in run.steps:
        seq += 1
        await tx.session.execute(
            _STEP,
            {
                "tenant": tenant_id,
                "run": run_id,
                "seq": seq,
                "key": step.tool_name,
                "kind": "tool",
                "tool": step.tool_name,
                "records": step.records_read,
                "summary": json.dumps({"label": step.label, **dict(step.summary)}),
            },
        )
    await tx.session.execute(
        _STEP,
        {
            "tenant": tenant_id,
            "run": run_id,
            "seq": seq + 1,
            "key": "narration",
            "kind": "narration",
            "tool": None,
            "records": 0,
            "summary": json.dumps(
                {
                    "blocks": dict(run.narration),
                    "facts": [f.model_dump() for f in run.facts.values()],
                }
            ),
        },
    )
    await close_deterministic_run(tx, run_id, output=dict(run.output))
    tx.record(
        "agent_run.code_recorded",
        target=Target("agent_run", run_id),
        after=Ref(steps=len(run.steps), model_calls=0),
        scope=Scope(engagement_id=run.engagement_id, work_item_id=run.work_item_id),
    )


def text_part(*segments: Mapping[str, object]) -> dict[str, object]:
    """An AgentBlocks paragraph from text and fact segments (a template, never a model)."""
    return {"kind": "p", "segments": list(segments)}


def txt(value: str) -> dict[str, object]:
    return {"kind": "text", "text": value}


def fact(fact_id: str) -> dict[str, object]:
    return {"kind": "fact", "fact_id": fact_id}


def blocks(*parts: Mapping[str, object]) -> dict[str, object]:
    return {"version": 1, "parts": list(parts)}
