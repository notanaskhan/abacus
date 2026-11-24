"""`assurance.post_issuance_analysis` v1 (Q-05-T22; TASK-8909; Q-05 §6; SPEC-711 AC-15, AC-16;
ADR-005, ADR-050, ADR-052, P-24; red).

A person asks for the analysis of a compared post-issuance case (`POST …/post-issuance/{case}/
analysis`, `post_issuance.analyse`). Code drives one model call (spec v2 `single_call`, prompt
`audit.post_issuance_analysis@v1`) on the capability's run row, attributed "<person> via Agent":

- **What the model sees.** Code's facts (the total difference, clearly trivial, overall
  materiality, the share of it, each compared line's difference), code's options and the one code
  marks eligible, and both certifications' masked page text as untrusted input (the certified
  trust report the audit relied on and the corrected certification; ADR-052).
- **What code settles** (`settle`): the blocks are AgentBlocks over code's facts only (a free
  number, an unknown fact, markup or a claimed human act is refused); the recommendation, if any,
  is the option code marks eligible (`recommendation_not_eligible` otherwise); there are quotes
  from **both** certifications on offered pages (`citation_coverage`). Code then appends the
  closing sentences, so the analysis always ends "I have not decided whether this needs action."
  (AC-16) and carries the suite's not-decided sentence.
- **What lands.** Every quote is a `document_text` citation code verifies on its certification;
  an unverified quote escalates the run and nothing is kept. A verified analysis is written on the
  case (sealed blocks, the tagged option, the citation ids, the run id) past `archived_guard()`
  under the `post_issuance` kind. Nothing else changes: the engagement partner decides (INV-1).

There is no C17 read tool: the call uses no tools (`single_call`), code hands the model its
facts, and C17 refuses any tool whose action names `post` (TOOL-001, `post_issuance.read`).

Synthetic firms only until the capability's Bedrock rerun is recorded in
`evals/post_issuance_analysis/clearance.yaml` (`client_data: none`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.clock import system_now
from abacus.kernel.crypto import seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AgentContext, AuthContext

CAPABILITY: Final = "assurance.post_issuance_analysis"
PROMPT: Final = "audit.post_issuance_analysis@v1"
SUITE_NOT_DECIDED: Final = "This analysis decides nothing; the engagement partner decides."
FINAL: Final = "I have not decided whether this needs action."
_AAD: Final = "assurance.post_issuance_analysis"
_SOURCES: Final[tuple[Literal["certified", "corrected"], ...]] = ("certified", "corrected")
Option = Literal["no_action", "revise_and_reissue", "notify_users"]
Source = Literal["certified", "corrected"]
Int = classified("internal")
Conf = classified("confidential")


class OutputRefused(DomainConflict):
    """The analysis may not be shown: `facts.reason` names why (a code, never the text)."""

    code = "agent_output_refused"


class FactIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$"), Int]
    kind: Annotated[Literal["money", "percent", "count"], Int]
    value: Annotated[str, Field(max_length=40), Conf]
    basis: Annotated[str, Field(max_length=200), Int] = "code"


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Annotated[Source, Int]
    evidence_version_id: Annotated[UUID, Int]
    pages: Annotated[list[int], Field(min_length=1, max_length=40), Int]


class PostIssuanceAnalysisInput(BaseModel):
    """What the model sees; the certifications' text is untrusted (never instructions)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_ref: Annotated[str, Field(max_length=10), Int]
    facts: Annotated[list[FactIn], Field(min_length=1, max_length=60), Int]
    options: Annotated[list[Option], Field(min_length=1, max_length=3), Int]
    eligible: Annotated[Option | None, Int] = None
    disclosure_affected: Annotated[bool, Int] = False
    sources: Annotated[list[SourceIn], Field(min_length=2, max_length=2), Int]
    untrusted: Annotated[list[str], Field(max_length=80), Conf] = []


class QuoteOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Annotated[Source, Int]
    page: Annotated[int, Field(ge=1, le=5000), Int]
    quote: Annotated[str, Field(min_length=3, max_length=200), Conf]


