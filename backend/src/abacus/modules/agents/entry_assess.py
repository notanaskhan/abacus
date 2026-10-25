"""The entry assessor (SPEC-037 Q4; TASK-085). PROTECTED.

For one selected journal entry, the agent reads the entry and up to three documents a person tied
to it (D1: linked on its result, or fulfilling its support request; never a search) and proposes
whether they support it. Code builds the context (ADR-051: entry and documents delimited as
untrusted, ADR-052), verifies every citation against the stored extraction, and checks every
amount quote holds the entry's amount (ADR-050: the model never compares figures). An `explained`
is shown only with a verified amount quote and a verified party quote and no unverified citation;
otherwise it's shown as `unclear`. People record every result (ADR-005).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
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
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.document_citations import verify
from abacus.modules.agents.handoff import DocumentCitation, EntryAssessment, EntryCitation
from abacus.modules.agents.repository import (
    finish_run,
    insert_entry_assessment,
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
from abacus.modules.agents.spec import AgentSpec, spec
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.agents.upload_review import TERMINAL, document_blocks
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.evidence.api import ReviewMaterial, review_material
from abacus.modules.fieldwork.api import EntryFacts, entry_facts
from abacus.modules.identity.api import (
    AgentContext,
    acts_for_offshore,
    authorise,
    is_active_member,
)

ASSESSOR = "fieldwork.entry_assessor"
_NUMBER: Final = re.compile(r"\(?-?[$€£]?\s?\d[\d,]*(?:\.\d+)?\)?")


@dataclass(frozen=True)
class AssessOutcome:
    run_id: UUID
    status: str  # completed | escalated
    verdict: str | None  # the verdict shown


@dataclass(frozen=True)
class CheckedCitation:
    document: str
    claim: str
    page: int | None
    sheet: str | None
    cell: str | None
    quote: str
    verified: bool  # the quote is in the document, where it says
    reason: str | None
    amount_matches: bool | None = None  # an amount quote: it holds the entry's amount (code)


def model_available() -> bool:
    return any(route_enabled(r) for r in spec(ASSESSOR).routes)


def shows_amount(quote: str, amount: Decimal) -> bool:
    """Code's check (ADR-050): a number in the quote equals the entry's amount, written with or
    without separators, a currency sign or accounting parentheses."""
    for found in _NUMBER.findall(quote):
        digits = re.sub(r"[^\d.]", "", found)
        try:
            if digits and Decimal(digits) == abs(amount):
                return True
        except InvalidOperation:
            continue
    return False


def build_context(
    entry: EntryFacts, documents: Sequence[ReviewMaterial], untrusted: list[str]
) -> AssembledContext:
    blocks: list[str] = []
    for n, material in enumerate(documents, start=1):
        blocks += [f"D{n}, {block}" for block in document_blocks(material)]
    return (
        ContextBuilder()
        .task(
            {
                "entry": {
                    "date": entry.posted_on,
                    "type": entry.kind or "not given",
                    "reference": entry.reference or "not given",
                    "name": entry.counterparty or "not given",
                    "accounts": list(entry.accounts),
                    "amount": f"{entry.amount:,.2f}",
                    "descriptions": list(entry.descriptions),
                },
                "documents": blocks,
            },
            untrusted=untrusted,
            trim="documents",
        )
        .build()
    )


def check(
    output: EntryAssessment, entry: EntryFacts, documents: Sequence[ReviewMaterial]
) -> tuple[str, list[CheckedCitation]]:
    """The verdict to show and each citation with code's verification."""
    checked: list[CheckedCitation] = []
    for c in output.citations:
        index = int(c.document[1:]) - 1
        if index >= len(documents):
            checked.append(_checked(c, False, "no_such_document"))
            continue
        material = documents[index]
        [v] = verify([_as_document(c)], material.pages, material.sheets)
        matches = shows_amount(c.quote, entry.amount) if c.claim == "amount" else None
        checked.append(_checked(c, v.verified, v.reason, matches))
    shown = output.verdict
    if shown == "explained" and not (
        all(c.verified for c in checked)
        and any(c.claim == "party" for c in checked)
        and any(c.claim == "amount" and c.amount_matches for c in checked)
    ):
        shown = "unclear"  # code couldn't confirm it: never shown as explained
    return shown, checked


def _as_document(c: EntryCitation) -> DocumentCitation:
    return DocumentCitation(page=c.page, sheet=c.sheet, cell=c.cell, quote=c.quote)


def _checked(
    c: EntryCitation, verified: bool, reason: str | None, amount_matches: bool | None = None
) -> CheckedCitation:
    return CheckedCitation(
        c.document,
        c.claim,
        c.page,
        c.sheet,
        c.cell,
        sanitise_text(c.quote),
        verified,
        reason,
        amount_matches,
    )


async def materials(
    tenant: TenantContext, entry: EntryFacts, *, masked: bool = False
) -> list[ReviewMaterial]:
    """The entry's documents that have an extraction, in order (unreadable ones are skipped).
    `masked` (the run acts for an offshore member; DEC-52, TASK-1207 review): only their masked
    text, and a document not yet scanned for PII is skipped."""
    found: list[ReviewMaterial] = []
    for version_id in entry.evidence_version_ids:
        material = await review_material(tenant, version_id, masked=masked)
        if material is not None and material.extraction_status == "extracted":
            found.append(material)
    return found


