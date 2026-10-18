"""The guidance drafter (SPEC-035; TASK-072). PROTECTED.

`create_draft_run` starts a run for a request item on behalf of a person (the engagement's daily
cap applies). `draft` builds the context by code in fixed layers (ADR-051): the year end, the item
(the firm's words, still delimited as untrusted: imported lists may carry client wording, ADR-052)
and up to three of the firm's own guidance texts as tone examples (Q4), both untrusted. The
gateway enforces the data boundary (ADR-112) and budgets. Code checks the draft's form
(`guidance_checks`) and records it; a failing draft is kept but never shown. Nothing is applied:
the drafter proposes, a person approves (ADR-005, ADR-111).

On a methodology template (SPEC-035 Q3; TASK-074 D1) the run is firm-level: no engagement, the
firm's daily cap and monthly budget, and the context has no year end (a template spans years). The
examples are the template's own guidance on other items.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.ai_gateway import (
    AssembledContext,
    Attribution,
    ContextBuilder,
    GatewayCall,
    call,
    sanitise_text,
)
from abacus.ai_gateway.routes import route_enabled
from abacus.kernel.config import settings
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.guidance_checks import check_draft
from abacus.modules.agents.handoff import GuidanceDraft
from abacus.modules.agents.repository import (
    finish_run,
    insert_guidance_draft,
    insert_run,
    insert_template_draft,
    lock_run,
    run_for_event,
    runs_since,
)
from abacus.modules.agents.service import (
    AgentRunNotRunning,
    _reader,  # pyright: ignore[reportPrivateUsage] -- the module's own system reader
    _run,  # pyright: ignore[reportPrivateUsage] -- the module's own run loader
    _today,  # pyright: ignore[reportPrivateUsage] -- the module's own clock
    fail_run,
)
from abacus.modules.agents.spec import spec
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.agents.upload_review import TERMINAL
from abacus.modules.engagements.api import (
    MethodologyVersionView,
    check_facts,
    get_ref,
    lock_ref,
    version_detail,
)
from abacus.modules.identity.api import (
    AgentContext,
    Resource,
    authorise,
    is_active_member,
    member_context,
)
from abacus.modules.requests.api import RequestItemView, document_kind, request_items_for

DRAFTER = "requests.guidance_drafter"
MAX_EXAMPLES: Final = 3


@dataclass(frozen=True)
class DraftOutcome:
    run_id: UUID
    status: str  # completed | escalated
    shown: bool  # passed code's checks
    reasons: tuple[str, ...]


def model_available() -> bool:
    """A real route the drafter may use is enabled (the fake model has no drafter answers)."""
    return any(route_enabled(r) for r in spec(DRAFTER).routes)


async def _items(tenant_id: UUID, person: UUID, engagement_id: UUID) -> list[RequestItemView]:
    """The engagement's items as `person` sees them (their own context, read fresh)."""
    ctx = await member_context(tenant_id, person)
    if ctx is None:
        return []
    return list(await request_items_for(ctx, engagement_id))


def examples(items: list[RequestItemView], target: UUID) -> list[dict[str, str]]:
    """Q4: up to three of the firm's own guidance texts on other items, as tone examples."""
    found = [
        {"request": i.description, "why": i.why or "", "good_looks_like": i.good_looks_like or ""}
        for i in items
        if i.id != target and i.guidance_source == "firm" and i.why and i.good_looks_like
    ]
    return found[:MAX_EXAMPLES]


