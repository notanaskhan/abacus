"""`decisions.recommender` modes `convention_706d` and `section_754` (T-05-T49; T-05 F10, §6.4;
SPEC-651; ADR-050, ADR-052, ADR-005; DEC-4709). Red (agent). The materiality mode
(`decision_recommend.py`, PROTECTED) is unchanged; these modes share its output shape
(`DecisionSuggestion`: one option key and up to three reasons by fact reference) and its rules.

- **Options from code.** The owner (tax) computes the options and the facts: the §706(d)
  conventions with the day each closes the books (Reg. §1.706-4(c)); elect and do not elect for
  §754 with the transfer and the §743(b) placeholder. The model is given them, and the
  agreement's clauses inside an untrusted block.
- **Code checks the answer** before anything is shown: the key is one of the computed options;
  every reason names facts the context listed; every number it prints is one of the facts'
  figures; no reason claims a person's act (elected, filed, decided, approved, signed); a
  `convention_706d` answer cites at least one of the agreement's clauses when there are any.
- **One call**, single-shot, through the gateway with the mode's prompt
  (`decisions.recommend.<mode>@v1`), the recommender's tier and budget. A refused or failed call
  leaves the card or question without a recommendation; a person decides either way (the agent
  is denied `decision.decide`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Literal
from uuid import UUID

from abacus.ai_gateway import AssembledContext, Attribution, ContextBuilder, GatewayCall, call
from abacus.modules.agents.decision_recommend import (
    CLAIMED_ACT,
    NO_PROVENANCE,
    OUTSIDE_SET,
    RECOMMENDER,
    UNKNOWN_FACT,
    numbers_in,
)
from abacus.modules.agents.handoff import DecisionSuggestion
from abacus.modules.agents.spec import spec

Mode = Literal["convention_706d", "section_754"]
MODES: Final[tuple[Mode, ...]] = ("convention_706d", "section_754")
MISSING_CITATION: Final = "agreement_not_cited"
_RESERVED: Final = re.compile(
    r"\b(?:elected|filed|decided|approved|signed(?: off)?|agreed)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class ModeOption:
    key: str
    label: str


@dataclass(frozen=True)
class ModeFact:
    ref: str  # "fact:transfer_date"
    label: str
    value: str  # code's figure or date, as text


@dataclass(frozen=True)
class ModeClause:
    ref: str  # "clause:assignment_3"
    label: str  # "Assignment §3"
    text: str  # the client's words (untrusted)


@dataclass(frozen=True)
class ModeFacts:
    mode: Mode
    options: tuple[ModeOption, ...]
    facts: tuple[ModeFact, ...]
    clauses: tuple[ModeClause, ...] = ()


def refs_of(facts: ModeFacts) -> frozenset[str]:
    return frozenset(
        {f"option:{o.key}" for o in facts.options}
        | {f.ref for f in facts.facts}
        | {c.ref for c in facts.clauses}
    )


def figures_of(facts: ModeFacts) -> frozenset[Decimal]:
    out: set[Decimal] = set()
    for f in facts.facts:
        for n in numbers_in(f.value):
            out.add(n)
        try:
            out.add(Decimal(f.value.replace(",", "")).normalize())
        except InvalidOperation:
            continue
    return frozenset(out)


def check(answer: DecisionSuggestion, facts: ModeFacts) -> str | None:
    """None when code accepts the answer; else why it is not shown."""
    if answer.recommended_option_key not in {o.key for o in facts.options}:
        return OUTSIDE_SET
    refs = refs_of(facts)
    figures = figures_of(facts)
    cited_clause = False
    for reason in answer.reasons:
        if not set(reason.facts) <= refs:
            return UNKNOWN_FACT
        if not numbers_in(reason.text) <= figures:
            return NO_PROVENANCE
        if _RESERVED.search(reason.text):
            return CLAIMED_ACT
        cited_clause = cited_clause or any(f.startswith("clause:") for f in reason.facts)
    if facts.mode == "convention_706d" and facts.clauses and not cited_clause:
        return MISSING_CITATION
    return None


def build_context(facts: ModeFacts) -> AssembledContext:
    return (
        ContextBuilder()
        .task(
            {
                "mode": facts.mode,
                "options": [
                    {"ref": f"option:{o.key}", "key": o.key, "label": o.label}
                    for o in facts.options
                ],
                "facts": [{"ref": f.ref, "label": f.label, "value": f.value} for f in facts.facts],
                "clauses": [
                    {"ref": c.ref, "label": c.label, "text": c.text} for c in facts.clauses
                ],
            },
            untrusted=["clauses"],
        )
        .build()
    )


def prompt_of(mode: Mode) -> str:
    return f"decisions.recommend.{mode}@v1"


@dataclass(frozen=True)
class ModeOutcome:
    suggestion: DecisionSuggestion | None
    refused: str | None  # why nothing is shown (a code check or `gateway_refused`)


async def recommend_mode(attribution: Attribution, facts: ModeFacts) -> ModeOutcome:
    """One gateway call for the mode, settled by code (module docstring)."""
    recommender = spec(RECOMMENDER)
    try:
        result = await call(
            GatewayCall(
                purpose=recommender.purpose,
                prompt=prompt_of(facts.mode),
                tier=recommender.tier,
                output_schema=DecisionSuggestion,
                budget_usd=recommender.limits.max_cost_usd,
                attribution=attribution,
                context=build_context(facts),
                work_class=recommender.work_class,
                essential=recommender.essential,
                routes=recommender.routes,
                cheaper_tiers=recommender.cheaper_tiers,
                max_output_tokens=recommender.limits.max_output_tokens,
                timeout_seconds=recommender.limits.max_seconds,
            )
        )
    except Exception:  # a refused call (consent, boundary, budget, schema)
        return ModeOutcome(None, "gateway_refused")
    answer = result.output
    if not isinstance(answer, DecisionSuggestion):
        return ModeOutcome(None, "gateway_refused")
    reason = check(answer, facts)
    return ModeOutcome(None, reason) if reason is not None else ModeOutcome(answer, None)


def attribution_for(
    tenant: object, engagement_id: UUID | None, run_id: UUID | None
) -> Attribution:
    return Attribution(tenant, engagement_id, RECOMMENDER, run_id)  # type: ignore[arg-type]


__all__ = [
    "MISSING_CITATION",
    "MODES",
    "Mode",
    "ModeClause",
    "ModeFact",
    "ModeFacts",
    "ModeOption",
    "ModeOutcome",
    "attribution_for",
    "build_context",
    "check",
    "figures_of",
    "prompt_of",
    "recommend_mode",
    "refs_of",
]
