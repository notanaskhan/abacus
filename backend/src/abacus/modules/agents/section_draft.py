"""The section drafter (A-04-T11; A-04 §3.1 AC1.1, §6 AC6.1; SPEC-620; DEC-1868). PROTECTED.

One capability, `workpapers.section_drafter`, for every workpaper section mode (gap,
risk_narrative, risk, ic, soc1; A-05 and A-08 add theirs as spec versions, OQ-1). A person with
`workpaper.draft` starts one run per paper section (`start`); `SectionDraftWorkflow` holds a work
slot and runs `draft`, whose steps are, in order:

1. **load_context** (code): the run row proves the engagement and the initiator; the paper must be
   that engagement's and readable by the agent (`workpaper.read` through the task scope). The
   layers are code-built: the bound methodology steps of the pinned version (`S<n>`), the paper's
   own typed figures as facts (`F<n>`, the prior version), and the section's cells, delimited as
   untrusted (ADR-051, ADR-052). Modes add their documents and facts with their mappings (T22-T35).
2. **validate_pack** (code, before any model call): the bound steps' template references resolve
   (workpapers' `pack_problem`, through the source slot); otherwise the run fails
   `pack_configuration_error` with AUD-09 d's sentence recorded, and nothing is written (AC6.1).
3. **call_model**: one gateway call with the mode's registered prompt, tier, budget and the
   `SectionDraft` schema.
4. **verify_citations**: every citation is written as a v2 row through C4's verifiers, as the
   agent, anchored on the run (`section_draft:<run>`, ref the cell); nothing the model says it
   cites is trusted.
5. **check_numbers** (number provenance, ADR-050): a fact value is code's own; a number in text
   must appear in a verified quote or a fact. A cell with no verified citation, or with a number
   nothing shows, is dropped and flagged Unsupported with its reason.
6. **write_suggestions**: each kept value becomes a pending `workpaper_cell` suggestion through
   `create_suggestion` ("<person> via Agent"); adopting it is a person's act through workpapers'
   applier, never the agent's (ADR-005, AC1.1).
7. **finish_run**: the run's output keeps the suggestion ids and the Unsupported cells.

Budgets: the spec's per-call cap and the engagement's daily run cap. Gate: `workpapers.drafting`
(the route); a real firm is refused with 409 `drafting_not_enabled` while the spec's
`client_data` is `none`, and the gateway's data boundary still applies.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from abacus.ai_gateway import (
    AssembledContext,
    Attribution,
    ContextBuilder,
    GatewayCall,
    call,
    fake_responds,
    is_synthetic,
    sanitise_text,
)
from abacus.ai_gateway.routes import route_enabled
from abacus.kernel.config import settings
from abacus.kernel.db import tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.draft_start import DraftingUnavailable
from abacus.modules.agents.handoff import DraftCitation, DraftedCell, SectionDraft
from abacus.modules.agents.proposals import ProposalInvalid, create_suggestion
from abacus.modules.agents.repository import (
    finish_run,
    insert_run,
    lock_run,
    run_for_event,
    runs_since,
)
from abacus.modules.agents.section_sources import (
    CELL_TARGET,
    PackRefused,
    SourcePaper,
    section_source,
)
from abacus.modules.agents.service import (
    AgentRunNotRunning,
    _reader,  # pyright: ignore[reportPrivateUsage] -- the module's own system reader
    _run,  # pyright: ignore[reportPrivateUsage] -- the module's own run loader
    _today,  # pyright: ignore[reportPrivateUsage] -- the module's own clock
    fail_run,
)
from abacus.modules.agents.spec import AgentSpec, spec
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.agents.v2_citations import record_agent_citations
from abacus.modules.agents.workflow_types import SectionDraftInput
from abacus.modules.agents.workflows import SectionDraftWorkflow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.api import CitationClaim
from abacus.modules.identity.api import AgentContext, AuthContext, authorise
from abacus.modules.methodology.api import VersionStep, version_steps

DRAFTER: Final = "workpapers.section_drafter"
MODES: Final = frozenset({"gap", "risk_narrative", "risk", "ic", "soc1"})
PACK_ERROR: Final = "pack_configuration_error"
ANCHOR: Final = "section_draft"
MAX_STEPS: Final = 120
MAX_FACTS: Final = 80
# Why a drafted cell was dropped (shown as Unsupported, never as a value).
UNCITED: Final = "uncited"
UNVERIFIED: Final = "citation_unverified"
NO_PROVENANCE: Final = "number_without_provenance"
UNKNOWN_CELL: Final = "unknown_cell"
UNKNOWN_FACT: Final = "unknown_fact"
REVIEW_REQUIRED: Final = "review_required"
_NUMBER: Final = re.compile(r"\d[\d,]*(?:\.\d+)?")

WORKFLOWS: dict[type, WorkClass] = {SectionDraftWorkflow: spec(DRAFTER).work_class}
register_work_classes(WORKFLOWS)


class DraftingNotEnabled(DomainConflict):
    """A real firm the section drafter isn't cleared for (SPEC-036): synthetic firms only."""

    code = "drafting_not_enabled"