async def ask(
    assessor: AgentSpec,
    attribution: Attribution,
    entry: EntryFacts,
    documents: Sequence[ReviewMaterial],
) -> tuple[EntryAssessment | None, AssembledContext]:
    """One model call through the gateway (the product run and the evaluation share it)."""
    context = build_context(entry, documents, list(assessor.untrusted_inputs))
    result = await call(
        GatewayCall(
            purpose=assessor.purpose,
            prompt=assessor.prompt,
            tier=assessor.tier,
            output_schema=EntryAssessment,
            budget_usd=assessor.limits.max_cost_usd,
            attribution=attribution,
            context=context,
            work_class=assessor.work_class,
            essential=assessor.essential,
            routes=assessor.routes,
            cheaper_tiers=assessor.cheaper_tiers,
            max_output_tokens=assessor.limits.max_output_tokens,
            timeout_seconds=assessor.limits.max_seconds,
        )
    )
    return result.output, context


async def create_assess_run(
    tenant_id: UUID,
    engagement_id: UUID,
    item_id: UUID,
    source_event_id: UUID,
    requested_by: UUID | None,
) -> UUID | None:
    """The assessor's run for this entry, once per event, on behalf of `requested_by`. None
    without a person, a real route, a document to read, or over the daily cap (audited)."""
    if requested_by is None or not await is_active_member(tenant_id, requested_by):
        return None
    if not model_available():
        return None
    assessor = spec(ASSESSOR)
    reader = _reader(tenant_id, f"agents:{assessor.id}")
    entry = await entry_facts(reader, item_id)
    if entry is None or entry.engagement_id != engagement_id or not entry.evidence_version_ids:
        return None
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            if await run_for_event(tx.session, assessor.id, source_event_id) is None and (
                await runs_since(tx.session, assessor.id, engagement_id, _today())
                >= settings().screening_daily_cap
            ):
                tx.record(
                    "action_cap.refused",
                    target=Target("engagement", engagement_id),
                    after=Ref(selected_item_id=item_id),
                )
                return None
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=assessor.id,
                shadow=await starts_in_shadow(tx.session, reader, assessor.id),  # SPEC-036
                spec_version=assessor.version,
                engagement_id=engagement_id,
                evidence_version_id=None,
                initiator_user_id=requested_by,
                source_event_id=source_event_id,
                task_scope=sorted(assessor.task_scope),
            )
            if run_id is None:
                existing = await run_for_event(tx.session, assessor.id, source_event_id)
                run_id = existing.id if existing is not None else None
            else:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(selected_item_id=item_id, initiator=requested_by),
                )
    except MissingAuditEvent:
        pass
    return run_id


async def assess(agent: AgentContext, item_id: UUID) -> AssessOutcome:
    """The run's assessment; a terminal error ends the run as failed with its code."""
    try:
        return await _assess(agent, item_id)
    except tuple(TERMINAL) as exc:
        code = next(c for kind, c in TERMINAL.items() if isinstance(exc, kind))
        await fail_run(agent.tenant_id, agent.agent_run_id, code)
        raise


async def _assess(agent: AgentContext, item_id: UUID) -> AssessOutcome:
    run = await _run(agent)
    assessor = spec(run.agent_id)
    engagement = await get_ref(agent, agent.engagement)
    await authorise(agent, "procedure.read", engagement.resource())
    await authorise(agent, "evidence.read", engagement.resource())
    entry = await entry_facts(agent.tenant, item_id)
    if entry is None or entry.engagement_id != agent.engagement:
        raise NotFound("selected_item")
    documents = await materials(agent.tenant, entry, masked=await acts_for_offshore(agent))
    if not documents:
        raise NotFound("upload_extraction")
    output, context = await ask(
        assessor,
        Attribution(agent.tenant, agent.engagement, run.agent_id, run.id),
        entry,
        documents,
    )
    if output is None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session, run.id, status="escalated", context_hash=context.sha256
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run.id))
        return AssessOutcome(run.id, "escalated", None)
    shown, checked = check(output, entry, documents)
    async with uow(agent.tenant) as tx:
        locked = await lock_run(tx.session, run.id)
        if locked is None or locked.status != "running":
            raise AgentRunNotRunning(locked.status if locked else "missing")
        locked_engagement = await lock_ref(tx, agent.engagement)
        await authorise(agent, "entry_assessment.run", locked_engagement.resource())
        await insert_entry_assessment(
            tx.session,
            tenant_id=agent.tenant_id,
            engagement_id=agent.engagement,
            selected_item_id=item_id,
            agent_run_id=run.id,
            prompt_ref=assessor.prompt,
            verdict=output.verdict,
            shown_verdict=shown,
            rationale=sanitise_text(output.rationale)[:400] or "(no rationale)",
            citations=[asdict(c) for c in checked],
        )
        await finish_run(
            tx.session,
            run.id,
            status="completed",
            context_hash=context.sha256,
            output=output.model_dump(mode="json"),
        )
        tx.record(
            "entry_assessment.created",
            target=Target("selected_item", item_id),
            after=Ref(agent_run_id=run.id),
        )
    return AssessOutcome(run.id, "completed", shown)
