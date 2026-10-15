"""The matcher (SPEC-033; TASK-065). PROTECTED.

`create_match_run` starts a run for an extracted inbox file on behalf of a person (the
engagement's daily cap applies). `match` builds the context by code in fixed layers (ADR-051):
the engagement, the candidate requests as R1..Rn (D1) with code's scores and reasons, and the
document excerpt, the only untrusted field (ADR-052, ADR-064). The gateway enforces the data
boundary (ADR-112) and budgets. Code maps references back to requests (an unknown one is
discarded), verifies every quote against the extraction (ADR-066), and records the proposals.
Nothing is assigned: the matcher proposes, a person decides (ADR-005).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
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
from abacus.modules.agents.document_citations import sheet_lines, verify
from abacus.modules.agents.handoff import MatchOutput, VerifiedDocumentCitation
from abacus.modules.agents.repository import (
    finish_run,
    insert_inbox_match,
    insert_match_proposals,
    insert_run,
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
from abacus.modules.agents.upload_review import TERMINAL
from abacus.modules.engagements.api import check_facts, get_ref, lock_ref
from abacus.modules.evidence.api import MatchMaterial, match_material
from abacus.modules.identity.api import AgentContext, authorise, is_active_member

MATCHER = "evidence.matcher"
REASON_TEXT = {
    "kind": "document kind matches",
    "date": "covers the year end",
    "account": "account digits match",
    "holder": "in the client's name",
    "file_name": "file name words",
}


@dataclass(frozen=True)
class MatchOutcome:
    run_id: UUID
    status: str  # completed | escalated
    none_fit: bool
    shown: tuple[UUID, ...]  # the requests shown, best first
    hidden: int


def model_available() -> bool:
    """A real route the matcher may use is enabled (the fake model has no matcher answers)."""
    return any(route_enabled(r) for r in spec(MATCHER).routes)


def refs(material: MatchMaterial) -> dict[str, UUID]:
    """D1: R1..Rn in candidate order."""
    return {f"R{n}": c.request_item_id for n, c in enumerate(material.candidates, start=1)}


async def create_match_run(
    tenant_id: UUID, inbox_file_id: UUID, source_event_id: UUID, requested_by: UUID | None
) -> UUID | None:
    """The matcher's run for this file, once per event, on behalf of `requested_by`. None
    without a person to act for, a real model route, an extraction, candidates, or over the
    daily cap (audited)."""
    if requested_by is None or not await is_active_member(tenant_id, requested_by):
        return None
    if not model_available():
        return None
    matcher = spec(MATCHER)
    reader = _reader(tenant_id, f"agents:{matcher.id}")
    material = await match_material(reader, inbox_file_id)
    if material is None or material.extraction_status != "extracted" or not material.candidates:
        return None  # SPEC-033 §4.5: an unreadable or unextracted file isn't matched
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            if await run_for_event(tx.session, matcher.id, source_event_id) is None and (
                await runs_since(tx.session, matcher.id, material.engagement_id, _today())
                >= settings().screening_daily_cap
            ):
                tx.record(
                    "action_cap.refused",
                    target=Target("engagement", material.engagement_id),
                    after=Ref(inbox_file_id=inbox_file_id),
                )
                return None
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=matcher.id,
                spec_version=matcher.version,
                engagement_id=material.engagement_id,
                evidence_version_id=None,
                inbox_file_id=inbox_file_id,
                initiator_user_id=requested_by,
                source_event_id=source_event_id,
                task_scope=sorted(matcher.task_scope),
            )
            if run_id is None:
                existing = await run_for_event(tx.session, matcher.id, source_event_id)
                run_id = existing.id if existing is not None else None
            else:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(inbox_file_id=inbox_file_id, initiator=requested_by),
                )
    except MissingAuditEvent:
        pass  # the run already existed
    return run_id


def document_blocks(material: MatchMaterial) -> list[str]:
    blocks = [f"Page {number}:\n{text}" for number, text in material.excerpt_pages]
    for name, rows in material.excerpt_tables:
        lines = "\n".join(sheet_lines(rows))
        blocks.append(f"Sheet {name or '(only sheet)'}:\n{lines}")
    return blocks


def build_context(
    material: MatchMaterial, year_end: str, entity: str, untrusted: list[str]
) -> AssembledContext:
    """The fixed layers (ADR-051). Request descriptions are the firm's own words; the document
    excerpt is the only untrusted, trimmable field."""
    return (
        ContextBuilder()
        .text("engagement", f"Year end {year_end}. Client company: {entity}.")
        .task(
            {
                "candidates": [
                    {
                        "ref": ref,
                        "request": c.description,
                        "area": c.audit_area,
                        "expects": c.document_kind or "not specified",
                        "accounts_still_needed": list(c.needed_accounts),
                        "code_score": c.score,
                        "code_reasons": [REASON_TEXT[r.code] for r in c.reasons],
                    }
                    for ref, c in zip(refs(material), material.candidates, strict=True)
                ],
                "excerpt_truncated": material.truncated,
                "document": document_blocks(material),
            },
            untrusted=untrusted,
            trim="document",
        )
        .build()
    )


async def match(agent: AgentContext, inbox_file_id: UUID) -> MatchOutcome:
    """The run's proposals; a terminal error ends the run as failed with its code."""
    try:
        return await _match(agent, inbox_file_id)
    except tuple(TERMINAL) as exc:
        code = next(c for kind, c in TERMINAL.items() if isinstance(exc, kind))
        await fail_run(agent.tenant_id, agent.agent_run_id, code)
        raise


