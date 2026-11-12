"""`tax.agreement_reader` v1: a partnership agreement and its assignments to a proposed allocation
structure with clause citations (T-05-T36; T-05 F5, §6.4; SPEC-651; ADR-019, ADR-050, ADR-052;
DEC-4621). Red zone (an agent path).

The model reads the agreement's clauses (id and text, inside an untrusted block: the client's
document is data, never instructions) and answers the structure's parameters, each with the
clause and the words it rests on. Code has the last word before anything is shown:

- **Citations.** A parameter is kept only when it cites a clause that was given and the quote is
  in that clause's text, verbatim (DE-3). An uncited or unverified parameter is dropped and
  counted, never shown.
- **Numbers.** Every number in a kept rung or transfer must appear in the given clauses; one that
  does not drops its parameter (number provenance, DE-3). Code computes every amount later
  (T-05-T41's preview); the reader proposes facts, never figures.
- **The §706(d) question.** Code reads the clauses for convention words. Silent (none) or
  conflicting (more than one) means the convention is not proposed and the question
  `convention` is raised for a person (TXP-06 d), whatever the model said.
- **Propose-only.** The output schema has no action field; the kept parameters become one
  `allocation_structure` proposal through C17's `tax.propose_allocation_structure`, which a
  manager approves at L3 (T-05-T41). The agent never approves, allocates or writes a structure.
- **Boundary.** `client_data: none` until T-05-T64's clearance; the partnership is the §7216
  subject (`entity_tri.entity_return_subjects`).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext

CAPABILITY: Final = "tax.agreement_reader"
PROPOSE_TOOL: Final = "tax.propose_allocation_structure"
MAX_CLAUSES: Final = 60
MAX_CLAUSE_CHARS: Final = 4000
Int = classified("internal")
Tri = classified("restricted", tri=True)
Kind = Literal["straight_percentage", "targeted_waterfall"]
Method = Literal["interim_closing", "proration"]
Convention = Literal["monthly", "semi_monthly", "calendar_day"]
Parameter = Literal["kind", "method", "convention", "rungs", "transfers"]
PARAMETERS: Final[tuple[Parameter, ...]] = ("kind", "method", "convention", "rungs", "transfers")
_NUMBER: Final = re.compile(r"\d+(?:\.\d+)?")
# The words a clause uses for each §706(d) convention (code's reading, not the model's).
_CONVENTIONS: Final[Mapping[Convention, re.Pattern[str]]] = {
    "monthly": re.compile(r"\bmonthly convention\b", re.IGNORECASE),
    "semi_monthly": re.compile(r"\bsemi-?monthly convention\b", re.IGNORECASE),
    "calendar_day": re.compile(r"\b(?:calendar[- ]day|daily) convention\b", re.IGNORECASE),
}


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class AgreementClause(BaseModel):
    model_config = _cfg()

    id: Annotated[str, Field(min_length=1, max_length=40, pattern=r"^[a-z0-9.\-]+$"), Int]
    text: Annotated[str, Field(min_length=1, max_length=MAX_CLAUSE_CHARS), Tri]


class ReadAgreementInput(BaseModel):
    """What the model is given: the agreement's and the assignments' clauses, nothing else."""

    model_config = _cfg()

    clauses: Annotated[list[AgreementClause], Field(min_length=1, max_length=MAX_CLAUSES), Tri]


class ClauseCitation(BaseModel):
    model_config = _cfg()

    clause: Annotated[str, Field(min_length=1, max_length=40), Int]
    quote: Annotated[str, Field(min_length=1, max_length=400), Tri]


class Rung(BaseModel):
    model_config = _cfg()

    rule: Annotated[Literal["return_of_capital", "preferred_return", "catch_up", "promote"], Int]
    rate: Annotated[str | None, Field(max_length=12), Tri] = None  # preferred return, percent
    target: Annotated[str | None, Field(max_length=12), Tri] = None  # catch-up target, percent
    share: Annotated[str | None, Field(max_length=12), Tri] = None  # catch-up share, percent
    gp: Annotated[str | None, Field(max_length=12), Tri] = None  # promote to the GP, percent


class Transfer(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    date: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$"), Tri]
    from_: Annotated[str, Field(alias="from", min_length=1, max_length=200), Tri]
    to: Annotated[str, Field(min_length=1, max_length=200), Tri]
    points: Annotated[str, Field(max_length=12), Tri]


class ReadAgreementOutput(BaseModel):
    """`tax.agreement_reader@v1`'s answer. No action field exists: the reader cannot ask for
    one (DE-5)."""

    model_config = _cfg()

    kind: Annotated[Kind | None, Int] = None
    method: Annotated[Method | None, Int] = None
    convention: Annotated[Convention | None, Int] = None
    rungs: Annotated[list[Rung], Field(max_length=8), Tri] = Field(default_factory=list[Rung])
    transfers: Annotated[list[Transfer], Field(max_length=20), Tri] = Field(
        default_factory=list[Transfer]
    )
    citations: Annotated[dict[Parameter, ClauseCitation], Tri] = Field(
        default_factory=dict[Parameter, ClauseCitation]
    )


@dataclass(frozen=True)
class Kept:
    parameter: Parameter
    value: object  # a string, or a list of rung or transfer dicts
    clause: str
    quote: str


@dataclass(frozen=True)
class Read:
    kept: tuple[Kept, ...]
    dropped: tuple[tuple[Parameter, str], ...]  # (parameter, reason code)
    question: Literal["convention"] | None

    def value(self, parameter: Parameter) -> object:
        return next((k.value for k in self.kept if k.parameter == parameter), None)


def conventions_in(clauses: Sequence[AgreementClause]) -> set[Convention]:
    """The §706(d) conventions the clauses name (code's reading)."""
    return {
        c for c, pattern in _CONVENTIONS.items() if any(pattern.search(x.text) for x in clauses)
    }


def _numbers(value: object) -> list[str]:
    if isinstance(value, list):
        out: list[str] = []
        for item in cast(list[dict[str, object]], value):
            for field, v in item.items():
                if field in ("rate", "target", "share", "gp", "points") and v is not None:
                    out.extend(_NUMBER.findall(str(v)))
                if field == "date" and v is not None:
                    year, _month, day = str(v).split("-")
                    out.extend([year, str(int(day))])  # the year and day the clause spells out
        return out
    return []


def _value_of(answer: ReadAgreementOutput, parameter: Parameter) -> object:
    if parameter == "rungs":
        return [r.model_dump(exclude_none=True) for r in answer.rungs] or None
    if parameter == "transfers":
        return [t.model_dump(by_alias=True) for t in answer.transfers] or None
    return getattr(answer, parameter)


def settle(answer: ReadAgreementOutput | None, given: ReadAgreementInput) -> Read:
    """Code's last word (module docstring): each proposed parameter verified or dropped."""
    texts = {c.id: c.text for c in given.clauses}
    corpus = set(_NUMBER.findall(" ".join(texts.values())))
    named = conventions_in(given.clauses)
    question: Literal["convention"] | None = None if len(named) == 1 else "convention"
    kept: list[Kept] = []
    dropped: list[tuple[Parameter, str]] = []
    if answer is None:
        return Read((), tuple((p, "refused") for p in PARAMETERS), question)
    for parameter in PARAMETERS:
        value = _value_of(answer, parameter)
        if value is None:
            continue
        if parameter == "convention" and question is not None:
            dropped.append((parameter, "convention_question"))
            continue
        if parameter == "convention" and value not in named:
            dropped.append((parameter, "convention_not_in_agreement"))
            continue
        cite = answer.citations.get(parameter)
        if cite is None:
            dropped.append((parameter, "uncited"))
            continue
        text = texts.get(cite.clause)
        if text is None or cite.quote not in text:
            dropped.append((parameter, "quote_not_in_clause"))
            continue
        if any(n not in corpus for n in _numbers(value)):
            dropped.append((parameter, "unsupported_number"))
            continue
        kept.append(Kept(parameter, value, cite.clause, cite.quote))
    return Read(tuple(kept), tuple(dropped), question)


@dataclass(frozen=True)
class ReaderResult:
    outcome: str  # proposed · nothing_to_propose · refused
    proposal_id: UUID | None
    read: Read


async def _judge(
    agent: AgentContext, given: ReadAgreementInput, return_id: UUID
) -> ReadAgreementOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2
    from abacus.modules.tax.entity_tri import entity_return_subjects

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder()
        .task(given.model_dump(), untrusted=("clauses",))  # the client's agreement text
        .subjects(*await entity_return_subjects(agent.tenant, return_id))
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=ReadAgreementOutput,
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
    except Exception:  # a refused call (boundary, budget, schema): nothing is proposed
        return None
    return cast(ReadAgreementOutput, result.output)


async def read_agreement(
    agent: AgentContext,
    return_id: UUID,
    client_entity_id: UUID,
    tax_year: int,
    clauses: Sequence[tuple[str, str]],
) -> ReaderResult:
    """One run over a return's agreement clauses: the model's reading, settled by code, as one
    proposal through C17 (module docstring)."""
    from abacus.modules.agents.api import ToolCallIn, call_tool

    given = ReadAgreementInput(
        clauses=[AgreementClause(id=i, text=t[:MAX_CLAUSE_CHARS]) for i, t in clauses]
    )
    answer = await _judge(agent, given, return_id)
    read = settle(answer, given)
    if answer is None:
        return ReaderResult("refused", None, read)
    if not read.kept and read.question is None:
        return ReaderResult("nothing_to_propose", None, read)
    proposed = await call_tool(
        agent,
        ToolCallIn(
            run_id=agent.agent_run_id,
            step_seq=1,
            attempt=1,
            name=PROPOSE_TOOL,
            arguments={
                "client_entity_id": str(client_entity_id),
                "tax_year": tax_year,
                "return_id": str(return_id),
                "parameters": [
                    {
                        "parameter": k.parameter,
                        "value": k.value,
                        "clause": k.clause,
                        "quote": k.quote,
                    }
                    for k in read.kept
                ],
                "question": read.question,
            },
        ),
    )
    if not proposed.ok:
        return ReaderResult("refused", None, read)
    proposal = UUID(str(cast(dict[str, object], proposed.result)["proposal_id"]))
    return ReaderResult("proposed", proposal, read)


__all__ = [
    "CAPABILITY",
    "PARAMETERS",
    "PROPOSE_TOOL",
    "AgreementClause",
    "ClauseCitation",
    "Kept",
    "Read",
    "ReadAgreementInput",
    "ReadAgreementOutput",
    "ReaderResult",
    "conventions_in",
    "read_agreement",
    "settle",
]
