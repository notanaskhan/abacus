"""The notices responder (N-04-T19; N-04 §6; DEC-2313). PROTECTED.

`analyze`: one gateway call with code's rows, checks and options, and the cited text as untrusted.
Code checks the answer before anything is shown: every number is a code fact (a miss rejects the
narrative), every citation is one the context listed and verified, the recommendation is one of the
options, and no text claims a person's act. Below 0.6 confidence the recommendation is hidden.

The gateway enforces the gates it owns, in order: the kill switch, provider terms, budgets and
condition 6: `consent_7216` use and AI disclosure for every taxpayer (`data_subjects`); a subject
the builder can't name is refused (fail closed). The firm's stage is read here first (the
`notices.responder` flag retired at N-04-T27, DEC-2602): `off` makes no call, `shadow` records and
shows nothing.

It never creates a notice, confirms a field, decides, signs, drafts a letter or sends (INV-1).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Final, cast
from uuid import UUID, uuid4

from abacus.ai_gateway import (
    AssembledContext,
    Attribution,
    ContextBuilder,
    GatewayCall,
    ModelRequest,
    call,
)
from abacus.ai_gateway.context import DataSubject
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.handoff import NoticeAnalyzeOutput, NoticeExtractOutput
from abacus.modules.agents.repository import finish_run, insert_run
from abacus.modules.agents.service import (
    _reader,  # pyright: ignore[reportPrivateUsage] -- the module's own system reader
    fail_run,
    load_agent_context,
)
from abacus.modules.agents.spec import spec
from abacus.modules.agents.stages import stage_for

RESPONDER: Final = "notices.responder"
HIDE_BELOW: Final = 0.6
_NUMBER: Final = re.compile(r"\d[\d,]*(?:\.\d+)?")
_NOT_FIGURES: Final = re.compile(
    r"\b[A-Z]{2,}\d*(?:-[A-Z0-9]+)*\b|\bD\d+:p\d+\b|\bForm \d+\b|\b1099(?:-[A-Z]+)?\b|"
    r"\b(?:19|20)\d{2}\b"
)
_ACT: Final = re.compile(r"\b(?:approved|decided|agreed to|signed|sent to the)\b", re.I)
_LINK: Final = re.compile(r"https?://|www\.", re.I)
NOT_IN_OPTIONS: Final = "recommendation_not_in_options"
NO_PROVENANCE: Final = "number_without_provenance"
BAD_CITATION: Final = "citation_unknown"
CLAIMED_ACT: Final = "claims_a_persons_act"
HAS_LINK: Final = "link_in_text"
JsonRow = dict[str, Any]  # Any: code's facts as JSON


@dataclass(frozen=True)
class AnalyzeFacts:
    """What code computed (`notices.analysis`), and the verified citation handles."""

    rows: tuple[JsonRow, ...]
    checks: tuple[JsonRow, ...]
    information_returns: tuple[JsonRow, ...]
    options: tuple[str, ...]
    lines: tuple[tuple[str, str], ...]  # (handle, the cited text: untrusted)


@dataclass(frozen=True)
class AnalyzeResult:
    stage: str  # off, shadow, live, refused
    run_id: UUID | None
    recommended: str | None
    answer: NoticeAnalyzeOutput | None


def figures_of(facts: AnalyzeFacts) -> frozenset[Decimal]:
    found: set[Decimal] = set()

    def add(value: object) -> None:
        try:
            found.add(Decimal(str(value)).normalize())
        except InvalidOperation:
            return

    for row in (*facts.rows, *facts.information_returns):
        for value in row.values():
            add(value)
    return frozenset(found)


def numbers_in(text: str) -> set[Decimal]:
    out: set[Decimal] = set()
    for raw in _NUMBER.findall(_NOT_FIGURES.sub(" ", unicodedata.normalize("NFKC", text))):
        try:
            out.add(Decimal(raw.replace(",", "")).normalize())
        except InvalidOperation:
            continue
    return out


def check(answer: NoticeAnalyzeOutput, facts: AnalyzeFacts) -> str | None:
    """None when code accepts the answer; else why it is never shown (the run's reason)."""
    if answer.recommended_option not in facts.options:
        return NOT_IN_OPTIONS
    known = {handle for handle, _ in facts.lines}
    figures = figures_of(facts)
    texts = [*(p.text for p in answer.why_surfaced), answer.proposed_action]
    for paragraph in answer.why_surfaced:
        if not paragraph.citations or not set(paragraph.citations) <= known:
            return BAD_CITATION
    for text in texts:
        if not numbers_in(text) <= figures:
            return NO_PROVENANCE
        if _ACT.search(text):
            return CLAIMED_ACT
        if _LINK.search(text):
            return HAS_LINK
    return None


def build_context(facts: AnalyzeFacts, subjects: Sequence[DataSubject]) -> AssembledContext:
    return (
        ContextBuilder()
        .task(
            {
                "rows": list(facts.rows),
                "checks": list(facts.checks),
                "information_returns": list(facts.information_returns),
                "options": list(facts.options),
                "lines": [{"ref": h, "text": t} for h, t in facts.lines],
            },
            untrusted=["lines"],
        )
        .subjects(*subjects)
        .build()
    )


async def _start(tenant_id: UUID, engagement_id: UUID, initiator: UUID) -> UUID | None:
    responder = spec(RESPONDER)
    reader = _reader(tenant_id, f"agents:{responder.id}")
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            run_id = await insert_run(
                tx.session,
                tenant_id=tenant_id,
                agent_id=responder.id,
                shadow=await stage_for(reader, responder.id) == "shadow",
                spec_version=responder.version,
                engagement_id=engagement_id,
                evidence_version_id=None,
                initiator_user_id=initiator,
                source_event_id=uuid4(),
                task_scope=sorted(responder.task_scope),
            )
            if run_id is not None:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(initiator=initiator),
                )
    except MissingAuditEvent:
        pass
    return run_id


