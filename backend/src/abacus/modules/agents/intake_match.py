"""The matcher's intake mode (N-01-T22; N-01 §6; `evidence.matcher` v3). PROTECTED.

For one intake attachment of a matched client, the matcher says what the document is (form family,
tax year, issuer, kind) and proposes up to three of that client's destinations. Code assembles
everything it reads (ADR-051):

- the attachment's masked pages only (P-03: every detected identifier replaced, then the TIN
  scrub; nothing until the PII scan ran), its file name and the channel it came by. The pages and
  the file name are the client's words, given as untrusted blocks (ADR-052, ADR-064);
- the matched client's own destinations only, as D1..Dn: open requests on its engagements, the
  permanent file and each work item's folder, read for the relationship partner the run acts for
  (their walls apply; another client's destinations never reach the context, INV-3). An
  engagement with AI turned off contributes none (the gateway's engagement check needs an
  engagement; an intake run has none, so code drops them here);
- when the client holds a tax return, its TRI data subjects (entity, tax year), so C19's
  condition 6 refuses the call unless both §7216 consents are in force (fail closed, audited,
  never retried).

Gates before a run: `matching.firm_intake`, a real model route, a client on the attachment, a
relationship partner who is an active member, masked pages, at least one destination, and the
firm's daily cap for intake runs. The gateway then applies the data boundary (opt-in, clearance,
stage) as for every agent.

Code maps references back (an unknown one or a repeat is discarded), verifies every quote against
the masked pages (a proposal without a verified quote, or under the spec's confidence, is kept
hidden), and records the run, its proposals and the classification (`proposed_by_kind = agent`).
Nothing is filed, ignored, held or superseded here: those stay a person's (I-AGENT-NEVER).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Final
from uuid import UUID

from abacus.ai_gateway import (
    AssembledContext,
    Attribution,
    ContextBuilder,
    DataSubject,
    GatewayCall,
    call,
    sanitise_text,
)
from abacus.kernel import _flags
from abacus.kernel.config import settings
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.document_citations import verify
from abacus.modules.agents.events import IntakeProposalsRecorded
from abacus.modules.agents.handoff import (
    DocumentCitation,
    IntakeMatchOutput,
    VerifiedDocumentCitation,
)
from abacus.modules.agents.inbox_match import MATCHER, model_available
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
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.agents.upload_review import TERMINAL
from abacus.modules.communications.api import (
    IntakeAttachmentFacts,
    intake_attachment_facts,
    intake_folder_destinations,
)
from abacus.modules.engagements.api import ai_excluded, client_tri_subjects, work_item_index
from abacus.modules.evidence.api import intake_masked_text, record_agent_classification
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    is_active_member,
)
from abacus.modules.organisations.api import client_partner_of
from abacus.modules.requests.api import request_items_for

INTAKE_MODE: Final = "intake"
MAX_DESTINATIONS: Final = 60  # D1..D60 (handoff.DestinationRef)
# A request still takes a document in these states (requests' own rule for what evidence fulfils).
_TAKES_EVIDENCE: Final = frozenset({"draft", "requested", "uploaded", "returned"})
# Attachments a person has not decided yet; a filed, ignored, held or withdrawn one isn't matched.
_UNDECIDED: Final = frozenset({"new", "waiting"})
_CHANNEL: Final = {"mailbox": "email", "portal": "the client portal", "staff": "logged by staff"}
_KIND_WORD: Final = {
    "request": "open request",
    "permanent_file": "permanent file",
    "work_item_folder": "work item folder",
}


@dataclass(frozen=True)
class Destination:
    kind: str  # INB-02's picker kind: request, permanent_file, work_item_folder, ...
    id: UUID  # the picker's id: the request item, the client, the work item, ...
    label: str


@dataclass(frozen=True)
class IntakeOutcome:
    run_id: UUID
    status: str  # completed | escalated
    none_fit: bool
    shown: tuple[tuple[str, UUID], ...]  # (kind, id) of the destinations shown, best first
    hidden: int


def refs(destinations: tuple[Destination, ...]) -> dict[str, Destination]:
    """D1..Dn in the order given."""
    return {f"D{n}": d for n, d in enumerate(destinations, start=1)}


async def intake_destinations(partner: AuthContext, client_id: UUID) -> tuple[Destination, ...]:
    """The client's destinations the partner may file to: open requests on its engagements, then
    the permanent file and work-item folders; none in an engagement with AI turned off."""
    items = work_item_index()
    async with tenant_session(partner.tenant) as session:
        rows = (
            await session.execute(
                items.select()
                .with_only_columns(items.c.id, items.c.engagement_id)
                .where(items.c.client_id == client_id)
            )
        ).all()
    engagement_of = {r.id: r.engagement_id for r in rows}
    engagements = sorted({r.engagement_id for r in rows if r.engagement_id is not None})
    excluded = {e for e in engagements if await ai_excluded(partner.tenant, e)}
    found: list[Destination] = []
    for engagement_id in engagements:
        if engagement_id in excluded:
            continue
        try:
            requests = await request_items_for(partner, engagement_id)
        except (Forbidden, NotFound):
            continue  # walled off, or not theirs to see: none of its requests is offered
        found.extend(
            Destination("request", r.id, r.description)
            for r in requests
            if r.status in _TAKES_EVIDENCE
        )
    try:
        folders = await intake_folder_destinations(partner, client_id)
    except (Forbidden, NotFound):
        folders = []  # the partner may not triage this client: no folder is theirs to offer
    for folder in folders:
        if folder.kind == "work_item_folder" and engagement_of.get(folder.id) in excluded:
            continue
        found.append(Destination(folder.kind, folder.id, folder.label))
    return tuple(found[:MAX_DESTINATIONS])


async def create_intake_match_run(
    tenant_id: UUID, attachment_id: UUID, client_id: UUID, source_event_id: UUID
) -> UUID | None:
    """The intake run for this attachment and event, on behalf of the client's relationship
    partner; None when a gate is closed (the flag, a model route, a matched and undecided
    attachment, an active partner, masked pages, the daily cap: audited)."""
    matcher = spec(MATCHER)
    reader = _reader(tenant_id, f"agents:{matcher.id}")
    if not await flag_enabled(reader, _flags.MATCHING_FIRM_INTAKE) or not model_available():
        return None
    facts = await intake_attachment_facts(reader, attachment_id)
    if facts is None or facts.client_id != client_id or facts.status not in _UNDECIDED:
        return None
    partner = await client_partner_of(reader, client_id)
    if not isinstance(partner, UUID) or not await is_active_member(tenant_id, partner):
        return None  # no one to act for: the matcher never acts as itself
    pages = await intake_masked_text(reader, attachment_id)
    if not pages:
        return None  # not scanned yet, or nothing readable (fail closed)
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            if await run_for_event(tx.session, matcher.id, source_event_id) is None and (
                await runs_since(tx.session, matcher.id, None, _today())
                >= settings().screening_daily_cap
            ):
                tx.record(
                    "action_cap.refused",
                    target=Target("client", client_id),
                    after=Ref(inbox_attachment_id=attachment_id),
                )
                return None
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=matcher.id,
                shadow=await starts_in_shadow(tx.session, reader, matcher.id),
                spec_version=matcher.version,
                engagement_id=None,
                evidence_version_id=None,
                initiator_user_id=partner,
                source_event_id=source_event_id,
                task_scope=sorted(matcher.task_scope),
                inbox_attachment_id=attachment_id,
            )
            if run_id is None:
                existing = await run_for_event(tx.session, matcher.id, source_event_id)
                run_id = existing.id if existing is not None else None
            else:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(inbox_attachment_id=attachment_id, initiator=partner),
                )
    except MissingAuditEvent:
        pass  # the run already existed
    return run_id


def build_intake_context(
    facts: IntakeAttachmentFacts,
    destinations: tuple[Destination, ...],
    pages: dict[int, str],
    subjects: tuple[DataSubject, ...],
    untrusted: list[str],
) -> AssembledContext:
    """The fixed layers (ADR-051). Destination labels are the firm's own words; the file name
    and the pages are the client's, the only untrusted fields; the pages trim first."""
    return (
        ContextBuilder()
        .subjects(*subjects)
        .text("firm", f"The document arrived by {_CHANNEL.get(facts.channel, 'email')}.")
        .task(
            {
                "destinations": [
                    {"ref": ref, "kind": _KIND_WORD.get(d.kind, d.kind), "label": d.label}
                    for ref, d in refs(destinations).items()
                ],
                "file_name": facts.file_name,
                "document": [f"Page {n}:\n{text}" for n, text in sorted(pages.items())],
            },
            untrusted=[*untrusted, "file_name"],
            trim="document",
        )
        .build()
    )


