"""`ledger.tb_mapper` v1: a group entity's trial balance accounts to the firm's FS-line catalogue
(A-09-T29; A-09 §6; SPEC-658 F1; ADR-019, ADR-050, ADR-052; DEC-5409). Red zone (an agent path).

The model sees each account's code and name (anything that reads as an amount redacted), the
entity, and code's facts (the balance side, last year's line for the code), never a figure. Code
has the last word:

- **Catalogue.** A suggestion whose line is not in the published catalogue is an abstention; so
  is a missing or repeated account, a confidence word outside high, medium and low, or reasoning
  over 140 characters. Low confidence is kept but marked, so a person sees it as Needs review.
- **Suggestions.** Kept lines become suggestions on the mapping set through C17's
  `assurance.suggest_account_mappings`; adopting one is a person's edit on AUD-31 and confirming
  the set (across every entity of the group) is a person's sign-off. The agent never maps.
- **Boundary.** `client_data: none` until cleared: the gateway refuses a real firm's client data,
  so the capability runs on synthetic firms and the evals.
- **Rerun.** "Request changes" on AUD-31 starts the capability again on the accounts still
  unmapped or marked Needs review.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext, AuthContext

CAPABILITY: Final = "ledger.tb_mapper"
PROPOSE_TOOL: Final = "assurance.suggest_account_mappings"
SUGGESTION_TARGET: Final = "account_mapping"
MAX_ACCOUNTS: Final = 300
MAX_REASONING: Final = 140
Int = classified("internal")
Conf = classified("confidential")
Confidence = Literal["high", "medium", "low"]
_AMOUNT: Final = re.compile(
    r"[$€£]\s?-?\d[\d,]*(?:\.\d+)?|\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|-?\d+\.\d{2}\b|\b\d{5,}\b"
)


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class TbAccount(BaseModel):
    model_config = _cfg()

    code: Annotated[str, Field(min_length=1, max_length=40), Conf]
    name: Annotated[str, Field(min_length=1, max_length=200), Conf]
    entity: Annotated[str, Field(min_length=1, max_length=200), Conf]
    balance_side: Annotated[Literal["debit", "credit", "zero"], Int]
    prior_line_id: Annotated[str | None, Field(max_length=120), Int] = None


class CatalogueLine(BaseModel):
    model_config = _cfg()

    line_id: Annotated[str, Field(min_length=1, max_length=120), Int]
    caption: Annotated[str, Field(min_length=1, max_length=200), Int]


class TbMapperInput(BaseModel):
    """What the model is given: codes, names, entity and code's facts; no amount field exists."""

    model_config = _cfg()

    accounts: Annotated[list[TbAccount], Field(min_length=1, max_length=MAX_ACCOUNTS), Conf]
    catalogue: Annotated[list[CatalogueLine], Field(min_length=1, max_length=1000), Int]


class TbSuggestion(BaseModel):
    model_config = _cfg()

    code: Annotated[str, Field(min_length=1, max_length=40), Conf]
    line_id: Annotated[str | None, Field(max_length=120), Int] = None
    confidence: Annotated[str, Field(max_length=10), Int] = "low"
    reasoning: Annotated[str, Field(max_length=400), Conf] = ""


class TbMapperOutput(BaseModel):
    """`ledger.tb_mapper@v1`'s answer: one suggestion per account (or abstention)."""

    model_config = _cfg()

    suggestions: Annotated[list[TbSuggestion], Field(max_length=MAX_ACCOUNTS), Conf]


@dataclass(frozen=True)
class Kept:
    code: str
    line_id: str
    confidence: Confidence
    reasoning: str


@dataclass(frozen=True)
class Settled:
    kept: tuple[Kept, ...]
    abstained: tuple[tuple[str, str], ...]  # (account code, reason code)


def redact_amounts(name: str) -> str:
    return _AMOUNT.sub("[amount]", name)


def model_input(
    accounts: Sequence[tuple[str, str, str, str, str | None]],
    catalogue: Sequence[tuple[str, str]],
) -> TbMapperInput:
    """(code, name, entity, balance side, prior line id) per account, unique by code, names
    redacted; the catalogue by id."""
    seen: dict[str, TbAccount] = {}
    for code, name, entity, side, prior in accounts:
        if code not in seen:
            seen[code] = TbAccount(
                code=code,
                name=redact_amounts(name),
                entity=entity,
                balance_side=cast(Literal["debit", "credit", "zero"], side),
                prior_line_id=prior,
            )
    lines = {line_id: caption for line_id, caption in catalogue}
    return TbMapperInput(
        accounts=list(seen.values()),
        catalogue=[CatalogueLine(line_id=k, caption=v) for k, v in sorted(lines.items())],
    )


def settle(answer: TbMapperOutput | None, given: TbMapperInput) -> Settled:
    """Code's last word (module docstring): every given account is kept or abstained, once."""
    catalogue = {line.line_id for line in given.catalogue}
    answered: dict[str, TbSuggestion] = {}
    repeated: set[str] = set()
    for s in answer.suggestions if answer is not None else ():
        if s.code in answered:
            repeated.add(s.code)
        answered.setdefault(s.code, s)
    kept: list[Kept] = []
    abstained: list[tuple[str, str]] = []
    for account in given.accounts:
        s = answered.get(account.code)
        if s is None:
            abstained.append((account.code, "no_answer"))
        elif account.code in repeated:
            abstained.append((account.code, "answered_twice"))
        elif s.line_id is None:
            abstained.append((account.code, "abstained"))
        elif s.line_id not in catalogue:
            abstained.append((account.code, "line_not_in_catalogue"))
        elif s.confidence not in ("high", "medium", "low"):
            abstained.append((account.code, "confidence_word_invalid"))
        elif len(s.reasoning) > MAX_REASONING:
            abstained.append((account.code, "reasoning_too_long"))
        else:
            kept.append(
                Kept(account.code, s.line_id, s.confidence, s.reasoning.strip())
            )
    return Settled(tuple(kept), tuple(abstained))