class DraftCapReached(DomainConflict):
    """The engagement reached its daily cap of section drafts."""

    code = "action_cap"


class UnknownMode(DomainConflict):
    """The spec declares no such mode."""

    code = "unknown_mode"


@dataclass(frozen=True)
class Fact:
    label: str  # F<n>
    name: str  # the cell it was read from
    value: dict[str, object]  # `{t, v}`, code's own


@dataclass(frozen=True)
class DraftContext:
    paper: SourcePaper
    version_id: UUID
    steps: tuple[VersionStep, ...]  # S1 is steps[0]
    facts: tuple[Fact, ...]


@dataclass(frozen=True)
class Unsupported:
    cell: str
    reason: str


@dataclass(frozen=True)
class DraftOutcome:
    run_id: UUID
    status: str  # completed | escalated
    suggestion_ids: tuple[UUID, ...]
    unsupported: tuple[Unsupported, ...]


def model_available() -> bool:
    """A real route the drafter may use is enabled, or the fake route with a responder for its
    prompt (local and test only)."""
    drafter = spec(DRAFTER)
    if any(route_enabled(r) for r in drafter.routes):
        return True
    return route_enabled("fake") and fake_responds(drafter.prompt)


def mode_call(drafter: AgentSpec, mode: str) -> tuple[str, Decimal]:
    """The mode's prompt and budget: the spec's own for the default mode (`gap`)."""
    if mode == "gap":
        return drafter.prompt, drafter.limits.max_cost_usd
    found = drafter.modes.get(mode)
    if found is None:
        raise UnknownMode(facts={"mode": "mode"})
    return found.prompt, found.max_cost_usd


# --- start (the route's slot) -------------------------------------------------------------------


