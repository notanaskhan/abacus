"""`tax.return_analyst` modes `two_year` and `planning_screen` (T-08-T26; TASK-8921; T-08 §6,
AC5.1, AC7.3; SPEC-710 AC-23, AC-27, AC-32, AC-33; ADR-005, ADR-050, ADR-052, ADR-167; DEC-5923).
Red zone (an agent path).

Code computes, the model explains, a person decides. Neither mode accepts, raises, sends or
dismisses anything: each run's only writes are P-35 suggestions with verified citations.

- **two_year** (TAX-10's "Explain…", `two_year.explain`, a person): code's comparison
  (`two_year_service.comparison`: CY, PY, Δ and Δ% per flagged line) is the model's facts; the
  return's documents (masked pages) are its untrusted sources. Per line the model writes
  AgentBlocks (every figure a fact segment) and quotes at least one passage from an offered
  page; code settles (`settle`: number provenance, quotes on offered pages), verifies each
  quote as a `document_text` citation, writes one suggestion per line (`variance_explanation`)
  and the line's agent explanation version (`author_kind = agent`, the suggestion's id), which a
  reviewer accepts in TAX-10 (acceptance stays human-only, insert-only).
- **planning_screen** (TAX-15, registered as the screen's narrator; background, as the
  opportunity owner's agent): per Open opportunity, code's calculator figures are the facts and
  the return's documents the sources; the model writes the rationale ("Why This Was Surfaced") and
  internal talking points; code settles and verifies the same way, writes two suggestions
  (`planning_rationale`, fields `rationale` and `talking_points`), and sets the opportunity's
  rationale (code's rendering of the settled blocks) and suggestion ids. No client draft exists
  in the output (ADR P-25 is not accepted, DEC-79): the raise sheet uses the firm's template.
- **Consent and boundary.** Before any model call both the `use` and `ai_disclosure` consents must
  be in force for the filing unit and the years read (C19; condition 6 again at the gateway): the
  route answers 409 `consent_7216_missing`; the narrator is only called for consented returns. A
  firm whose AI boundary is not cleared gets the DF-04 state: the run ends escalated with
  `boundary_refused:<reason>` (synthetic firms only until a Bedrock report clears the modes,
  DEC-5901) and the template rationale stands.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AgentContext, AuthContext
from abacus.modules.tax.compute.two_year import ComparisonLine

CAPABILITY: Final = "tax.return_analyst"
TWO_YEAR_PROMPT: Final = "tax.return_analyst.two_year@v1"
PLANNING_PROMPT: Final = "tax.return_analyst.planning_screen@v1"
EXPLANATION_TARGET: Final = "variance_explanation"
RATIONALE_TARGET: Final = "planning_rationale"
MAX_SOURCES: Final = 4
MAX_PAGES: Final = 12
Int = classified("internal")
Tri = classified("restricted", tri=True)
Status = Literal["succeeded", "escalated", "shadow"]


class OutputRefused(DomainConflict):
    """The output may not be shown (`facts.reason`, a code)."""

    code = "agent_output_refused"


class AgentNotAvailable(DomainConflict):
    """DF-04: the firm's AI boundary is not cleared for these modes yet."""

    code = "agent_not_available"


# --- the model's input and output ----------------------------------------------------------------


class FactIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$"), Int]
    kind: Annotated[Literal["money", "percent", "count"], Int]
    value: Annotated[str, Field(max_length=40), Tri]
    basis: Annotated[str, Field(max_length=200), Int] = "code"


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Annotated[str, Field(pattern=r"^s[a-z]$"), Int]  # sa, sb, … (no digits)
    title: Annotated[str, Field(max_length=200), Tri]
    pages: Annotated[list[int], Field(min_length=1, max_length=MAX_PAGES), Int]


class SubjectIn(BaseModel):
    """One flagged line or one opportunity: its key and the facts that belong to it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: Annotated[str, Field(max_length=60), Int]
    label: Annotated[str, Field(max_length=200), Tri]
    fact_ids: Annotated[list[str], Field(max_length=12), Int]


class ModeInput(BaseModel):
    """What the model sees; the documents' text is untrusted (never instructions)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Annotated[Literal["two_year", "planning_screen"], Int]
    subjects: Annotated[list[SubjectIn], Field(min_length=1, max_length=40), Int]
    facts: Annotated[list[FactIn], Field(min_length=1, max_length=200), Int]
    sources: Annotated[list[SourceIn], Field(min_length=1, max_length=MAX_SOURCES), Int]
    untrusted: Annotated[list[str], Field(max_length=80), Tri] = []


class QuoteOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Annotated[str, Field(pattern=r"^s[a-z]$"), Int]
    page: Annotated[int, Field(ge=1, le=5000), Int]
    quote: Annotated[str, Field(min_length=3, max_length=200), Tri]


class SubjectOut(BaseModel):
    """Per subject: AgentBlocks (`blocks`; the explanation or the rationale), and for a planning
    opportunity the internal talking points; at least one quote. No client draft, no action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: Annotated[str, Field(max_length=60), Int]
    blocks: Annotated[dict[str, object], Tri]
    talking_points: Annotated[dict[str, object] | None, Tri] = None
    quotes: Annotated[list[QuoteOut], Field(min_length=1, max_length=6), Int]


class ModeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subjects: Annotated[list[SubjectOut], Field(min_length=1, max_length=40), Int]


@dataclass(frozen=True)
class SettledSubject:
    key: str
    blocks: dict[str, object]
    talking_points: dict[str, object] | None
    quotes: tuple[QuoteOut, ...]


# --- code settles --------------------------------------------------------------------------------


def settle(given: ModeInput, answer: ModeOutput) -> tuple[SettledSubject, ...]:
    """Every subject's blocks carry only code's facts (no free number), its quotes sit on offered
    pages, every subject the input named is answered once, and a two-year answer carries no
    talking points (they are TAX-15's)."""
    from abacus.modules.agents.api import AgentFact, BlocksRejected, validate_blocks

    facts = {f.id: AgentFact(id=f.id, kind=f.kind, value=f.value, basis=f.basis)
             for f in given.facts}  # fmt: skip
    pages = {s.source: set(s.pages) for s in given.sources}
    wanted = {s.key for s in given.subjects}
    answered = [s.key for s in answer.subjects]
    if sorted(answered) != sorted(wanted):
        raise OutputRefused(facts={"reason": "subjects_not_answered"})
    out: list[SettledSubject] = []
    for s in answer.subjects:
        if given.mode == "two_year" and s.talking_points is not None:
            raise OutputRefused(facts={"reason": "talking_points_not_offered"})
        try:
            blocks = _dump(validate_blocks(s.blocks, facts, frozenset()), s.blocks)
            points = (
                None if s.talking_points is None
                else _dump(validate_blocks(s.talking_points, facts, frozenset()), s.talking_points)
            )  # fmt: skip
        except BlocksRejected as rejected:
            raise OutputRefused(facts={"reason": rejected.code}) from None
        if any(q.page not in pages.get(q.source, set()) for q in s.quotes):
            raise OutputRefused(facts={"reason": "page_not_offered"})
        out.append(SettledSubject(s.key, blocks, points, tuple(s.quotes)))
    return tuple(sorted(out, key=lambda x: x.key))


def _dump(found: object, raw: dict[str, object]) -> dict[str, object]:
    dump = getattr(found, "model_dump", None)
    return cast("dict[str, object]", dump(mode="json") if callable(dump) else raw)


def _shown(fact: FactIn) -> str:
    try:
        value = Decimal(fact.value)
    except InvalidOperation:
        return fact.value
    if fact.kind == "percent":
        return f"{value.normalize():f}%"
    if fact.kind == "count":
        return f"{int(value):,}"
    whole = value.quantize(Decimal(1))
    return f"({abs(whole):,})" if whole < 0 else f"{whole:,}"


def render(blocks: Mapping[str, object], facts: Sequence[FactIn], limit: int = 600) -> str:
    """The settled blocks as plain text with code's values in place of each fact (what TAX-10's
    explanation and TAX-15's rationale show)."""
    by_id = {f.id: f for f in facts}
    words: list[str] = []
    for part in cast("list[dict[str, object]]", blocks.get("parts") or []):
        for seg in cast("list[dict[str, object]]", part.get("segments") or []):
            if seg.get("kind") == "fact":
                found = by_id.get(str(seg.get("fact_id")))
                words.append("" if found is None else _shown(found))
            else:
                words.append(str(seg.get("text", "")))
        words.append(" ")
    return " ".join("".join(words).split())[:limit]


# --- shared run plumbing -------------------------------------------------------------------------


@dataclass(frozen=True)
class ModeRun:
    run_id: UUID
    started_at: datetime
    status: Status
    reason: str | None = None
    suggestions: int = 0


@dataclass(frozen=True)
class _Sources:
    given: list[SourceIn]
    versions: dict[str, UUID]
    untrusted: list[str]


_LETTERS: Final = "abcdefghijklmnopqrstuvwxyz"


async def _sources(ctx: AuthContext, engagement_id: UUID) -> _Sources:
    """The return's latest documents (masked pages, ADR-167) as the model's untrusted sources."""
    from abacus.modules.evidence.api import engagement_documents, masked_pages

    docs = [d for d in await engagement_documents(ctx.tenant, engagement_id) if d[5]]
    given: list[SourceIn] = []
    versions: dict[str, UUID] = {}
    untrusted: list[str] = []
    for version_id, _item, title, _category, _n, _latest in docs:
        if len(given) >= MAX_SOURCES:
            break
        found = await masked_pages(ctx.tenant, evidence_version_id=version_id)
        pages: dict[int, str] = {} if found is None else dict(found)
        if not pages:
            continue
        ref = f"s{_LETTERS[len(given)]}"
        chosen = sorted(pages)[:MAX_PAGES]
        given.append(SourceIn(source=ref, title=str(title)[:200], pages=chosen))
        versions[ref] = version_id
        untrusted += [f"{ref} page {p}: {pages[p]}"[:4000] for p in chosen]
    return _Sources(given, versions, untrusted[:80])


async def _answer(
    agent: AgentContext, prompt: str, given: ModeInput, subjects: Sequence[object]
) -> ModeOutput:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    builder = ContextBuilder().task(given.model_dump(mode="json"), untrusted=("untrusted",))
    for subject in subjects:
        builder = builder.subjects(subject)  # pyright: ignore[reportArgumentType] -- DataSubject
    result = await call(
        GatewayCall(
            purpose=spec.purpose, prompt=prompt, tier=spec.tier, output_schema=ModeOutput,
            budget_usd=spec.limits.max_cost_usd,
            attribution=Attribution(agent.tenant, agent.engagement_id, CAPABILITY,
                                    agent.agent_run_id),
            context=builder.build(), work_class=spec.work_class, essential=spec.essential,
            routes=spec.routes, cheaper_tiers=spec.cheaper_tiers,
            max_output_tokens=spec.limits.max_output_tokens,
            timeout_seconds=spec.limits.max_seconds,
        )
    )  # fmt: skip
    return cast(ModeOutput, result.output)


def _reason(exc: Exception) -> str:
    code = getattr(exc, "code", None) or getattr(exc, "reason", None) or type(exc).__name__
    text_ = str(code)
    return text_ if text_.startswith("boundary_refused") else f"boundary_refused:{text_}"[:60]


async def _verified(
    agent: AgentContext,
    target: str,
    target_id: UUID,
    field: str,
    settled: SettledSubject,
    versions: Mapping[str, UUID],
    *,
    shadow: bool,
    work_item_id: UUID,
) -> list[UUID] | None:
    """The subject's quotes as `document_text` citations; None if any does not verify."""
    from abacus.modules.evidence.api import CitationAnchor, CitationClaim, record_citations

    if agent.engagement_id is None:
        return None
    claims = [
        CitationClaim("document_text",
                      {"evidence_version_id": str(versions[q.source]), "page": q.page},
                      quote=q.quote)
        for q in settled.quotes if q.source in versions
    ]  # fmt: skip
    if len(claims) != len(settled.quotes):
        return None
    anchor = CitationAnchor(target, target_id, field, None, agent.engagement_id,
                            work_item_id=work_item_id)  # fmt: skip
    async with uow(agent.tenant) as tx:
        recorded = await record_citations(
            tx, actor=agent, anchor=anchor, claims=claims, shadow=shadow
        )
    if len(recorded) != len(claims) or not all(r.verified for r in recorded):
        return None
    return [r.id for r in recorded]


async def _consented(tenant: TenantContext, entity: UUID, years: Sequence[int]) -> bool:
    from abacus.kernel.clock import now
    from abacus.modules.organisations.api import tri_consent_verdict

    at = await now(tenant)
    for year in sorted(set(years)):
        if not (await tri_consent_verdict(tenant, [entity], at, tax_year=year)).valid:
            return False
    return True


# --- two_year ------------------------------------------------------------------------------------

_RETURN: Final = text("SELECT client_entity_id, tax_year FROM tax_returns WHERE work_item_id = :r")
_NEXT: Final = text(
    "SELECT coalesce(max(version_no), 0) + 1 FROM variance_explanation_versions "
    "WHERE work_item_id = :w AND line_key = :k"
)
_AGENT_VERSION: Final = text(
    "INSERT INTO variance_explanation_versions (tenant_id, engagement_id, work_item_id, "
    "line_key, version_no, text, citations, author_kind, suggestion_id, created_by) VALUES "
    "(:t, :e, :w, :k, :n, :text, CAST(:c AS jsonb), 'agent', :s, :u) RETURNING id"
)


async def return_subject(tenant: TenantContext, return_id: UUID) -> tuple[UUID, int]:
    """The return's §7216 subject: its client entity and tax year."""
    async with tenant_session(tenant) as session:
        ret = (await session.execute(_RETURN, {"r": return_id})).first()
    if ret is None:
        raise OutputRefused(facts={"reason": "return_missing"})
    return cast(UUID, ret.client_entity_id), int(ret.tax_year)


def two_year_facts(lines: Sequence[ComparisonLine]) -> tuple[list[SubjectIn], list[FactIn]]:
    """Code's facts for the flagged lines: CY, PY, Δ and Δ% (each a fact; ids carry the line's
    position, never its digits)."""
    subjects: list[SubjectIn] = []
    facts: list[FactIn] = []
    for n, line in enumerate(lines):
        tag = f"l{_LETTERS[n // 26]}{_LETTERS[n % 26]}"
        ids = [f"{tag}_cy", f"{tag}_py", f"{tag}_delta"]
        facts += [
            FactIn(id=ids[0], kind="money", value=str(line.current), basis=f"{line.code} CY"),
            FactIn(id=ids[1], kind="money", value=str(line.prior), basis=f"{line.code} PY"),
            FactIn(id=ids[2], kind="money", value=str(line.delta), basis=f"{line.code} delta"),
        ]
        if line.delta_pct is not None:
            ids.append(f"{tag}_pct")
            facts.append(FactIn(id=ids[3], kind="percent", value=str(line.delta_pct),
                                basis=f"{line.code} delta pct"))  # fmt: skip
        subjects.append(SubjectIn(key=line.code, label=line.label[:200], fact_ids=ids))
    return subjects, facts


async def two_year_explain(
    ctx: AuthContext, return_id: UUID, line_keys: Sequence[str] = ()
) -> ModeRun:
    """TAX-10's "Explain…" (module docstring). 409 `consent_7216_missing` without both consents
    for both years; 409 `agent_not_available` on a firm whose boundary is not cleared."""
    from abacus.ai_gateway import DataSubject, is_synthetic
    from abacus.modules.agents.api import (
        create_suggestion,
        end_capability_run,
        start_capability_run,
        starts_in_shadow,
    )
    from abacus.modules.tax.practice_tools_errors import Consent7216Missing
    from abacus.modules.tax.two_year_service import comparison

    found = await comparison(ctx, return_id)
    entity, year = await return_subject(ctx.tenant, return_id)
    if not await _consented(ctx.tenant, entity, (year, year - 1)):
        raise Consent7216Missing(facts={"client_entity_id": str(entity)})
    if not await is_synthetic(ctx.tenant):
        raise AgentNotAvailable(facts={"capability": CAPABILITY})
    flagged = [ln for ln in found.lines if ln.line.flagged
               and (not line_keys or ln.line.code in set(line_keys))]  # fmt: skip
    if not flagged:
        raise OutputRefused(facts={"reason": "nothing_flagged"})
    started = system_now()
    agent = await start_capability_run(ctx, CAPABILITY, found.engagement_id)
    if agent is None:
        raise AgentNotAvailable(facts={"reason": "run_not_recorded"})
    async with tenant_session(agent.tenant) as session:
        shadow = bool(await starts_in_shadow(session, agent.tenant, CAPABILITY))
    sources = await _sources(ctx, found.engagement_id)
    if not sources.given:
        await end_capability_run(agent, status="escalated", output={"reason": "no_sources"})
        return ModeRun(agent.agent_run_id, started, "escalated", "no_sources")
    subjects, facts = two_year_facts([ln.line for ln in flagged])
    given = ModeInput(mode="two_year", subjects=subjects, facts=facts, sources=sources.given,
                      untrusted=sources.untrusted)  # fmt: skip
    try:
        settled = settle(given, await _answer(
            agent, TWO_YEAR_PROMPT, given,
            [DataSubject(entity, year), DataSubject(entity, year - 1)],
        ))  # fmt: skip
    except OutputRefused as refused:
        reason = str((refused.facts or {}).get("reason"))[:60]
        await end_capability_run(agent, status="escalated", output={"reason": reason})
        return ModeRun(agent.agent_run_id, started, "escalated", reason)
    except Exception as exc:  # the boundary, budget or schema refused: DF-04
        reason = _reason(exc)
        await end_capability_run(agent, status="escalated", output={"reason": reason})
        return ModeRun(agent.agent_run_id, started, "escalated", reason)
    written = 0
    for s in settled:
        cites = await _verified(agent, EXPLANATION_TARGET, return_id, s.key, s, sources.versions,
                                shadow=shadow, work_item_id=return_id)  # fmt: skip
        if cites is None:
            await end_capability_run(
                agent, status="escalated", output={"reason": "citation_unverified"}
            )
            return ModeRun(agent.agent_run_id, started, "escalated", "citation_unverified",
                           written)  # fmt: skip
        if shadow:
            continue
        body = render(s.blocks, facts)
        suggestion = await create_suggestion(
            agent, engagement_id=found.engagement_id, target_type=EXPLANATION_TARGET,
            target_id=return_id, field_key=s.key, proposed_value={"t": "text", "v": body},
            citation_ids=cites, rationale_ref=None,
        )  # fmt: skip
        async with uow(agent.tenant) as tx:
            number = int(cast(int, await tx.session.scalar(_NEXT, {"w": return_id, "k": s.key})))
            import json

            version = await tx.session.scalar(
                _AGENT_VERSION,
                {"t": ctx.tenant_id, "e": found.engagement_id, "w": return_id, "k": s.key,
                 "n": number, "text": body, "c": json.dumps([str(c) for c in cites]),
                 "s": suggestion, "u": ctx.user_id},
            )  # fmt: skip
            tx.record(
                "variance_explanation.proposed",
                target=Target("variance_explanation_version", cast(UUID, version)),
                after=Ref(version=number, citations=len(cites)),
                scope=Scope(engagement_id=found.engagement_id, work_item_id=return_id),
            )
        written += 1
    status: Status = "shadow" if shadow else "succeeded"
    await end_capability_run(agent, status="succeeded", output={"suggestions": written})
    return ModeRun(agent.agent_run_id, started, status, None, written)


# --- planning_screen -----------------------------------------------------------------------------

_OPPORTUNITIES: Final = text(
    "SELECT id, engagement_id, rule_key, title, savings_basis, owner_user_id, status "
    "FROM planning_opportunities WHERE work_item_id = :r AND id = ANY(:ids) ORDER BY id"
)
_SET_RATIONALE: Final = text(
    "UPDATE planning_opportunities SET body = CAST(:body AS jsonb), "
    "rationale_suggestion_id = :rs, talking_points_suggestion_id = :ts, "
    "row_version = row_version + 1, updated_at = clock_timestamp() "
    "WHERE id = :id AND status IN ('open', 'not_screened')"
)


def planning_facts(rows: Sequence[object]) -> tuple[list[SubjectIn], list[FactIn]]:
    """Code's facts per opportunity: its calculator's figures (`savings_basis.figures`) and the
    estimate; ids by position (digit-free)."""
    subjects: list[SubjectIn] = []
    facts: list[FactIn] = []
    for n, row in enumerate(rows):
        tag = f"o{_LETTERS[n // 26]}{_LETTERS[n % 26]}"
        basis = cast("dict[str, object]", getattr(row, "savings_basis", None) or {})
        figures = cast("dict[str, str]", basis.get("figures") or {})
        ids: list[str] = []
        for key in sorted(figures):
            fid = f"{tag}_{''.join(ch for ch in key if ch.isalpha() or ch == '_')}"[:40]
            kind: Literal["money", "percent"] = "percent" if key.endswith("pct") else "money"
            facts.append(FactIn(id=fid, kind=kind, value=str(figures[key]), basis=key))
            ids.append(fid)
        subjects.append(
            SubjectIn(key=str(getattr(row, "id")), label=str(getattr(row, "title")),  # noqa: B009
                      fact_ids=ids[:12])
        )  # fmt: skip
    return subjects, facts


async def planning_narrate(
    tenant: TenantContext, return_id: UUID, opportunity_ids: Sequence[UUID]
) -> ModeRun | None:
    """The `planning_screen` run for a consented return's Open opportunities (the screen's
    narrator, `register_planning_narrator`), as the opportunity owner's agent. None when there is
    nothing to narrate or no owner."""
    import json

    from abacus.ai_gateway import DataSubject, is_synthetic
    from abacus.modules.agents.api import (
        create_suggestion,
        end_capability_run,
        start_capability_run,
        starts_in_shadow,
    )
    from abacus.modules.identity.api import member_context

    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(_OPPORTUNITIES, {"r": return_id, "ids": list(opportunity_ids)})
        ).all()
        ret = (await session.execute(_RETURN, {"r": return_id})).first()
    rows = [r for r in rows if r.status == "open" and r.owner_user_id is not None]
    if not rows or ret is None or not await is_synthetic(tenant):
        return None
    entity, year = cast(UUID, ret.client_entity_id), int(ret.tax_year)
    if not await _consented(tenant, entity, (year,)):
        return None
    owner = await member_context(tenant.tenant_id, cast(UUID, rows[0].owner_user_id))
    if owner is None:
        return None
    engagement_id = cast(UUID, rows[0].engagement_id)
    started = system_now()
    agent = await start_capability_run(owner, CAPABILITY, engagement_id)
    if agent is None:
        return None
    async with tenant_session(agent.tenant) as session:
        shadow = bool(await starts_in_shadow(session, agent.tenant, CAPABILITY))
    sources = await _sources(owner, engagement_id)
    subjects, facts = planning_facts(rows)
    if not sources.given or not facts:
        await end_capability_run(agent, status="escalated", output={"reason": "no_sources"})
        return ModeRun(agent.agent_run_id, started, "escalated", "no_sources")
    given = ModeInput(mode="planning_screen", subjects=subjects, facts=facts,
                      sources=sources.given, untrusted=sources.untrusted)  # fmt: skip
    try:
        settled = settle(given, await _answer(agent, PLANNING_PROMPT, given,
                                              [DataSubject(entity, year)]))  # fmt: skip
    except OutputRefused as refused:
        reason = str((refused.facts or {}).get("reason"))[:60]
        await end_capability_run(agent, status="escalated", output={"reason": reason})
        return ModeRun(agent.agent_run_id, started, "escalated", reason)
    except Exception as exc:  # DF-04: the template rationale stands
        reason = _reason(exc)
        await end_capability_run(agent, status="escalated", output={"reason": reason})
        return ModeRun(agent.agent_run_id, started, "escalated", reason)
    written = 0
    for s in settled:
        opportunity = UUID(s.key)
        cites = await _verified(
            agent, RATIONALE_TARGET, opportunity, "rationale", s, sources.versions,
            shadow=shadow, work_item_id=return_id,
        )  # fmt: skip
        if cites is None:
            await end_capability_run(
                agent, status="escalated", output={"reason": "citation_unverified"}
            )
            return ModeRun(agent.agent_run_id, started, "escalated", "citation_unverified",
                           written)  # fmt: skip
        if shadow:
            continue
        body = render(s.blocks, facts, 4000)
        rationale = await create_suggestion(
            agent, engagement_id=engagement_id, target_type=RATIONALE_TARGET,
            target_id=opportunity, field_key="rationale", proposed_value={"t": "text", "v": body},
            citation_ids=cites, rationale_ref=None,
        )  # fmt: skip
        points = None
        if s.talking_points is not None:
            points = await create_suggestion(
                agent, engagement_id=engagement_id, target_type=RATIONALE_TARGET,
                target_id=opportunity, field_key="talking_points",
                proposed_value={"t": "text", "v": render(s.talking_points, facts, 4000)},
                citation_ids=cites, rationale_ref=None,
            )  # fmt: skip
        async with uow(tenant) as tx:
            await tx.session.execute(
                _SET_RATIONALE,
                {"body": json.dumps([{"kind": "text", "text": body}]), "rs": rationale,
                 "ts": points, "id": opportunity},
            )  # fmt: skip
            tx.record(
                "planning_opportunity.narrated",
                target=Target("planning_opportunity", opportunity),
                after=Ref(run=agent.agent_run_id, citations=len(cites)),
                scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
            )
        written += 1
    await end_capability_run(agent, status="succeeded", output={"suggestions": written})
    return ModeRun(agent.agent_run_id, started, "shadow" if shadow else "succeeded", None, written)