@dataclass(frozen=True)
class SuggestResult:
    outcome: Literal["suggested", "nothing_to_suggest", "refused", "unavailable"]
    suggestions: int
    abstained: tuple[tuple[str, str], ...]


async def _judge(agent: AgentContext, given: TbMapperInput) -> TbMapperOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder()
        .task(given.model_dump(), untrusted=("accounts",))  # names from the client's books
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=TbMapperOutput,
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
    except Exception:  # a refused call (boundary, budget, schema): nothing is suggested
        return None
    return cast(TbMapperOutput, result.output)


async def suggest_for(
    agent: AgentContext, mapping_set_id: UUID, given: TbMapperInput
) -> SuggestResult:
    """One run over the given accounts: the model's suggestions, settled by code, through C17."""
    from abacus.modules.agents.api import ToolCallIn, call_tool

    answer = await _judge(agent, given)
    if answer is None:
        return SuggestResult("refused", 0, tuple((a.code, "refused") for a in given.accounts))
    settled = settle(answer, given)
    if not settled.kept:
        return SuggestResult("nothing_to_suggest", 0, settled.abstained)
    done = await call_tool(
        agent,
        ToolCallIn(
            run_id=agent.agent_run_id,
            step_seq=1,
            attempt=1,
            name=PROPOSE_TOOL,
            arguments={
                "mapping_set_id": str(mapping_set_id),
                "suggestions": [
                    {
                        "account_code": k.code,
                        "line_id": k.line_id,
                        "confidence": k.confidence,
                        "reasoning": k.reasoning,
                    }
                    for k in settled.kept
                ],
            },
        ),
    )
    if not done.ok:
        return SuggestResult("refused", 0, settled.abstained)
    return SuggestResult("suggested", len(settled.kept), settled.abstained)


async def _inputs(
    person: AuthContext, mapping_set_id: UUID, *, only_open: bool
) -> tuple[UUID, TbMapperInput] | None:
    """Code's inputs from the mapping set: each account's code, name, the entity, the side its
    balance sits on and the line last year's mapping gave the code (never a figure)."""
    from abacus.kernel.db import tenant_session
    from abacus.modules.engagements.api import get_ref
    from abacus.modules.identity.api import authorise
    from abacus.modules.ledger import api as ledger
    from abacus.modules.organisations.api import client_names

    found = await ledger.mapping_set_by_id(person.tenant, mapping_set_id)
    if found is None:
        return None
    await authorise(
        person, "mapping_set.run", (await get_ref(person, found.engagement_id)).resource()
    )
    view = await ledger.mapping_view(person.tenant, found.engagement_id, found.trial_balance_id)
    if view is None:
        return None
    tb = await ledger.trial_balance_view(
        person.tenant, found.engagement_id, found.trial_balance_id
    )
    entity_id = tb.summary.client_entity_id
    entity = ""
    if entity_id is not None:
        async with tenant_session(person.tenant) as session:
            names = await client_names(session, [entity_id])
        entity = names[entity_id].client_entity_name if entity_id in names else ""
    key_of = {line.id: line.key for g in view.groupings for line in g.lines}
    rows: list[tuple[str, str, str, str, str | None]] = []
    for a in view.accounts:
        if only_open and a.fs_line_id is not None and a.method != "prior_year":
            continue
        side = "debit" if a.eoy > 0 else "credit" if a.eoy < 0 else "zero"
        prior = key_of.get(a.fs_line_id) if a.method == "prior_year" and a.fs_line_id else None
        rows.append((a.account_code, a.account_name, entity or "Entity", side, prior))
    if not rows:
        return None
    catalogue = [(line.key, line.label) for g in view.groupings for line in g.lines]
    return found.engagement_id, model_input(rows, catalogue)


async def run_suggestions(
    person: AuthContext, mapping_set_id: UUID, *, only_open: bool = False
) -> SuggestResult:
    """AUD-31 "Suggest with the agent" (and "Request changes", `only_open`): a person's run;
    None of it maps anything. Synthetic firms only until the boundary is cleared."""
    from abacus.ai_gateway import is_synthetic
    from abacus.modules.agents.api import end_capability_run, start_capability_run
    from abacus.modules.identity.api import Forbidden

    if person.tenant.actor_kind != "human" or person.client or person.is_support:
        raise Forbidden("mapping_set.run", "role")
    if not await is_synthetic(person.tenant):
        return SuggestResult("unavailable", 0, ())
    found = await _inputs(person, mapping_set_id, only_open=only_open)
    if found is None:
        return SuggestResult("nothing_to_suggest", 0, ())
    engagement_id, given = found
    agent = await start_capability_run(person, CAPABILITY, engagement_id)
    if agent is None:
        return SuggestResult("refused", 0, ())
    result = await suggest_for(agent, mapping_set_id, given)
    await end_capability_run(
        agent,
        status="succeeded" if result.outcome == "suggested" else "escalated",
        output={"suggestions": result.suggestions, "abstained": len(result.abstained)},
    )
    return result


__all__ = [
    "CAPABILITY",
    "PROPOSE_TOOL",
    "SuggestResult",
    "TbMapperInput",
    "TbMapperOutput",
    "model_input",
    "redact_amounts",
    "run_suggestions",
    "settle",
]