class PostIssuanceAnalysisOutput(BaseModel):
    """The model's answer: AgentBlocks, at most one option (tagged only if code marks it
    eligible) and quotes from both certifications. There is no action field: the analysis takes
    none (reserved actions are absent by construction)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocks: Annotated[dict[str, object], Conf]
    recommendation: Annotated[Option | None, Int] = None
    quotes: Annotated[list[QuoteOut], Field(min_length=2, max_length=10), Int]


@dataclass(frozen=True)
class Settled:
    blocks: dict[str, object]  # with code's closing sentences appended
    recommendation: Option | None
    quotes: tuple[QuoteOut, ...]


def _closing() -> dict[str, object]:
    return {"kind": "p", "segments": [
        {"kind": "text", "text": f"{SUITE_NOT_DECIDED} {FINAL}"}]}  # fmt: skip


def settle(given: PostIssuanceAnalysisInput, answer: PostIssuanceAnalysisOutput) -> Settled:
    """Code settles the answer (module docstring) and appends the closing sentences."""
    from abacus.modules.agents.api import AgentFact, BlocksRejected, validate_blocks

    facts = {
        f.id: AgentFact(id=f.id, kind=f.kind, value=f.value, basis=f.basis) for f in given.facts
    }
    try:
        blocks = validate_blocks(answer.blocks, facts, frozenset())
    except BlocksRejected as rejected:
        raise OutputRefused(facts={"reason": rejected.code}) from None
    if answer.recommendation is not None and answer.recommendation != given.eligible:
        raise OutputRefused(facts={"reason": "recommendation_not_eligible"})
    pages = {s.source: set(s.pages) for s in given.sources}
    if {q.source for q in answer.quotes} != {"certified", "corrected"}:
        raise OutputRefused(facts={"reason": "citation_coverage"})
    if any(q.page not in pages.get(q.source, set()) for q in answer.quotes):
        raise OutputRefused(facts={"reason": "page_not_offered"})
    dump = getattr(blocks, "model_dump", None)
    shown = cast("dict[str, object]", dump(mode="json") if callable(dump) else answer.blocks)
    parts = [*cast("list[object]", shown.get("parts") or []), _closing()]
    return Settled({**shown, "parts": parts}, answer.recommendation, tuple(answer.quotes))


def facts_for(case: object) -> list[FactIn]:
    """Code's facts for a compared case (the evaluation and each line's difference)."""
    evaluation = getattr(case, "evaluation")  # noqa: B009 -- post_issuance.Case
    lines = getattr(case, "comparison")  # noqa: B009
    out = [
        FactIn(id="difference", kind="money", value=str(evaluation.total_difference)),
        FactIn(id="clearly_trivial", kind="money", value=str(evaluation.clearly_trivial)),
        FactIn(id="overall_materiality", kind="money", value=str(evaluation.overall_materiality)),
        FactIn(id="share_pct", kind="percent", value=str(evaluation.share_pct)),
        FactIn(id="lines", kind="count", value=str(len(lines))),
    ]
    out += [
        FactIn(id=f"line_{n}", kind="money", value=str(ln.difference), basis=ln.line_key[:180])
        for n, ln in enumerate(lines, start=1)
    ][:40]
    return out


# --- the run -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalysisRun:
    run_id: UUID
    started_at: datetime
    status: Literal["succeeded", "escalated", "shadow"]
    reason: str | None = None


_CERTIFIED_VERSION: Final = text(
    "SELECT evidence_version_id FROM ebp_trust_report_lines WHERE work_item_id = :w "
    "AND superseded_by IS NULL GROUP BY evidence_version_id ORDER BY count(*) DESC LIMIT 1"
)
_WRITE: Final = text(
    "UPDATE post_issuance_events SET analysis_run_id = :run, analysis_sealed = :sealed, "
    "analysis_recommendation = :rec, analysis_citation_ids = :cites "
    "WHERE id = :c AND status <> 'decided' RETURNING id"
)


async def _pages(ctx: AuthContext, version_id: UUID) -> dict[int, str]:
    from abacus.modules.evidence.api import masked_pages

    found = await masked_pages(ctx.tenant, evidence_version_id=version_id)
    return {} if found is None else dict(sorted(found.items()))


async def _answer(
    agent: AgentContext, given: PostIssuanceAnalysisInput
) -> PostIssuanceAnalysisOutput:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder().task(given.model_dump(mode="json"), untrusted=("untrusted",)).build()
    )
    result = await call(
        GatewayCall(
            purpose=spec.purpose,
            prompt=PROMPT,
            tier=spec.tier,
            output_schema=PostIssuanceAnalysisOutput,
            budget_usd=spec.limits.max_cost_usd,
            attribution=Attribution(
                agent.tenant, agent.engagement_id, CAPABILITY, agent.agent_run_id
            ),
            context=context,
            work_class=spec.work_class,
            essential=spec.essential,
            routes=spec.routes,
            cheaper_tiers=spec.cheaper_tiers,
            max_output_tokens=spec.limits.max_output_tokens,
            timeout_seconds=spec.limits.max_seconds,
        )
    )
    return cast(PostIssuanceAnalysisOutput, result.output)


async def analyse(ctx: AuthContext, work_item_id: UUID, case_id: UUID) -> AnalysisRun:
    """One analysis run on a compared case (synthetic firms only; 409 `comparison_unavailable`
    before code compared, 409 `agent_not_available` on a real firm)."""
    from abacus.ai_gateway import is_synthetic
    from abacus.modules.agents.api import (
        end_capability_run,
        start_capability_run,
        starts_in_shadow,
    )
    from abacus.modules.assurance import post_issuance as pi
    from abacus.modules.evidence.api import CitationAnchor, CitationClaim, record_citations

    found = await pi.require_comparison(ctx, work_item_id, case_id)
    if not await is_synthetic(ctx.tenant):
        raise AgentNotAvailable(facts={"capability": CAPABILITY})
    engagement_id = await pi.work_item_engagement(ctx.tenant, work_item_id)
    async with tenant_session(ctx.tenant) as session:
        certified = await session.scalar(_CERTIFIED_VERSION, {"w": work_item_id})
    corrected = found.source_evidence_version_id
    if certified is None or corrected is None or engagement_id is None:
        raise pi.ComparisonUnavailable(facts={"case_id": str(case_id)})
    texts = {"certified": await _pages(ctx, cast(UUID, certified)),
             "corrected": await _pages(ctx, corrected)}  # fmt: skip
    versions = {"certified": cast(UUID, certified), "corrected": corrected}
    if not texts["certified"] or not texts["corrected"]:
        raise pi.ComparisonUnavailable(facts={"reason": "certification_not_scanned"})
    given = PostIssuanceAnalysisInput(
        case_ref=found.ref,
        facts=facts_for(found),
        options=[cast(Option, o) for o in found.options],
        eligible=cast(Option | None, found.recommended),
        disclosure_affected=bool(found.evaluation and found.evaluation.disclosure_affected),
        sources=[
            SourceIn(source=s, evidence_version_id=versions[s], pages=sorted(texts[s])[:40])
            for s in _SOURCES
        ],
        untrusted=[
            f"{s} certification page {p}: {t}"[:4000]
            for s in _SOURCES
            for p, t in texts[s].items()
        ][:80],
    )
    started = system_now()
    agent = await start_capability_run(ctx, CAPABILITY, engagement_id)
    if agent is None:
        raise AgentNotAvailable(facts={"reason": "run_not_recorded"})
    async with tenant_session(agent.tenant) as session:
        shadow = bool(await starts_in_shadow(session, agent.tenant, CAPABILITY))
    try:
        settled = settle(given, await _answer(agent, given))
    except OutputRefused as refused:
        reason = str((refused.facts or {}).get("reason"))[:60]
        await end_capability_run(agent, status="escalated", output={"reason": reason})
        return AnalysisRun(agent.agent_run_id, started, "escalated", reason)
    except Exception:  # boundary, budget or schema refusal: nothing is shown
        await end_capability_run(agent, status="escalated", output={"reason": "gateway_refused"})
        return AnalysisRun(agent.agent_run_id, started, "escalated", "gateway_refused")
    claims = [
        CitationClaim("document_text",
                      {"evidence_version_id": str(versions[q.source]), "page": q.page},
                      quote=q.quote)
        for q in settled.quotes
    ]  # fmt: skip
    anchor = CitationAnchor(pi.TARGET, case_id, "analysis", None, engagement_id,
                            work_item_id=work_item_id)  # fmt: skip
    async with uow(agent.tenant) as tx:
        recorded = await record_citations(
            tx, actor=agent, anchor=anchor, claims=claims, shadow=shadow
        )
    if len(recorded) != len(claims) or not all(r.verified for r in recorded):
        await end_capability_run(
            agent, status="escalated", output={"reason": "citation_unverified"}
        )
        return AnalysisRun(agent.agent_run_id, started, "escalated", "citation_unverified")
    cites = [r.id for r in recorded]
    if shadow:
        await end_capability_run(agent, status="succeeded", output={"citations": len(cites)})
        return AnalysisRun(agent.agent_run_id, started, "shadow")
    sealed = await seal(ctx.tenant_id, json.dumps(settled.blocks).encode(), _AAD)
    async with uow(ctx.tenant) as tx:
        await tx.allow_archived_write("post_issuance")
        written = await tx.session.scalar(
            _WRITE,
            {"run": agent.agent_run_id, "sealed": sealed, "rec": settled.recommendation,
             "cites": cites, "c": case_id},
        )  # fmt: skip
        if written is None:
            raise pi.CaseDecided(facts={"case_id": str(case_id)})
        tx.record(
            "post_issuance.analysed",
            target=Target(pi.TARGET, case_id),
            after=Ref(run=agent.agent_run_id, citations=len(cites)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    await end_capability_run(agent, status="succeeded", output={"citations": len(cites)})
    return AnalysisRun(agent.agent_run_id, started, "succeeded")


class AgentNotAvailable(DomainConflict):
    """The firm's AI boundary is not cleared for this capability yet."""

    code = "agent_not_available"