# --- appliers (a person adopts) ------------------------------------------------------------------


async def _return_engagement(tenant: TenantContext, return_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        return await session.scalar(
            text("SELECT engagement_id FROM tax_returns WHERE work_item_id = :r"), {"r": return_id}
        )


async def _opportunity_engagement(tenant: TenantContext, opportunity_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        return await session.scalar(
            text("SELECT engagement_id FROM planning_opportunities WHERE id = :o"),
            {"o": opportunity_id},
        )


async def apply_explanation(tx: object, ctx: AuthContext, value: object) -> None:
    """Adopting an explanation suggestion is the person's own version of it (TAX-10's edit);
    acceptance stays a separate, human-only act over the values seen."""
    from abacus.kernel.uow import UnitOfWork
    from abacus.modules.agents.api import AdoptedValue
    from abacus.modules.engagements.api import engagement_resource_of
    from abacus.modules.identity.api import authorise

    adopted = cast(AdoptedValue, value)
    unit = cast(UnitOfWork, tx)
    engagement = await _return_engagement(ctx.tenant, adopted.target_id)
    if engagement is None:
        raise OutputRefused(facts={"reason": "return_missing"})
    await authorise(
        ctx, "variance_explanation.edit", await engagement_resource_of(ctx.tenant, engagement)
    )
    body = str(adopted.value.get("v") or "")[:600]
    number = int(
        cast(
            int, await unit.session.scalar(_NEXT, {"w": adopted.target_id, "k": adopted.field_key})
        )
    )
    version = await unit.session.scalar(
        text(
            "INSERT INTO variance_explanation_versions (tenant_id, engagement_id, work_item_id, "
            "line_key, version_no, text, author_kind, created_by) VALUES (:t, :e, :w, :k, :n, "
            ":text, 'human', :u) RETURNING id"
        ),
        {"t": ctx.tenant_id, "e": engagement, "w": adopted.target_id, "k": adopted.field_key,
         "n": number, "text": body, "u": ctx.user_id},
    )  # fmt: skip
    unit.record(
        "variance_explanation.edited",
        target=Target("variance_explanation_version", cast(UUID, version)),
        after=Ref(version=number),
        scope=Scope(engagement_id=engagement, work_item_id=adopted.target_id),
    )


async def apply_rationale(tx: object, ctx: AuthContext, value: object) -> None:
    """Adopting a rationale or talking points keeps them as shown (already on the opportunity):
    the adoption is recorded, nothing else changes (the raise is a separate person's send)."""
    from abacus.kernel.uow import UnitOfWork
    from abacus.modules.agents.api import AdoptedValue

    adopted = cast(AdoptedValue, value)
    unit = cast(UnitOfWork, tx)
    engagement = await _opportunity_engagement(ctx.tenant, adopted.target_id)
    if engagement is None:
        raise OutputRefused(facts={"reason": "opportunity_missing"})
    unit.record(
        "planning_opportunity.rationale_adopted",
        target=Target("planning_opportunity", adopted.target_id),
        scope=Scope(engagement_id=engagement),
    )


def register() -> None:
    """At the tax api's import: the suggestion appliers and the planning narrator."""
    from abacus.modules.agents.api import register_suggestion_applier
    from abacus.modules.tax.planning.service import register_planning_narrator

    register_suggestion_applier(
        EXPLANATION_TARGET,
        apply_explanation,
        engagement_of=_return_engagement,
    )
    register_suggestion_applier(
        RATIONALE_TARGET,
        apply_rationale,
        engagement_of=_opportunity_engagement,
    )

    async def narrator(tenant: TenantContext, return_id: UUID, ids: Sequence[UUID]) -> None:
        await planning_narrate(tenant, return_id, ids)

    register_planning_narrator(narrator)


__all__ = [
    "CAPABILITY",
    "PLANNING_PROMPT",
    "TWO_YEAR_PROMPT",
    "AgentNotAvailable",
    "FactIn",
    "ModeInput",
    "ModeOutput",
    "ModeRun",
    "OutputRefused",
    "QuoteOut",
    "SourceIn",
    "SubjectIn",
    "SubjectOut",
    "apply_explanation",
    "apply_rationale",
    "planning_facts",
    "planning_narrate",
    "register",
    "render",
    "settle",
    "two_year_explain",
    "two_year_facts",
]