def _citation(c: VerifiedDocumentCitation) -> dict[str, object]:
    found = asdict(c)
    found["quote"] = sanitise_text(c.quote)
    return found


async def match_intake(agent: AgentContext, attachment_id: UUID) -> IntakeOutcome:
    """The run's proposals; a terminal error ends the run as failed with its code."""
    try:
        return await _match_intake(agent, attachment_id)
    except tuple(TERMINAL) as exc:
        code = next(c for kind, c in TERMINAL.items() if isinstance(exc, kind))
        await fail_run(agent.tenant_id, agent.agent_run_id, code)
        raise


async def _match_intake(agent: AgentContext, attachment_id: UUID) -> IntakeOutcome:
    run = await _run(agent)
    matcher = spec(run.agent_id)
    facts = await intake_attachment_facts(agent.tenant, attachment_id)
    if facts is None or facts.client_id is None or facts.status not in _UNDECIDED:
        raise NotFound("inbox_attachment")
    client_id = facts.client_id
    await authorise(agent, "inbox_match.run", Resource.client(agent.tenant_id, client_id))
    destinations = await intake_destinations(agent.initiator, client_id)
    pages = await intake_masked_text(agent.tenant, attachment_id)
    if not destinations or not pages:
        raise NotFound("inbox_attachment")
    subjects = await client_tri_subjects(agent.tenant, client_id)
    context = build_intake_context(
        facts, destinations, pages, subjects, list(matcher.untrusted_inputs)
    )
    result = await call(
        GatewayCall(
            purpose=matcher.purpose,
            prompt=matcher.prompt,
            tier=matcher.tier,
            output_schema=IntakeMatchOutput,
            budget_usd=matcher.limits.max_cost_usd,
            attribution=Attribution(agent.tenant, None, run.agent_id, run.id),
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
        return IntakeOutcome(run.id, "escalated", False, (), 0)
    output = result.output
    known = refs(destinations)
    threshold = matcher.confidence_routing.below
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, UUID]] = set()
    for proposal in output.proposals:
        target = known.get(proposal.destination)
        if target is None or (target.kind, target.id) in seen:
            continue  # a reference it wasn't given, or a repeat: discarded
        seen.add((target.kind, target.id))
        checked = verify(
            [DocumentCitation(page=c.page, quote=c.quote) for c in proposal.citations], pages, {}
        )
        confidence = Decimal(str(proposal.confidence))
        rows.append(
            {
                "tenant_id": agent.tenant_id,
                "rank": len(rows) + 1,
                "request_item_id": target.id if target.kind == "request" else None,
                "inbox_attachment_id": attachment_id,
                "destination_kind": target.kind,
                "destination_id": target.id,
                "confidence": confidence.quantize(Decimal("0.001")),
                "rationale": sanitise_text(proposal.rationale)[:300] or "(no rationale)",
                "citations": [_citation(c) for c in checked],
                "shown": any(c.verified for c in checked) and confidence >= threshold,
            }
        )
    found = output.classification
    async with uow(agent.tenant) as tx:
        locked = await lock_run(tx.session, run.id)
        if locked is None or locked.status != "running":
            raise AgentRunNotRunning(locked.status if locked else "missing")
        await authorise(agent, "inbox_match.run", Resource.client(agent.tenant_id, client_id))
        match_id = await insert_inbox_match(
            tx.session,
            values={
                "tenant_id": agent.tenant_id,
                "engagement_id": None,
                "inbox_file_id": None,
                "inbox_attachment_id": attachment_id,
                "client_id": client_id,
                "agent_run_id": run.id,
                "prompt_ref": matcher.prompt,
                "none_fit": output.none_fit,
                "truncated": bool(context.truncated),
            },
        )
        await insert_match_proposals(tx.session, [{**r, "match_id": match_id} for r in rows])
        tx.emit(
            IntakeProposalsRecorded(
                attachment_id=attachment_id, client_id=client_id, match_id=match_id
            )
        )
        await record_agent_classification(
            tx,
            tenant_id=agent.tenant_id,
            attachment_id=attachment_id,
            agent_run_id=run.id,
            prompt_ref=matcher.prompt,
            form_family=(found.form_family or "unknown").strip() or "unknown",
            kind=found.kind,
            page_count=len(pages),
            tax_year=found.tax_year,
            issuer_name=sanitise_text(found.issuer) if found.issuer else None,
            confidence=found.confidence,
        )
        await finish_run(
            tx.session,
            run.id,
            status="completed",
            context_hash=context.sha256,
            output=output.model_dump(mode="json"),
        )
        shown = tuple(
            (str(r["destination_kind"]), r["destination_id"]) for r in rows if r["shown"]
        )
        tx.record(
            "inbox_match.created",
            target=Target("inbox_attachment", attachment_id),
            after=Ref(
                agent_run_id=run.id,
                shown=len(shown),
                hidden=len(rows) - len(shown),
                none_fit=int(output.none_fit),
            ),
        )
    return IntakeOutcome(
        run.id,
        "completed",
        output.none_fit,
        tuple((kind, UUID(str(i))) for kind, i in shown),
        len(rows) - len(shown),
    )