def _p(*segments: dict[str, object]) -> dict[str, object]:
    return {"kind": "p", "segments": list(segments)}


def _t(value: str) -> dict[str, object]:
    return {"kind": "text", "text": value}


def _f(fact_id: str) -> dict[str, object]:
    return {"kind": "fact", "fact_id": fact_id}


# The fake model's answer for Northwind's PI-01 (the golden case): (12,250) on three lines, below
# clearly trivial 12,610, 4.9% of 252,200; no disclosure affected, so code marks No action
# eligible.
FAKE_RESPONSES: Final[Mapping[str, PostIssuanceAnalysisOutput]] = {
    "PI-01": PostIssuanceAnalysisOutput(
        blocks={"version": 1, "parts": [
            _p(_t("The corrected certification differs from the certified trust report by "),
               _f("difference"), _t(" across "), _f("lines"),
               _t(" lines, below clearly trivial of "), _f("clearly_trivial"), _t(" and "),
               _f("share_pct"), _t(" of overall materiality of "), _f("overall_materiality"),
               _t(".")),
        ]},
        recommendation="no_action",
        quotes=[QuoteOut(source="certified", page=1, quote="Statement of Net Assets"),
                QuoteOut(source="corrected", page=1, quote="Corrected certification")],
    ),
}  # fmt: skip