async def create_draft_run(
    tenant_id: UUID,
    engagement_id: UUID,
    request_item_id: UUID,
    source_event_id: UUID,
    requested_by: UUID | None,
) -> UUID | None:
    """The drafter's run for this item, once per event, on behalf of `requested_by`. None
    without a person, a real model route, the item, or over the daily cap (audited)."""
    if requested_by is None or not await is_active_member(tenant_id, requested_by):
        return None
    if not model_available():
        return None
    if not any(
        i.id == request_item_id for i in await _items(tenant_id, requested_by, engagement_id)
    ):
        return None
    drafter = spec(DRAFTER)
    reader = _reader(tenant_id, f"agents:{drafter.id}")
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            if await run_for_event(tx.session, drafter.id, source_event_id) is None and (
                await runs_since(tx.session, drafter.id, engagement_id, _today())
                >= settings().screening_daily_cap
            ):
                tx.record(
                    "action_cap.refused",
                    target=Target("engagement", engagement_id),
                    after=Ref(request_item_id=request_item_id),
                )
                return None
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=drafter.id,
                shadow=await starts_in_shadow(tx.session, reader, drafter.id),  # SPEC-036
                spec_version=drafter.version,
                engagement_id=engagement_id,
                evidence_version_id=None,
                initiator_user_id=requested_by,
                source_event_id=source_event_id,
                task_scope=sorted(drafter.task_scope),
            )
            if run_id is None:
                existing = await run_for_event(tx.session, drafter.id, source_event_id)
                run_id = existing.id if existing is not None else None
            else:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(request_item_id=request_item_id, initiator=requested_by),
                )
    except MissingAuditEvent:
        pass
    return run_id


def build_context(
    item: RequestItemView, year_end: str, firm_examples: list[dict[str, str]], untrusted: list[str]
) -> AssembledContext:
    return _context(
        f"Year end {year_end}.",
        {
            "description": item.description,
            "audit_area": item.audit_area,
            "expects": item.document_kind or "not specified",
            "tier": item.retrievability_tier or "not classified",
        },
        firm_examples,
        untrusted,
    )


def _context(
    engagement: str,
    item: dict[str, str],
    firm_examples: list[dict[str, str]],
    untrusted: list[str],
) -> AssembledContext:
    return (
        ContextBuilder()
        .text("engagement", engagement)
        .task({"item": item, "examples": firm_examples}, untrusted=untrusted)
        .build()
    )


# --- On a methodology template (SPEC-035 Q3; TASK-074) ------------------------------------------

TEMPLATE_CONTEXT: Final = (
    "A methodology template the firm uses on every engagement; no year end (it spans years)."
)


def template_examples(version: MethodologyVersionView, target: int) -> list[dict[str, str]]:
    """Q4 on a template: up to three of its own guidance texts on other items."""
    found = [
        {"request": t.description, "why": t.why, "good_looks_like": t.good_looks_like}
        for i, t in enumerate(version.items)
        if i != target and t.why and t.good_looks_like
    ]
    return found[:MAX_EXAMPLES]


def template_item(version: MethodologyVersionView, position: int) -> dict[str, str] | None:
    if not 0 <= position < len(version.items):
        return None
    t = version.items[position]
    area = next((a.name for a in version.areas if a.code == t.area_code), t.area_code)
    return {
        "description": t.description,
        "audit_area": area,
        "expects": document_kind(t.description, area) or "not specified",
        "tier": t.tier,
    }


async def create_template_draft_run(
    tenant_id: UUID,
    version_id: UUID,
    position: int,
    source_event_id: UUID,
    requested_by: UUID | None,
) -> UUID | None:
    """The drafter's firm-level run for a template item, once per event, on behalf of
    `requested_by` (D1). None without a person, a real model route, or over the firm's daily cap
    (audited)."""
    if requested_by is None or not await is_active_member(tenant_id, requested_by):
        return None
    if not model_available():
        return None
    version = await version_detail(_reader(tenant_id, "agents:templates"), version_id)
    if template_item(version, position) is None:
        return None
    drafter = spec(DRAFTER)
    reader = _reader(tenant_id, f"agents:{drafter.id}")
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            if await run_for_event(tx.session, drafter.id, source_event_id) is None and (
                await runs_since(tx.session, drafter.id, None, _today())
                >= settings().screening_daily_cap
            ):
                tx.record(
                    "action_cap.refused",
                    target=Target("methodology_version", version_id),
                    after=Ref(position=position),
                )
                return None
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=drafter.id,
                shadow=await starts_in_shadow(tx.session, reader, drafter.id),  # SPEC-036
                spec_version=drafter.version,
                engagement_id=None,
                evidence_version_id=None,
                initiator_user_id=requested_by,
                source_event_id=source_event_id,
                task_scope=sorted(drafter.task_scope),
                methodology_version_id=version_id,
            )
            if run_id is None:
                existing = await run_for_event(tx.session, drafter.id, source_event_id)
                run_id = existing.id if existing is not None else None
            else:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(
                        methodology_version_id=version_id,
                        position=position,
                        initiator=requested_by,
                    ),
                )
    except MissingAuditEvent:
        pass
    return run_id