async def analyze(
    tenant: TenantContext,
    *,
    engagement_id: UUID,
    initiator: UUID,
    facts: AnalyzeFacts,
    subjects: Sequence[DataSubject],
) -> AnalyzeResult:
    """Fails closed at each step: no stage, no model, a refused answer: no recommendation,
    and the code analysis stands alone ("Analysis by code only")."""
    stage = await stage_for(tenant, RESPONDER)
    if stage not in ("shadow", "live"):
        return AnalyzeResult("off", None, None, None)
    run_id = await _start(tenant.tenant_id, engagement_id, initiator)
    if run_id is None:
        return AnalyzeResult("refused", None, None, None)
    agent = await load_agent_context(tenant.tenant_id, run_id)
    responder = spec(RESPONDER)
    context = build_context(facts, subjects)
    try:
        result = await call(
            GatewayCall(
                purpose=responder.purpose,
                prompt=responder.prompt,
                tier=responder.tier,
                output_schema=NoticeAnalyzeOutput,
                budget_usd=responder.limits.max_cost_usd,
                attribution=Attribution(agent.tenant, engagement_id, RESPONDER, run_id),
                context=context,
                work_class=responder.work_class,
                essential=responder.essential,
                routes=responder.routes,
                cheaper_tiers=responder.cheaper_tiers,
                max_output_tokens=responder.limits.max_output_tokens,
                timeout_seconds=responder.limits.max_seconds,
            )
        )
    except Exception:  # a refused gateway call (consent, terms, budget) shows no recommendation
        await fail_run(tenant.tenant_id, run_id, "gateway_error")
        return AnalyzeResult("refused", run_id, None, None)
    answer = result.output
    reason = NOT_IN_OPTIONS if answer is None else check(answer, facts)
    if answer is None or reason is not None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session,
                run_id,
                status="escalated",
                context_hash=context.sha256,
                output={"refused": reason},
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run_id))
        return AnalyzeResult("refused", run_id, None, None)
    async with uow(agent.tenant) as tx:
        if await finish_run(
            tx.session,
            run_id,
            status="completed",
            context_hash=context.sha256,
            output=answer.model_dump(mode="json"),
        ):
            tx.record("agent_run.completed", target=Target("agent_run", run_id))
    recommended = answer.recommended_option if answer.confidence >= HIDE_BELOW else None
    return AnalyzeResult(stage, run_id, recommended, answer)