async def read_analysis(ctx: AuthContext, case_id: UUID) -> dict[str, object] | None:
    """The case's stored analysis (blocks, tagged option, citation ids, run), opened for a reader
    that `post_issuance.read` already admitted; None when none was kept."""
    from abacus.kernel.crypto import open_sealed

    async with tenant_session(ctx.tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT analysis_run_id, analysis_sealed, analysis_recommendation, "
                    "analysis_citation_ids FROM post_issuance_events WHERE id = :c"
                ),
                {"c": case_id},
            )
        ).first()
    if row is None or row.analysis_sealed is None:
        return None
    blocks = json.loads(await open_sealed(ctx.tenant_id, bytes(row.analysis_sealed), _AAD))
    return {"run_id": row.analysis_run_id, "blocks": blocks,
            "recommendation": row.analysis_recommendation,
            "citation_ids": list(row.analysis_citation_ids or [])}  # fmt: skip


__all__ = [
    "CAPABILITY",
    "FAKE_RESPONSES",
    "FINAL",
    "PROMPT",
    "AgentNotAvailable",
    "AnalysisRun",
    "OutputRefused",
    "PostIssuanceAnalysisInput",
    "PostIssuanceAnalysisOutput",
    "analyse",
    "facts_for",
    "read_analysis",
    "settle",
]