async def start(
    ctx: AuthContext,
    engagement_id: UUID,
    workpaper_id: UUID,
    mode: str,
    section_key: str | None,
    idempotency_key: str,
) -> UUID:
    """One run for this paper section, once per idempotency key; the route authorised
    `workpaper.draft` and both flags."""
    drafter = spec(DRAFTER)
    mode_call(drafter, mode)
    if drafter.client_data != "cleared" and not await is_synthetic(ctx.tenant):
        raise DraftingNotEnabled
    if not model_available():
        raise DraftingUnavailable(str(engagement_id))
    engagement = await get_ref(ctx, engagement_id)
    # The route authorised it too; this public entry never relies on its caller (defence in depth).
    await authorise(ctx, "workpaper.draft", engagement.resource())
    paper = await section_source().paper(ctx.tenant, engagement_id, workpaper_id, section_key)
    event = uuid5(
        NAMESPACE_URL,
        f"abacus:section_draft:{ctx.tenant_id}:{workpaper_id}:{section_key}:{idempotency_key}",
    )
    reader = _reader(ctx.tenant_id, f"agents:{drafter.id}")
    async with tenant_session(reader) as session:
        existing = await run_for_event(session, drafter.id, event)
    if existing is not None:
        return existing.id  # a replayed start: the run it made
    run_id: UUID | None = None
    capped = False
    # A concurrent start that won the insert leaves nothing to record (MissingAuditEvent).
    with suppress(MissingAuditEvent):
        async with uow(reader) as tx:
            if (
                await runs_since(tx.session, drafter.id, engagement_id, _today())
                >= settings().screening_daily_cap
            ):
                tx.record(
                    "action_cap.refused",
                    target=Target("engagement", engagement_id),
                    after=Ref(workpaper_id=workpaper_id),
                )
                capped = True
            else:
                run_id = await insert_run(
                    tx.session,
                    tenant_id=ctx.tenant_id,
                    agent_id=drafter.id,
                    shadow=await starts_in_shadow(tx.session, reader, drafter.id),  # SPEC-036
                    spec_version=drafter.version,
                    engagement_id=engagement_id,
                    evidence_version_id=None,
                    initiator_user_id=ctx.user_id,
                    source_event_id=event,
                    task_scope=sorted(drafter.task_scope),
                )
                if run_id is not None:
                    tx.record(
                        "agent_run.started",
                        target=Target("agent_run", run_id),
                        after=Ref(workpaper_id=workpaper_id, initiator=ctx.user_id),
                    )
                    tx.record(
                        "section_draft.started",
                        target=Target("agent_run", run_id),
                        after=Ref(workpaper_id=workpaper_id),
                    )
    if capped:
        raise DraftCapReached
    if run_id is None:
        async with tenant_session(reader) as session:
            found = await run_for_event(session, drafter.id, event)
        if found is None:
            raise NotFound("agent_run")
        return found.id
    section = section_key
    with suppress(WorkflowAlreadyStartedError):
        await dispatch(
            SectionDraftWorkflow,
            SectionDraftInput(
                str(ctx.tenant_id), str(run_id), str(workpaper_id), mode, section_key or ""
            ),
            id=f"section_draft:{ctx.tenant_id}:{paper.work_item_id}:{section or 'all'}:{run_id}",
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
            id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
        )
    return run_id


# --- load_context --------------------------------------------------------------------------------


def _facts(paper: SourcePaper) -> tuple[Fact, ...]:
    """The paper's own typed figures and dates (the prior version), in cell order."""
    found: list[Fact] = []
    for c in paper.cells:
        if c.value is None or c.value.get("t") not in ("decimal", "money", "percent", "date"):
            continue
        if c.value.get("v") is None:
            continue
        name = c.cell_key if c.sheet_key == "main" else f"{c.sheet_key}!{c.cell_key}"
        found.append(Fact(f"F{len(found) + 1}", name, dict(c.value)))
        if len(found) == MAX_FACTS:
            break
    return tuple(found)


async def load_context(
    agent: AgentContext, workpaper_id: UUID, section_key: str | None
) -> DraftContext:
    engagement = await get_ref(agent, agent.engagement)
    await authorise(agent, "workpaper.read", engagement.resource())
    await authorise(agent, "procedure.read", engagement.resource())
    if engagement.methodology_version_id is None:
        raise NotFound("methodology_version")
    source = section_source()
    paper = await source.paper(agent.tenant, agent.engagement, workpaper_id, section_key)
    version = await version_steps(agent.tenant, engagement.methodology_version_id)
    steps = source.bound(version.steps, paper)
    return DraftContext(
        paper, engagement.methodology_version_id, tuple(steps[:MAX_STEPS]), _facts(paper)
    )


def build_context(mode: str, context: DraftContext, untrusted: Sequence[str]) -> AssembledContext:
    paper = context.paper
    return (
        ContextBuilder()
        .task(
            {
                "mode": mode,
                "workpaper": {"code": paper.code, "title": paper.title, "kind": paper.kind},
                "section": paper.section_key or "whole paper",
                "steps": [
                    f"S{n}: {s.program_code} step {s.number}: {s.text}"
                    for n, s in enumerate(context.steps, start=1)
                ],
                "facts": [f"{f.label}: {f.name} = {f.value.get('v')}" for f in context.facts],
                "cells": [
                    {
                        "cell": c.cell_key
                        if c.sheet_key == "main"
                        else f"{c.sheet_key}!{c.cell_key}",
                        "row": c.row_key or "",
                        "column": c.col_key or "",
                        "value": "" if c.value is None else str(c.value.get("v") or ""),
                    }
                    for c in paper.cells
                ],
                "documents": [],
            },
            untrusted=list(untrusted),
            trim="cells",
        )
        .build()
    )


