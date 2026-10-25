"""The upload reviewer (SPEC-030; TASK-058). PROTECTED.

`create_review_run` starts a run for an extracted evidence version on behalf of a person (the
engagement's daily cap applies, SPEC-007). `review` builds the context by code in the fixed layers
(ADR-051), with the document excerpt the only untrusted field (ADR-052, ADR-064); calls the
gateway, which enforces the data boundary (ADR-112) and budgets; verifies every quote against the
extraction by code (ADR-066); and records the review. A flag is shown to the firm only with a
verified quote and enough confidence (SPEC-030 Q3). Nothing here changes the evidence: the agent
proposes, people decide (ADR-005).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from uuid import UUID

from abacus.ai_gateway import (
    AssembledContext,
    Attribution,
    BudgetExceeded,
    BudgetExhausted,
    CallTooLarge,
    ContextBuilder,
    ContextTooLarge,
    DataBoundaryRefused,
    DatasetTooLarge,
    GatewayCall,
    GatewayRefused,
    call,
    sanitise_text,
)
from abacus.ai_gateway.routes import route_enabled
from abacus.kernel.config import settings
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.document_citations import sheet_lines, verify
from abacus.modules.agents.events import ProposalRecorded, UploadReviewRecorded
from abacus.modules.agents.handoff import UploadReviewOutput, VerifiedDocumentCitation
from abacus.modules.agents.repository import (
    finish_run,
    insert_review_flags,
    insert_run,
    insert_upload_review,
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
from abacus.modules.agents.tri_gate import model_blocked
from abacus.modules.agents.v2_citations import document_claims, record_agent_citations
from abacus.modules.engagements.api import check_facts, get_ref, lock_ref
from abacus.modules.evidence.api import ReviewMaterial, is_version_withdrawn, review_material
from abacus.modules.identity.api import (
    AgentContext,
    Forbidden,
    acts_for_offshore,
    authorise,
    is_active_member,
    is_offshore,
)
from abacus.modules.requests.api import items_of_version

REVIEWER = "evidence.upload_reviewer"
# Problems code already found (balances, totals, period, company): an "altered" flag about the
# same document would only repeat them, so it's kept hidden (TASK-058/059).
CODE_FINDINGS = frozenset(
    {"running_balance_breaks", "closing_balance_differs", "totals_dont_add_up"}
    | {"wrong_entity", "wrong_period", "stale_as_of"}
)
TERMINAL: dict[type[Exception], str] = {
    DataBoundaryRefused: "data_boundary",  # SPEC-030 AC-5: not run, never retried
    DatasetTooLarge: "context_too_large",
    ContextTooLarge: "context_too_large",
    BudgetExceeded: "budget_exceeded",
    BudgetExhausted: "budget_exhausted",
    CallTooLarge: "context_too_large",
    GatewayRefused: "gateway_refused",
    Forbidden: "forbidden",
    NotFound: "not_found",
}


@dataclass(frozen=True)
class ReviewOutcome:
    run_id: UUID
    status: str  # completed | escalated
    shown: int
    hidden: int


def model_available() -> bool:
    """A real route the reviewer may use is enabled (TASK-059 D3): the fake model has no
    reviewer answers, so without one nothing is started (the local stack, unless a developer
    turns on the real model for the synthetic Dev firm)."""
    return any(route_enabled(r) for r in spec(REVIEWER).routes)  # real routes only


async def create_review_run(
    tenant_id: UUID, evidence_version_id: UUID, source_event_id: UUID, requested_by: UUID | None
) -> UUID | None:
    """The reviewer's run for this version, once per event, on behalf of `requested_by`. None
    without a person to act for, without an extraction, or over the daily cap (audited)."""
    if requested_by is None or not await is_active_member(tenant_id, requested_by):
        return None
    if not model_available():
        return None
    reviewer = spec(REVIEWER)
    reader = _reader(tenant_id, f"agents:{reviewer.id}")
    items = await items_of_version(reader, evidence_version_id)
    if await model_blocked(reader, [i.id for i in items]):
        return None  # P-06-T20: tax-return information, no consent registered: no model call
    # DEC-52 (TASK-1207 review): for an offshore member, only the masked text, after its scan.
    masked = await is_offshore(reader, requested_by)
    material = await review_material(reader, evidence_version_id, masked=masked)
    if material is None or material.extraction_status != "extracted":
        return None  # SPEC-030 AC-4: an unreadable or unextracted upload isn't reviewed
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            if await run_for_event(tx.session, reviewer.id, source_event_id) is None and (
                await runs_since(tx.session, reviewer.id, material.engagement_id, _today())
                >= settings().screening_daily_cap
            ):
                tx.record(
                    "action_cap.refused",
                    target=Target("engagement", material.engagement_id),
                    after=Ref(evidence_version_id=evidence_version_id),
                )
                return None
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=reviewer.id,
                shadow=await starts_in_shadow(tx.session, reader, reviewer.id),  # SPEC-036
                spec_version=reviewer.version,
                engagement_id=material.engagement_id,
                evidence_version_id=evidence_version_id,
                initiator_user_id=requested_by,
                source_event_id=source_event_id,
                task_scope=sorted(reviewer.task_scope),
            )
            if run_id is None:
                existing = await run_for_event(tx.session, reviewer.id, source_event_id)
                run_id = existing.id if existing is not None else None
            else:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(evidence_version_id=evidence_version_id, initiator=requested_by),
                )
    except MissingAuditEvent:
        pass  # the run already existed
    return run_id


def document_blocks(material: ReviewMaterial) -> list[str]:
    """The excerpt as blocks, in order, for the context's one trimmable, untrusted field."""
    blocks = [f"Page {number}:\n{text}" for number, text in material.excerpt_pages]
    for name, rows in material.excerpt_tables:
        lines = "\n".join(sheet_lines(rows))
        blocks.append(f"Sheet {name or '(only sheet)'}:\n{lines}")
    return blocks