@dataclass(frozen=True)
class ExtractProposal:
    """The fields and the run they came from: an agent's value names its run (0650's CHECK).
    `notices.intake_read` records them as proposals a person confirms."""

    output: NoticeExtractOutput
    run_id: UUID


async def extract_fields(
    tenant: TenantContext,
    *,
    engagement_id: UUID | None,
    initiator: UUID,
    keys: Sequence[str],
    lines: Sequence[tuple[str, str]],
    subjects: Sequence[DataSubject],
) -> ExtractProposal | None:
    """Field proposals for a notice with no code map; a citation outside `lines` drops its
    field."""
    if await stage_for(tenant, RESPONDER) not in ("shadow", "live"):
        return None
    run_id = await _start(tenant.tenant_id, cast(UUID, engagement_id), initiator)
    if run_id is None:
        return None
    agent = await load_agent_context(tenant.tenant_id, run_id)
    responder = spec(RESPONDER)
    mode = responder.modes["extract"]
    context = (
        ContextBuilder()
        .task(
            {"keys": list(keys), "lines": [{"ref": h, "text": t} for h, t in lines]},
            untrusted=["lines"],
        )
        .subjects(*subjects)
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=responder.purpose,
                prompt=mode.prompt,
                tier="small",
                output_schema=NoticeExtractOutput,
                budget_usd=mode.max_cost_usd,
                attribution=Attribution(agent.tenant, engagement_id, RESPONDER, run_id),
                context=context,
                work_class=responder.work_class,
                essential=responder.essential,
                routes=responder.routes,
                cheaper_tiers=responder.cheaper_tiers,
                max_output_tokens=responder.limits.max_output_tokens,
                timeout_seconds=60,
            )
        )
    except Exception:
        await fail_run(tenant.tenant_id, run_id, "gateway_error")
        return None
    answer = result.output
    if answer is None:
        await fail_run(tenant.tenant_id, run_id, "no_output")
        return None
    known, allowed = {h for h, _ in lines}, set(keys)
    kept = [f for f in answer.fields if f.citation in known and f.field_key in allowed]
    async with uow(agent.tenant) as tx:
        if await finish_run(
            tx.session,
            run_id,
            status="completed",
            context_hash=context.sha256,
            output={"fields": len(kept)},
        ):
            tx.record("agent_run.completed", target=Target("agent_run", run_id))
    return ExtractProposal(NoticeExtractOutput(fields=kept), run_id)


def _task(request: ModelRequest) -> Mapping[str, Any]:  # Any: JSON
    return cast(
        Mapping[str, Any],  # Any: JSON
        json.loads(request.user.split("## task\n", 1)[1].split("\n", 1)[0]),
    )


def fake_analyze(request: ModelRequest) -> str:
    """The fake model's answer, read from the task by code (local runs and tests only)."""
    task = _task(request)
    handles = [line["ref"] for line in task["lines"]] or ["none"]
    return json.dumps(
        {
            "why_surfaced": [
                {"text": "The notice proposes a change the rows below show.", "citations": handles}
            ],
            "proposed_action": "Review the comparison with the signer.",
            "recommended_option": task["options"][0],
            "confidence": 0.9,
        }
    )


def fake_extract(request: ModelRequest) -> str:
    task = _task(request)
    return (
        json.dumps({"fields": []})
        if not task["lines"]
        else json.dumps(
            {
                "fields": [
                    {
                        "field_key": task["keys"][0],
                        "value": task["lines"][0]["text"][:40],
                        "confidence": 0.8,
                        "citation": task["lines"][0]["ref"],
                    }
                ]
            }
        )
    )