# --- verify_citations and check_numbers (code; ADR-050) ----------------------------------------


def _numbers(text: str) -> set[Decimal]:
    found: set[Decimal] = set()
    for raw in _NUMBER.findall(text):
        with suppress(InvalidOperation):
            found.add(Decimal(raw.replace(",", "")))
    return found


def _claim(c: DraftCitation, context: DraftContext) -> CitationClaim | None:
    """The claim a citation makes, or None when it names a step the context didn't list (a
    document is cited only once a mode's mapping supplies documents)."""
    if c.step is None:
        return None
    index = int(c.step[1:]) - 1
    if index >= len(context.steps):
        return None
    step = context.steps[index]
    return CitationClaim(
        "methodology_step",
        {"template_version_id": str(context.version_id), "step_key": step.step_key},
        quote=c.quote,
    )


def provenance_ok(
    cell: DraftedCell, verified_quotes: Sequence[str], facts: Mapping[str, Fact]
) -> bool:
    """Every number in a text value appears in a verified quote or a fact's value."""
    if cell.text is None:
        return True
    shown: set[Decimal] = set()
    for quote in verified_quotes:
        shown |= _numbers(quote)
    for fact in facts.values():
        shown |= _numbers(str(fact.value.get("v") or ""))
    return _numbers(cell.text) <= shown


def _value(cell: DraftedCell, facts: Mapping[str, Fact]) -> dict[str, object]:
    if cell.fact is not None:
        fact = facts[cell.fact]
        kind = cast(str, fact.value.get("t"))
        return {"t": kind if kind in ("decimal", "date") else "decimal", "v": fact.value.get("v")}
    # Model text is hostile until proven otherwise: control and deceptive characters removed.
    return {"t": "text", "v": sanitise_text(cell.text or "")}


def _cell_key(cell: str) -> tuple[str, str]:
    sheet, sep, key = cell.partition("!")
    return (sheet, key) if sep else ("main", cell)


# --- draft (the workflow's activity) ------------------------------------------------------------


async def draft(
    agent: AgentContext, workpaper_id: UUID, mode: str, section_key: str | None
) -> DraftOutcome:
    """The run's draft; a terminal error ends the run as failed with its code."""
    try:
        return await _draft(agent, workpaper_id, mode, section_key)
    except PackRefused as exc:
        await _fail_pack(agent, workpaper_id, exc)
        raise
    except NotFound:
        await fail_run(agent.tenant_id, agent.agent_run_id, "not_found")
        raise


async def _fail_pack(agent: AgentContext, workpaper_id: UUID, exc: PackRefused) -> None:
    """AC6.1: the run fails with the error's code; its output keeps AUD-09 d's sentence."""
    async with uow(_reader(agent.tenant_id, f"agent-run:{agent.agent_run_id}")) as tx:
        if await finish_run(
            tx.session,
            agent.agent_run_id,
            status="failed",
            failure_code=PACK_ERROR,
            output={"error": PACK_ERROR, "message": exc.message, **exc.facts},
        ):
            tx.record("agent_run.failed", target=Target("agent_run", agent.agent_run_id))
            tx.record(
                "section_draft.failed",
                target=Target("agent_run", agent.agent_run_id),
                after=Ref(workpaper_id=workpaper_id),
            )