def _citation(c: VerifiedDocumentCitation) -> dict[str, object]:
    found = asdict(c)
    found["quote"] = sanitise_text(c.quote)
    return found


async def _match(agent: AgentContext, inbox_file_id: UUID) -> MatchOutcome:
    run = await _run(agent)
    matcher = spec(run.agent_id)
    engagement = await get_ref(agent, agent.engagement)
    await authorise(agent, "evidence.read", engagement.resource())
    material = await match_material(agent.tenant, inbox_file_id)
    facts = await check_facts(agent.tenant, agent.engagement)
    if material is None or facts is None or material.engagement_id != agent.engagement:
        raise NotFound("inbox_file")
    context = build_context(
        material,
        facts.fiscal_period_end.isoformat(),
        facts.client_entity_name,
        list(matcher.untrusted_inputs),
    )
    result = await call(
        GatewayCall(
            purpose=matcher.purpose,
            prompt=matcher.prompt,
            tier=matcher.tier,
            output_schema=MatchOutput,
            budget_usd=matcher.limits.max_cost_usd,
            attribution=Attribution(agent.tenant, agent.engagement, run.agent_id, run.id),
            context=context,
            work_class=matcher.work_class,
            essential=matcher.essential,
            routes=matcher.routes,
            cheaper_tiers=matcher.cheaper_tiers,
            max_output_tokens=matcher.limits.max_output_tokens,
            timeout_seconds=matcher.limits.max_seconds,
        )
    )
    if result.output is None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session, run.id, status="escalated", context_hash=context.sha256
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run.id))
        return MatchOutcome(run.id, "escalated", False, (), 0)
    output = result.output
    known = refs(material)
    threshold = matcher.confidence_routing.below
    rows: list[dict[str, object]] = []
    seen: set[UUID] = set()
    for proposal in output.proposals:
        item = known.get(proposal.request)
        if item is None or item in seen:
            continue  # a reference it wasn't given, or a repeat: discarded (D1)
        seen.add(item)
        checked = verify(proposal.citations, material.pages, material.sheets)
        shown = any(c.verified for c in checked) and Decimal(str(proposal.confidence)) >= threshold
        rows.append(
            {
                "tenant_id": agent.tenant_id,
                "rank": len(rows) + 1,
                "request_item_id": item,
                "confidence": Decimal(str(proposal.confidence)).quantize(Decimal("0.001")),
                "rationale": sanitise_text(proposal.rationale)[:300] or "(no rationale)",
                "citations": [_citation(c) for c in checked],
                "shown": shown,
            }
        )
    async with uow(agent.tenant) as tx:
        locked = await lock_run(tx.session, run.id)
        if locked is None or locked.status != "running":
            raise AgentRunNotRunning(locked.status if locked else "missing")
        locked_engagement = await lock_ref(tx, agent.engagement)
        await authorise(agent, "inbox_match.run", locked_engagement.resource())
        match_id = await insert_inbox_match(
            tx.session,
            values={
                "tenant_id": agent.tenant_id,
                "engagement_id": agent.engagement,
                "inbox_file_id": inbox_file_id,
                "agent_run_id": run.id,
                "prompt_ref": matcher.prompt,
                "none_fit": output.none_fit,
                "truncated": material.truncated or bool(context.truncated),
            },
        )
        await insert_match_proposals(tx.session, [{**r, "match_id": match_id} for r in rows])
        await finish_run(
            tx.session,
            run.id,
            status="completed",
            context_hash=context.sha256,
            output=output.model_dump(mode="json"),
        )
        shown = tuple(r["request_item_id"] for r in rows if r["shown"])
        tx.record(
            "inbox_match.created",
            target=Target("inbox_file", inbox_file_id),
            after=Ref(
                agent_run_id=run.id,
                shown=len(shown),
                hidden=len(rows) - len(shown),
                none_fit=int(output.none_fit),
            ),
        )
    return MatchOutcome(
        run.id,
        "completed",
        output.none_fit,
        tuple(UUID(str(i)) for i in shown),
        len(rows) - len(shown),
    )