def build_context(
    material: ReviewMaterial,
    year_end: str,
    entity: str,
    untrusted: list[str],
    evidence_version_id: UUID | None = None,
) -> AssembledContext:
    builder = ContextBuilder()
    if evidence_version_id is not None:
        builder.sources(evidence_version_id)  # Q-02-T20: an access event when it is sent
    return (
        builder.text("engagement", f"Year end {year_end}. Client entity: {entity}.")
        .task(
            {
                "request": material.item_description,
                "document_kind": material.document_kind or "not specified",
                "checks_by_code": [
                    {"check": code, "outcome": outcome, "reason": reason}
                    for code, outcome, reason in material.checks
                ],
                "excerpt_truncated": material.truncated,
                "document": document_blocks(material),
            },
            untrusted=untrusted,
            trim="document",
        )
        .build()
    )


async def review(agent: AgentContext) -> ReviewOutcome:
    """The run's review; a terminal error ends the run as failed with its code."""
    try:
        return await _review(agent)
    except tuple(TERMINAL) as exc:
        code = next(c for kind, c in TERMINAL.items() if isinstance(exc, kind))
        await fail_run(agent.tenant_id, agent.agent_run_id, code)
        raise


def _citation(c: VerifiedDocumentCitation) -> dict[str, object]:
    found = asdict(c)
    found["quote"] = sanitise_text(c.quote)
    return found


async def review_material_for(agent: AgentContext, version_id: UUID) -> ReviewMaterial | None:
    """What the reviewer reads, for a run authorised on the version's engagement: the
    extraction's text, or only its masked projection when the run acts for an offshore member
    (DEC-52, TASK-1207 review; None before the PII scan: the run can't proceed)."""
    return await review_material(agent.tenant, version_id, masked=await acts_for_offshore(agent))