async def _draft(
    agent: AgentContext, workpaper_id: UUID, mode: str, section_key: str | None
) -> DraftOutcome:
    run = await _run(agent)
    drafter = spec(run.agent_id)
    prompt_ref, budget = mode_call(drafter, mode)
    context = await load_context(agent, workpaper_id, section_key)
    # Code's pack validation, before any model call (AC6.1).
    problem = await section_source().pack_problem(agent.tenant, context.version_id, context.paper)
    if problem is not None:
        raise PackRefused(problem)
    assembled = build_context(mode, context, list(drafter.untrusted_inputs))
    result = await call(
        GatewayCall(
            purpose=drafter.purpose,
            prompt=prompt_ref,
            tier=drafter.tier,
            output_schema=SectionDraft,
            budget_usd=budget,
            attribution=Attribution(agent.tenant, agent.engagement, run.agent_id, run.id),
            context=assembled,
            work_class=drafter.work_class,
            essential=drafter.essential,
            routes=drafter.routes,
            cheaper_tiers=drafter.cheaper_tiers,
            max_output_tokens=drafter.limits.max_output_tokens,
            timeout_seconds=drafter.limits.max_seconds,
        )
    )
    output = result.output
    if output is None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session, run.id, status="escalated", context_hash=assembled.sha256
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run.id))
        return DraftOutcome(run.id, "escalated", (), ())
    facts = {f.label: f for f in context.facts}
    cells = {(c.sheet_key, c.cell_key) for c in context.paper.cells}
    unsupported: list[Unsupported] = []
    kept: list[tuple[DraftedCell, tuple[UUID, ...]]] = []
    async with uow(agent.tenant) as tx:
        locked = await lock_run(tx.session, run.id)
        if locked is None or locked.status != "running":
            raise AgentRunNotRunning(locked.status if locked else "missing")
        engagement = await lock_ref(tx, agent.engagement)
        await authorise(agent, "section_draft.run", engagement.resource())
        for cell in output.cells:
            if _cell_key(cell.cell) not in cells:
                unsupported.append(Unsupported(cell.cell, UNKNOWN_CELL))
                continue
            if cell.fact is not None and cell.fact not in facts:
                unsupported.append(Unsupported(cell.cell, UNKNOWN_FACT))
                continue
            if not cell.citations:
                unsupported.append(Unsupported(cell.cell, UNCITED))
                continue
            claims = [_claim(c, context) for c in cell.citations]
            recorded = await record_agent_citations(
                tx,
                agent,
                anchor_type=ANCHOR,
                anchor_id=run.id,
                ref=cell.cell,
                claims=[c for c in claims if c is not None],
                shadow=locked.shadow,
            )
            verified = [r for r in recorded if r.verified]
            if not verified:
                unsupported.append(Unsupported(cell.cell, UNVERIFIED))
                continue
            quotes = [
                c.quote
                for c, claim in zip(cell.citations, claims, strict=True)
                if claim is not None
            ]
            verified_quotes = [q for q, r in zip(quotes, recorded, strict=True) if r.verified]
            if not provenance_ok(cell, verified_quotes, facts):
                unsupported.append(Unsupported(cell.cell, NO_PROVENANCE))
                continue
            kept.append((cell, tuple(r.id for r in verified)))
    suggestions: list[UUID] = []
    for cell, citation_ids in kept:
        sheet, key = _cell_key(cell.cell)
        try:
            suggestions.append(
                await create_suggestion(
                    agent,
                    engagement_id=agent.engagement,
                    target_type=CELL_TARGET,
                    target_id=context.paper.workpaper_id,
                    field_key=key if sheet == "main" else f"{sheet}!{key}",
                    proposed_value=_value(cell, facts),
                    citation_ids=citation_ids,
                    rationale_ref=f"{ANCHOR}:{run.id}",
                )
            )
        except ProposalInvalid:
            unsupported.append(Unsupported(cell.cell, REVIEW_REQUIRED))
    async with uow(agent.tenant) as tx:
        if await finish_run(
            tx.session,
            run.id,
            status="completed",
            context_hash=assembled.sha256,
            output={
                "mode": mode,
                "workpaper_id": str(workpaper_id),
                "suggestion_ids": [str(s) for s in suggestions],
                "unsupported": [{"cell": u.cell, "reason": u.reason} for u in unsupported],
            },
        ):
            tx.record(
                "agent_run.completed",
                target=Target("agent_run", run.id),
                after=Ref(suggestions=len(suggestions), unsupported=len(unsupported)),
            )
    return DraftOutcome(run.id, "completed", tuple(suggestions), tuple(unsupported))


__all__ = [
    "DRAFTER",
    "MODES",
    "PACK_ERROR",
    "WORKFLOWS",
    "DraftCapReached",
    "DraftContext",
    "DraftOutcome",
    "DraftingNotEnabled",
    "Fact",
    "UnknownMode",
    "Unsupported",
    "build_context",
    "draft",
    "load_context",
    "model_available",
    "provenance_ok",
    "start",
]