async def draft_template(agent: AgentContext, position: int) -> DraftOutcome:
    """A firm-level run's draft for one template item; a terminal error fails the run."""
    try:
        return await _draft_template(agent, position)
    except tuple(TERMINAL) as exc:
        code = next(c for kind, c in TERMINAL.items() if isinstance(exc, kind))
        await fail_run(agent.tenant_id, agent.agent_run_id, code)
        raise


async def _draft_template(agent: AgentContext, position: int) -> DraftOutcome:
    run = await _run(agent)
    if agent.engagement_id is not None or run.methodology_version_id is None:
        raise NotFound("methodology_version")  # only a firm-level run drafts on a template
    drafter = spec(run.agent_id)
    firm = Resource.firm(agent.tenant_id)
    await authorise(agent, "methodology.read", firm)
    version = await version_detail(agent.tenant, run.methodology_version_id)
    item = template_item(version, position)
    if item is None:
        raise NotFound("template_item")
    context = _context(
        TEMPLATE_CONTEXT,
        item,
        template_examples(version, position),
        list(drafter.untrusted_inputs),
    )
    result = await call(
        GatewayCall(
            purpose=drafter.purpose,
            prompt=drafter.prompt,
            tier=drafter.tier,
            output_schema=GuidanceDraft,
            budget_usd=drafter.limits.max_cost_usd,
            attribution=Attribution(agent.tenant, None, run.agent_id, run.id),
            context=context,
            work_class=drafter.work_class,
            essential=drafter.essential,
            routes=drafter.routes,
            cheaper_tiers=drafter.cheaper_tiers,
            max_output_tokens=drafter.limits.max_output_tokens,
            timeout_seconds=drafter.limits.max_seconds,
        )
    )
    if result.output is None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session, run.id, status="escalated", context_hash=context.sha256
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run.id))
        return DraftOutcome(run.id, "escalated", False, ())
    output = result.output
    reasons = check_draft(output, description=item["description"], area=item["audit_area"])
    async with uow(agent.tenant) as tx:
        locked = await lock_run(tx.session, run.id)
        if locked is None or locked.status != "running":
            raise AgentRunNotRunning(locked.status if locked else "missing")
        await authorise(agent, "guidance_draft.run", firm)
        await insert_template_draft(
            tx.session,
            tenant_id=agent.tenant_id,
            methodology_version_id=run.methodology_version_id,
            position=position,
            agent_run_id=run.id,
            prompt_ref=drafter.prompt,
            why=sanitise_text(output.why)[:300] or "(empty)",
            good_looks_like=sanitise_text(output.good_looks_like)[:600] or "(empty)",
            effort=output.effort,
            effort_reason=sanitise_text(output.effort_reason or "")[:160] or None,
            blocks_fieldwork=output.blocks_fieldwork,
            blocks_reason=sanitise_text(output.blocks_reason or "")[:160] or None,
            passed_checks=not reasons,
            check_reasons=reasons,
        )
        await finish_run(
            tx.session,
            run.id,
            status="completed",
            context_hash=context.sha256,
            output=output.model_dump(mode="json"),
        )
        tx.record(
            "guidance_draft.created",
            target=Target("methodology_version", run.methodology_version_id),
            after=Ref(agent_run_id=run.id, position=position, shown=int(not reasons)),
        )
    return DraftOutcome(run.id, "completed", not reasons, tuple(reasons))


