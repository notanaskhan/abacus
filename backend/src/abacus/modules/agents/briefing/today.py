"""`briefing.today` v1: one engagement's Today briefing (I-02-T08; I-02 §6, F3; SPEC-654;
ADR-019, ADR-050, ADR-052, ADR-230; DEC-4721). Red (agent).

- **Input** is code's only: the engagement's label, the gates the viewer must act on (kind,
  subject label, due date and whether something blocks it, by gate id) and the facts registry
  (`facts.collect`): ids, kinds and values. Gate titles and client strings sit in an untrusted
  block.
- **Output** `EngagementBriefing`: a one-paragraph summary, exactly one why line per supplied gate
  (by gate id) and an optional risk line, each an AgentBlocks paragraph whose figures are fact
  references and whose sources are citation ids (ADR-230, P-24).
- **Validation** by code before anything is stored (`validate`): gate coverage (every gate, none
  invented), every why line cites or references a fact, every number is a registered fact
  (numbers outside fact segments are refused), every citation is one of the run's candidates, a
  recommendation restated is the card's own, no reserved verb (approve, sign off, …), style rules
  (AgentBlocks' own lint: no markdown, links or deceptive characters). One repair: the model is
  asked once more with the codes it failed; a second failure stores the briefing `unverified`,
  never displayed.
- **The briefing step** (`build_engagement_briefing`) runs under the run's AgentContext: collects
  the facts as the viewer, refuses `consent_7216` before any model call (stored `unavailable`),
  skips the call when today's ready briefing has the same `facts_hash`, and writes one
  `daily_briefings` row (scope `engagement`, next `seq`) with the blocks, citations, run and
  prompt reference.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.modules.agents.blocks import AgentBlocks, BlocksRejected, Fact, validate_blocks
from abacus.modules.agents.briefing.facts import BriefingFacts, ConsentRequired, collect

CAPABILITY: Final = "briefing.today"
PROMPT: Final = "briefing.today@v1"
Int = classified("internal")
Conf = classified("confidential")
_RESERVED: Final = re.compile(
    r"\b(?:I|we)\s+(?:have\s+|will\s+)?(?:approved?|signed?(?: off)?|released?|sent|posted?|"
    r"elected|filed|decided)\b|\blet me\s+(?:approve|sign|release|send|post|elect|file|decide)\b",
    re.IGNORECASE,
)


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class GateIn(BaseModel):
    model_config = _cfg()

    gate_id: Annotated[str, Int]
    kind: Annotated[str, Int]
    title: Annotated[str, Field(max_length=200), Conf]
    due_on: Annotated[str | None, Int] = None
    blocked: Annotated[bool, Int] = False
    recommendation: Annotated[str | None, Field(max_length=40), Int] = None


class FactIn(BaseModel):
    model_config = _cfg()

    id: Annotated[str, Int]
    kind: Annotated[str, Int]
    value: Annotated[str, Conf]


class BriefingInput(BaseModel):
    model_config = _cfg()

    engagement: Annotated[str, Field(max_length=200), Conf]
    gates: Annotated[list[GateIn], Field(max_length=40), Conf]
    facts: Annotated[list[FactIn], Field(max_length=200), Conf]
    citations: Annotated[list[str], Field(max_length=200), Int]


class WhyLine(BaseModel):
    model_config = _cfg()

    gate_id: Annotated[str, Int]
    line: Annotated[AgentBlocks, Conf]
    recommendation: Annotated[str | None, Field(max_length=40), Int] = None


class EngagementBriefing(BaseModel):
    model_config = _cfg()

    summary: Annotated[AgentBlocks, Conf]
    why: Annotated[list[WhyLine], Field(max_length=40), Conf]
    risk: Annotated[AgentBlocks | None, Conf] = None


def _text_of(blocks: AgentBlocks) -> str:
    return blocks.model_dump_json()


def _refs(blocks: AgentBlocks) -> tuple[set[str], set[str]]:
    """(fact ids, citation ids) a block set references."""
    raw = blocks.model_dump()
    facts: set[str] = set()
    cites: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            node_d = cast(dict[str, object], node)
            if "fact_id" in node_d and isinstance(node_d["fact_id"], str):
                facts.add(node_d["fact_id"])
            if "citation_id" in node_d and node_d["citation_id"] is not None:
                cites.add(str(node_d["citation_id"]))
            for v in node_d.values():
                walk(v)
        elif isinstance(node, list):
            for v in cast(list[object], node):
                walk(v)

    walk(raw)
    return facts, cites


def validate(
    answer: EngagementBriefing, facts: BriefingFacts, recommendations: Mapping[str, str | None]
) -> list[str]:
    """The codes the briefing fails (empty: shown). Blocks lint runs through `validate_blocks`."""
    codes: list[str] = []
    registry = facts.facts
    citations = {UUID(int=0)}  # candidate citations are refs by kind (record_field:…), not uuids
    gate_ids = {str(g.gate_id) for g in facts.gates}
    seen = {w.gate_id for w in answer.why}
    if seen != gate_ids:
        codes.append("gate_coverage")
    parts = [
        answer.summary,
        *(w.line for w in answer.why),
        *([answer.risk] if answer.risk else []),
    ]
    for blocks in parts:
        try:
            validate_blocks(blocks.model_dump(), registry, citations)
        except BlocksRejected as rejected:
            codes.append(f"blocks:{rejected.code}")
        if _RESERVED.search(_text_of(blocks)):
            codes.append("reserved_verb")
    for w in answer.why:
        fact_refs, cite_refs = _refs(w.line)
        if not fact_refs and not cite_refs:
            codes.append("uncited_line")
        if w.recommendation is not None and w.recommendation != recommendations.get(w.gate_id):
            codes.append("recommendation_fidelity")
    return sorted(set(codes))


def input_of(
    facts: BriefingFacts, engagement_label: str, titles: Mapping[str, str]
) -> BriefingInput:
    return BriefingInput(
        engagement=engagement_label,
        gates=[
            GateIn(
                gate_id=str(g.gate_id),
                kind=g.kind,
                title=titles.get(str(g.gate_id), g.kind)[:200],
                due_on=None if g.due_on is None else g.due_on.isoformat(),
                blocked=g.blocked,
            )
            for g in facts.gates
        ],
        facts=[FactIn(id=f.id, kind=f.kind, value=f.value) for f in facts.facts.values()],
        citations=[f"{c.kind}:{c.ref}" for c in facts.citations][:200],
    )


async def _call(
    agent: object, given: BriefingInput, repair: Sequence[str]
) -> EngagementBriefing | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    task: dict[str, object] = given.model_dump()
    if repair:
        task["repair"] = list(repair)  # the codes the last answer failed (one repair)
    context = ContextBuilder().task(task, untrusted=("gates",)).build()
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=EngagementBriefing,
                budget_usd=spec.limits.max_cost_usd,
                attribution=Attribution(
                    agent.tenant,  # type: ignore[attr-defined]
                    agent.engagement_id,  # type: ignore[attr-defined]
                    CAPABILITY,
                    agent.agent_run_id,  # type: ignore[attr-defined]
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
    except Exception:  # a refused call (boundary, budget, schema)
        return None
    try:
        return EngagementBriefing.model_validate(result.output)
    except ValidationError:
        return None


@dataclass(frozen=True)
class Built:
    status: Literal["ready", "unverified", "failed", "unavailable", "unchanged"]
    briefing_id: UUID | None
    codes: tuple[str, ...] = ()


_TODAY: Final = text(
    "SELECT id, seq, status, facts_hash FROM daily_briefings WHERE scope = 'engagement' AND "
    "viewer_user_id = :v AND engagement_id = :e AND brief_date = :d ORDER BY seq DESC LIMIT 1"
)
_INSERT: Final = text(
    "INSERT INTO daily_briefings (tenant_id, scope, viewer_user_id, engagement_id, brief_date, "
    "seq, status, unavailable_reason, facts_hash, blocks, agent_run_id, prompt_ref, "
    "capability_version, built_at) VALUES (:t, 'engagement', :v, :e, :d, :seq, :status, :reason, "
    ":hash, CAST(:blocks AS jsonb), :run, :prompt, 1, clock_timestamp()) RETURNING id"
)


async def build_engagement_briefing(
    agent: object, viewer: object, engagement_id: UUID, *, engagement_label: str,
    titles: Mapping[str, str], recommendations: Mapping[str, str | None], on: date,
) -> Built:  # fmt: skip
    """The briefing step (module docstring)."""
    from abacus.kernel.db import tenant_session
    from abacus.kernel.uow import Ref, Target, uow

    tenant = agent.tenant  # type: ignore[attr-defined]
    viewer_id: UUID = viewer.user_id  # type: ignore[attr-defined]

    async def store(status: str, reason: str | None, digest: str | None, blocks: object) -> UUID:
        async with tenant_session(tenant) as session:
            prior = (
                await session.execute(_TODAY, {"v": viewer_id, "e": engagement_id, "d": on})
            ).first()
        async with uow(tenant) as tx:
            new_id = cast(
                UUID,
                await tx.session.scalar(
                    _INSERT,
                    {
                        "t": tenant.tenant_id, "v": viewer_id, "e": engagement_id, "d": on,
                        "seq": 1 if prior is None else int(prior.seq) + 1, "status": status,
                        "reason": reason,
                        "hash": None if digest is None else bytes.fromhex(digest),
                        "blocks": None if blocks is None else json.dumps(blocks),
                        "run": agent.agent_run_id,  # type: ignore[attr-defined]
                        "prompt": PROMPT,
                    },
                ),
            )  # fmt: skip
            tx.record(
                "daily_briefing.built",
                target=Target("daily_briefing", new_id),
                after=Ref(status=status, engagement=engagement_id),
            )
        return new_id

    try:
        facts = await collect(viewer, engagement_id)
    except ConsentRequired:
        return Built("unavailable", await store("unavailable", "consent_7216", None, None))
    async with tenant_session(tenant) as session:
        prior = (
            await session.execute(_TODAY, {"v": viewer_id, "e": engagement_id, "d": on})
        ).first()
    if (
        prior is not None
        and prior.status == "ready"
        and prior.facts_hash == bytes.fromhex(facts.facts_hash)
    ):
        return Built("unchanged", prior.id)
    given = input_of(facts, engagement_label, titles)
    answer = await _call(agent, given, ())
    if answer is None:
        return Built("failed", await store("failed", None, facts.facts_hash, None))
    codes = validate(answer, facts, recommendations)
    if codes:
        repaired = await _call(agent, given, codes)
        if repaired is not None and not validate(repaired, facts, recommendations):
            answer, codes = repaired, []
    status = "unverified" if codes else "ready"
    stored = await store(status, None, facts.facts_hash, answer.model_dump(mode="json"))
    return Built(status, stored, tuple(codes))  # type: ignore[arg-type]


def registry_of(facts: Sequence[Fact]) -> dict[str, Fact]:
    return {f.id: f for f in facts}


async def briefing_step(agent: object, step: object) -> object:
    """The `briefing_today` run step (P-10's slot): one engagement's briefing for the run's
    initiator, on the firm's today. Arguments: `engagement_id`, `label`."""
    from abacus.kernel import clock
    from abacus.modules.agents.engagement_run import RunStepResult

    args = cast(dict[str, object], step.arguments)  # type: ignore[attr-defined]
    raw = args.get("engagement_id") or agent.engagement_id  # type: ignore[attr-defined]
    if raw is None:
        return RunStepResult("failed", "engagement_missing")
    built = await build_engagement_briefing(
        agent,
        agent.initiator,  # type: ignore[attr-defined] -- the viewer the run acts for (ADR-025)
        UUID(str(raw)),
        engagement_label=str(args.get("label") or ""),
        titles={},
        recommendations={},
        on=await clock.today(agent.tenant),  # type: ignore[attr-defined]
    )
    if built.status in ("ready", "unchanged"):
        return RunStepResult("succeeded", records_read=1)
    return RunStepResult("failed", built.status)


def register() -> None:
    from abacus.modules.agents.engagement_run import register_run_step

    register_run_step("briefing_today", briefing_step)  # type: ignore[arg-type]


__all__ = [
    "CAPABILITY",
    "PROMPT",
    "BriefingInput",
    "Built",
    "EngagementBriefing",
    "WhyLine",
    "briefing_step",
    "build_engagement_briefing",
    "input_of",
    "register",
    "registry_of",
    "validate",
]