async def _review(agent: AgentContext) -> ReviewOutcome:
    run = await _run(agent)
    if run.evidence_version_id is None:
        raise NotFound("evidence_version")
    reviewer = spec(run.agent_id)
    engagement = await get_ref(agent, agent.engagement)
    await authorise(agent, "evidence.read", engagement.resource())
    material = await review_material_for(agent, run.evidence_version_id)
    facts = await check_facts(agent.tenant, agent.engagement)
    if material is None or facts is None:
        raise NotFound("upload_extraction")
    context = build_context(
        material,
        facts.fiscal_period_end.isoformat(),
        facts.client_entity_name,
        list(reviewer.untrusted_inputs),
        run.evidence_version_id,
    )
    result = await call(
        GatewayCall(
            purpose=reviewer.purpose,
            prompt=reviewer.prompt,
            tier=reviewer.tier,
            output_schema=UploadReviewOutput,
            budget_usd=reviewer.limits.max_cost_usd,
            attribution=Attribution(agent.tenant, agent.engagement, run.agent_id, run.id),
            context=context,
            work_class=reviewer.work_class,
            essential=reviewer.essential,
            routes=reviewer.routes,
            cheaper_tiers=reviewer.cheaper_tiers,
            max_output_tokens=reviewer.limits.max_output_tokens,
            timeout_seconds=reviewer.limits.max_seconds,
        )
    )
    if result.output is None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session, run.id, status="escalated", context_hash=context.sha256
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run.id))
        return ReviewOutcome(run.id, "escalated", 0, 0)
    output = result.output
    threshold = reviewer.confidence_routing.below
    # Code has the last word on what it checks (ADR-050, SPEC-030 amendment): when it already
    # found such a problem, an "altered" flag would only repeat it, so it's kept hidden.
    code_found = any(
        code in CODE_FINDINGS and outcome == "problem" for code, outcome, _ in material.checks
    )
    rows: list[dict[str, object]] = []
    for position, flag in enumerate(output.flags, start=1):
        checked = verify(flag.citations, material.pages, material.sheets)
        shown = (
            any(c.verified for c in checked)
            and Decimal(str(flag.confidence)) >= threshold
            and not (flag.category == "altered" and code_found)
        )
        rows.append(
            {
                "tenant_id": agent.tenant_id,
                "position": position,
                "category": flag.category,
                "confidence": Decimal(str(flag.confidence)).quantize(Decimal("0.001")),
                "rationale": sanitise_text(flag.rationale)[:600] or "(no rationale)",
                "citations": [_citation(c) for c in checked],
                "shown": shown,
            }
        )
    if await is_version_withdrawn(agent.tenant, run.evidence_version_id):
        # P-06-T19 (ADR-162 §4): withdrawn while the run was in flight: it records nothing.
        raise NotFound("evidence_version")
    async with uow(agent.tenant) as tx:
        locked = await lock_run(tx.session, run.id)
        if locked is None or locked.status != "running":
            raise AgentRunNotRunning(locked.status if locked else "missing")
        locked_engagement = await lock_ref(tx, agent.engagement)
        await authorise(agent, "upload_review.run", locked_engagement.resource())
        review_id = await insert_upload_review(
            tx.session,
            values={
                "tenant_id": agent.tenant_id,
                "engagement_id": agent.engagement,
                "evidence_version_id": run.evidence_version_id,
                "agent_run_id": run.id,
                "prompt_ref": reviewer.prompt,
                "document_kind": material.document_kind,
                "no_concerns": not any(r["shown"] for r in rows),
                "truncated": material.truncated or bool(context.truncated),
            },
        )
        await insert_review_flags(tx.session, [{**r, "review_id": review_id} for r in rows])
        # P-03-T10: each flag's quotes as v2 rows on the version, verified by code (DEC-267).
        for position, flag in enumerate(output.flags, start=1):
            await record_agent_citations(
                tx,
                agent,
                anchor_type="upload_review",
                anchor_id=review_id,
                ref=f"F{position}",
                claims=document_claims(
                    flag.citations, evidence_version_id=run.evidence_version_id
                ),
            )
        await finish_run(
            tx.session,
            run.id,
            status="completed",
            context_hash=context.sha256,
            output=output.model_dump(mode="json"),
        )
        shown_count = sum(1 for r in rows if r["shown"])
        tx.record(
            "upload_review.created",
            target=Target("evidence_version", run.evidence_version_id),
            after=Ref(agent_run_id=run.id, shown=shown_count, hidden=len(rows) - shown_count),
        )
        # P-06-T20: the screening aggregates of its request batches recompose (code only).
        tx.emit(
            UploadReviewRecorded(
                engagement_id=agent.engagement, evidence_version_id=run.evidence_version_id
            )
        )
        tx.emit(ProposalRecorded(engagement_id=agent.engagement, source="upload_review"))
    return ReviewOutcome(run.id, "completed", shown_count, len(rows) - shown_count)