async def draft(agent: AgentContext, request_item_id: UUID) -> DraftOutcome:
    """The run's draft; a terminal error ends the run as failed with its code."""
    try:
        return await _draft(agent, request_item_id)
    except tuple(TERMINAL) as exc:
        code = next(c for kind, c in TERMINAL.items() if isinstance(exc, kind))
        await fail_run(agent.tenant_id, agent.agent_run_id, code)
        raise


async def _draft(agent: AgentContext, request_item_id: UUID) -> DraftOutcome:
    run = await _run(agent)
    drafter = spec(run.agent_id)
    engagement = await get_ref(agent, agent.engagement)
    await authorise(agent, "request_item.read", engagement.resource())
    items = await _items(agent.tenant_id, run.initiator_user_id, agent.engagement)
    item = next((i for i in items if i.id == request_item_id), None)
    facts = await check_facts(agent.tenant, agent.engagement)
    if item is None or facts is None:
        raise NotFound("request_item")
    context = build_context(
        item,
        facts.fiscal_period_end.isoformat(),
        examples(items, request_item_id),
        list(drafter.untrusted_inputs),
    )
    result = await call(
        GatewayCall(
            purpose=drafter.purpose,
            prompt=drafter.prompt,
            tier=drafter.tier,
            output_schema=GuidanceDraft,
            budget_usd=drafter.limits.max_cost_usd,
            attribution=Attribution(agent.tenant, agent.engagement, run.agent_id, run.id),
            context=context,
            work_class=drafter.work_class,
            essential=drafter.essential,
            routes=drafter.routes,
            cheaper_tiers=drafter.cheaper_tiers,
            max_output_tokens=drafter.limits.max_output_tokens,
            timeout_seconds=drafter.limits.max_seconds,
        )
    )
    if result.output is None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session, run.id, status="escalated", context_hash=context.sha256
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run.id))
        return DraftOutcome(run.id, "escalated", False, ())
    output = result.output
    reasons = check_draft(
        output,
        description=item.description,
        area=item.audit_area,
        year_end_year=facts.fiscal_period_end.year,
    )
    async with uow(agent.tenant) as tx:
        locked = await lock_run(tx.session, run.id)
        if locked is None or locked.status != "running":
            raise AgentRunNotRunning(locked.status if locked else "missing")
        locked_engagement = await lock_ref(tx, agent.engagement)
        await authorise(agent, "guidance_draft.run", locked_engagement.resource())
        await insert_guidance_draft(
            tx.session,
            tenant_id=agent.tenant_id,
            engagement_id=agent.engagement,
            request_item_id=request_item_id,
            agent_run_id=run.id,
            prompt_ref=drafter.prompt,
            why=sanitise_text(output.why)[:300] or "(empty)",
            good_looks_like=sanitise_text(output.good_looks_like)[:600] or "(empty)",
            effort=output.effort,
            effort_reason=sanitise_text(output.effort_reason or "")[:160] or None,
            blocks_fieldwork=output.blocks_fieldwork,
            blocks_reason=sanitise_text(output.blocks_reason or "")[:160] or None,
            passed_checks=not reasons,
            check_reasons=reasons,
        )
        await finish_run(
            tx.session,
            run.id,
            status="completed",
            context_hash=context.sha256,
            output=output.model_dump(mode="json"),
        )
        tx.record(
            "guidance_draft.created",
            target=Target("request_item", request_item_id),
            after=Ref(agent_run_id=run.id, shown=int(not reasons)),
        )
    return DraftOutcome(run.id, "completed", not reasons, tuple(reasons))
