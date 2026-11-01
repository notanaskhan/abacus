"""The materiality recommender (A-04-T15; A-04 §6.1; SPEC-620; DEC-1953). PROTECTED.

`decisions.recommender`: when a manager or senior proposes materiality with a recommendation,
one agent run on their behalf reads the facts code computed (the options with their thresholds,
the benchmark, the firm's range, the prior years) and the qualitative factors (untrusted, ADR-052),
and makes one gateway call with `decisions.recommend@v1`. Code then checks the answer before
anything is shown (ADR-050, INV-1):

- the key is one of the computed options, its rate inside the firm's range, never "custom";
- every reason names facts the context listed, and every number it prints is one of them;
- no reason claims the partner's act.

An accepted answer becomes the agent's suggestion on the work item's materiality (the card's
`recommendation_suggestion_id`) and the agent raises the `planning_materiality` card through its
task scope with that tag; the engagement partner still decides (the agent is denied
`decision.decide` at every layer). A refused answer, a gateway failure or no available model
leaves the card to be raised untagged by the proposer; the run ends escalated with the reason.

The plan names a `DecisionRecommendWorkflow` (interactive class); this runs in the proposer's
request as one single call, so there is no workflow to version yet (DEC-1953).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Awaitable, Callable
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
    fake_responds,
    is_synthetic,
)
from abacus.ai_gateway.routes import route_enabled
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.agents.handoff import DecisionSuggestion
from abacus.modules.agents.proposals import create_suggestion
from abacus.modules.agents.repository import finish_run, insert_run
from abacus.modules.agents.service import (
    _reader,  # pyright: ignore[reportPrivateUsage] -- the module's own system reader
    fail_run,
    load_agent_context,
)
from abacus.modules.agents.spec import spec
from abacus.modules.agents.stages import starts_in_shadow
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AgentContext, AuthContext, authorise

RECOMMENDER: Final = "decisions.recommender"
SUGGESTION_TARGET: Final = "materiality"
SUGGESTION_FIELD: Final = "option_key"
_NUMBER: Final = re.compile(r"\d[\d,]*(?:\.\d+)?")
# Citation tokens and labels whose digits are names, not figures (the suite's rule).
_NOT_FIGURES: Final = re.compile(
    r"\b[A-Z]{2,}(?:-[A-Z]+)*-\d+\b|\bstep \d+\b|\bAU-C \d+\b|\bPY\d{4}\b|§[\d()a-zA-Z.]+|"
    r"\b(?:19|20)\d{2}\b"
)
_ACT: Final = re.compile(r"\b(?:approved|decided|agreed|signed off)\b", re.I)
# Why a recommendation was not shown (the run's escalation reason).
OUTSIDE_SET: Final = "key_not_in_option_set"
OUTSIDE_RANGE: Final = "key_outside_policy_range"
UNKNOWN_FACT: Final = "unknown_fact"
NO_PROVENANCE: Final = "number_without_provenance"
CLAIMED_ACT: Final = "claims_partner_act"


@dataclass(frozen=True)
class OptionFact:
    key: str
    rate_pct: Decimal
    overall: Decimal
    pm: Decimal
    ct: Decimal
    pm_pct: Decimal
    ct_pct: Decimal


@dataclass(frozen=True)
class PriorFact:
    year: str
    amount: Decimal
    rate_used_pct: Decimal | None


@dataclass(frozen=True)
class RecommendFacts:
    """What code computed for the card (the materiality service's options and record)."""

    benchmark_key: str
    benchmark_label: str
    benchmark_amount: Decimal
    policy_low_pct: Decimal
    policy_high_pct: Decimal
    options: tuple[OptionFact, ...]
    priors: tuple[PriorFact, ...] = ()
    factors: tuple[tuple[str, bool], ...] = ()


@dataclass(frozen=True)
class Recommended:
    run_id: UUID
    option_key: str
    suggestion_id: UUID
    card_id: UUID
    reasons: tuple[str, ...]


# The raise the caller performs as the agent once the answer is accepted: (agent, key,
# suggestion) -> card id. The materiality service owns the card's options (its provider).
RaiseCard = Callable[[AgentContext, str, UUID], Awaitable[UUID]]


def model_available() -> bool:
    """A real route the recommender may use is enabled, or the fake route with a responder for
    its prompt (local and test only)."""
    recommender = spec(RECOMMENDER)
    if any(route_enabled(r) for r in recommender.routes):
        return True
    return route_enabled("fake") and fake_responds(recommender.prompt)


def _figures(facts: RecommendFacts) -> frozenset[Decimal]:
    found: set[Decimal] = {facts.benchmark_amount, facts.policy_low_pct, facts.policy_high_pct}
    for o in facts.options:
        found |= {o.rate_pct, o.overall, o.pm, o.ct, o.pm_pct, o.ct_pct}
    for p in facts.priors:
        found.add(p.amount)
        if p.rate_used_pct is not None:
            found.add(p.rate_used_pct)
    return frozenset(v.normalize() for v in found)


def refs_of(facts: RecommendFacts) -> frozenset[str]:
    refs = {"benchmark_key", "benchmark_amount", "policy"}
    refs |= {f"option:{o.key}" for o in facts.options}
    refs |= {f"factor:{i}" for i in range(len(facts.factors))}
    refs |= {f"prior:{p.year}" for p in facts.priors}
    return frozenset(refs)


def numbers_in(text: str) -> set[Decimal]:
    out: set[Decimal] = set()
    for raw in _NUMBER.findall(_NOT_FIGURES.sub(" ", unicodedata.normalize("NFKC", text))):
        try:
            out.add(Decimal(raw.replace(",", "")).normalize())
        except InvalidOperation:
            continue
    return out


def check(answer: DecisionSuggestion, facts: RecommendFacts) -> str | None:
    """None when code accepts the answer; else why it is not shown (the run's reason)."""
    by_key = {o.key: o for o in facts.options}
    chosen = by_key.get(answer.recommended_option_key)
    if chosen is None:
        return OUTSIDE_SET
    if not facts.policy_low_pct <= chosen.rate_pct <= facts.policy_high_pct:
        return OUTSIDE_RANGE
    refs = refs_of(facts)
    figures = _figures(facts)
    for reason in answer.reasons:
        if not set(reason.facts) <= refs:
            return UNKNOWN_FACT
        if not numbers_in(reason.text) <= figures:
            return NO_PROVENANCE
        if _ACT.search(reason.text):
            return CLAIMED_ACT
    return None


def build_context(facts: RecommendFacts) -> AssembledContext:
    return (
        ContextBuilder()
        .task(
            {
                "benchmark": {
                    "ref": "benchmark_key",
                    "key": facts.benchmark_key,
                    "label": facts.benchmark_label,
                    "amount_ref": "benchmark_amount",
                    "amount": format(facts.benchmark_amount, "f"),
                },
                "policy": {
                    "ref": "policy",
                    "low_pct": format(facts.policy_low_pct, "f"),
                    "high_pct": format(facts.policy_high_pct, "f"),
                },
                "options": [
                    {
                        "ref": f"option:{o.key}",
                        "key": o.key,
                        "rate_pct": format(o.rate_pct, "f"),
                        "overall": format(o.overall, "f"),
                        "pm_pct": format(o.pm_pct, "f"),
                        "pm": format(o.pm, "f"),
                        "ct_pct": format(o.ct_pct, "f"),
                        "ct": format(o.ct, "f"),
                    }
                    for o in facts.options
                ],
                "prior_years": [
                    {
                        "ref": f"prior:{p.year}",
                        "amount": format(p.amount, "f"),
                        "rate_used_pct": None
                        if p.rate_used_pct is None
                        else format(p.rate_used_pct, "f"),
                    }
                    for p in facts.priors
                ],
                "factors": [
                    {"ref": f"factor:{i}", "text": text, "applies": applies}
                    for i, (text, applies) in enumerate(facts.factors)
                ],
            },
            untrusted=["factors"],
        )
        .build()
    )


async def consult_model(
    attribution: Attribution, facts: RecommendFacts
) -> tuple[DecisionSuggestion | None, AssembledContext]:
    """One model call through the gateway (the product run and the evaluation share it)."""
    recommender = spec(RECOMMENDER)
    context = build_context(facts)
    result = await call(
        GatewayCall(
            purpose=recommender.purpose,
            prompt=recommender.prompt,
            tier=recommender.tier,
            output_schema=DecisionSuggestion,
            budget_usd=recommender.limits.max_cost_usd,
            attribution=attribution,
            context=context,
            work_class=recommender.work_class,
            essential=recommender.essential,
            routes=recommender.routes,
            cheaper_tiers=recommender.cheaper_tiers,
            max_output_tokens=recommender.limits.max_output_tokens,
            timeout_seconds=recommender.limits.max_seconds,
        )
    )
    return result.output, context


async def _start(person: AuthContext, engagement_id: UUID) -> UUID | None:
    recommender = spec(RECOMMENDER)
    reader = _reader(person.tenant_id, f"agents:{recommender.id}")
    run_id: UUID | None = None
    try:
        async with uow(reader) as tx:
            run_id = await insert_run(
                tx.session,
                tenant_id=person.tenant_id,
                agent_id=recommender.id,
                shadow=await starts_in_shadow(tx.session, reader, recommender.id),
                spec_version=recommender.version,
                engagement_id=engagement_id,
                evidence_version_id=None,
                initiator_user_id=person.user_id,
                source_event_id=uuid4(),
                task_scope=sorted(recommender.task_scope),
            )
            if run_id is not None:
                tx.record(
                    "agent_run.started",
                    target=Target("agent_run", run_id),
                    after=Ref(initiator=person.user_id),
                )
    except MissingAuditEvent:
        pass
    return run_id


async def recommend(
    person: AuthContext,
    *,
    engagement_id: UUID,
    work_item_id: UUID,
    facts: RecommendFacts,
    raise_card: RaiseCard,
) -> Recommended | None:
    """The recommendation run on behalf of `person` (who authorised `materiality.propose`);
    None when no model is available, the firm is not synthetic (`client_data: none`), or code
    refused the answer (the run says why)."""
    if not model_available() or not await is_synthetic(person.tenant):
        return None
    run_id = await _start(person, engagement_id)
    if run_id is None:
        return None
    agent = await load_agent_context(person.tenant_id, run_id)
    engagement = await get_ref(agent, engagement_id)
    await authorise(agent, "materiality.read", engagement.resource())
    try:
        answer, context = await consult_model(
            Attribution(agent.tenant, engagement_id, RECOMMENDER, run_id), facts
        )
    except Exception:
        await fail_run(person.tenant_id, run_id, "gateway_error")
        return None
    reason = OUTSIDE_SET if answer is None else check(answer, facts)
    if answer is None or reason is not None:
        async with uow(agent.tenant) as tx:
            if await finish_run(
                tx.session,
                run_id,
                status="escalated",
                context_hash=context.sha256,
                output={"refused": reason or OUTSIDE_SET},
            ):
                tx.record("agent_run.escalated", target=Target("agent_run", run_id))
        return None
    suggestion = await create_suggestion(
        agent,
        engagement_id=engagement_id,
        target_type=SUGGESTION_TARGET,
        target_id=work_item_id,
        field_key=SUGGESTION_FIELD,
        proposed_value={"t": "text", "v": answer.recommended_option_key},
    )
    card_id = await raise_card(agent, answer.recommended_option_key, suggestion)
    async with uow(agent.tenant) as tx:
        if await finish_run(
            tx.session,
            run_id,
            status="completed",
            context_hash=context.sha256,
            output={**answer.model_dump(mode="json"), "card_id": str(card_id)},
        ):
            tx.record(
                "agent_run.completed",
                target=Target("agent_run", run_id),
                after=Ref(card=card_id, suggestion=suggestion),
            )
    return Recommended(
        run_id,
        answer.recommended_option_key,
        suggestion,
        card_id,
        tuple(r.text for r in answer.reasons),
    )


def fake_recommend(request: ModelRequest) -> str:
    """The fake model's answer, read from the task by code (local runs and tests only): the
    option at the range's midpoint, else the lowest in range, with reasons by reference."""
    task = cast(
        dict[str, Any],  # Any: JSON
        json.loads(request.user.split("## task\n", 1)[1].split("\n", 1)[0]),
    )
    policy = cast(dict[str, str], task["policy"])
    low, high = Decimal(policy["low_pct"]), Decimal(policy["high_pct"])
    options = [(str(o["key"]), Decimal(str(o["rate_pct"]))) for o in task["options"]]
    inside = [(k, r) for k, r in options if low <= r <= high]
    mid = (low + high) / 2
    key = next((k for k, r in inside if r == mid), inside[0][0] if inside else "custom")
    return json.dumps(
        {
            "recommended_option_key": key,
            "reasons": [
                {
                    "text": "The benchmark is the firm's default for this kind of audit.",
                    "facts": ["benchmark_key", "policy"],
                },
                {
                    "text": "This option sits in the middle of the firm's range.",
                    "facts": [f"option:{key}", "policy"],
                },
            ],
        }
    )
