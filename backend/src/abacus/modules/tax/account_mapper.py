"""`tax.account_mapper` v1: an entity return's accounts to published Form 1065 line keys
(T-05-T23; T-05 §6; SPEC-651; ADR-019, ADR-050, ADR-052; DEC-4406). Red zone (an agent path).

The model sees each account's code and name, never an amount (code removes anything that reads as
one from a name), and the published key set. Code has the last word:

- **Keys.** A mapping whose key is not in the published set is an abstention; so is a missing or
  repeated account, a confidence outside 0 to 1, or one under `MIN_CONFIDENCE`. An abstention
  proposes nothing and is counted for the preparer.
- **Proposals.** The kept mappings become one `tax_account_mapping` proposal through C17's
  `tax.propose_account_mappings` (a person approves it in SHL-10; the mapping is applied by
  ledger's `form_line_key`, T-05-T26); the agent never writes a mapping.
- **Boundary.** The capability is `client_data: none` until cleared: the gateway refuses a real
  firm's client data (SPEC-036), so it runs on synthetic firms and the evals until clearance.
  The partnership is the §7216 subject (`entity_tri.entity_return_subjects`).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Final, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext

CAPABILITY: Final = "tax.account_mapper"
PROPOSE_TOOL: Final = "tax.propose_account_mappings"
MAX_ACCOUNTS: Final = 200
MIN_CONFIDENCE: Final = 0.5
Int = classified("internal")
Tri = classified("restricted", tri=True)
# What reads as an amount in a name: a currency sign or a grouped or decimal number. Account codes
# travel apart; a bare number of up to four digits stays (it names a form, a year or a line).
_AMOUNT: Final = re.compile(
    r"[$€£]\s?-?\d[\d,]*(?:\.\d+)?|\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|-?\d+\.\d{2}\b|\b\d{5,}\b"
)


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class MapAccount(BaseModel):
    model_config = _cfg()

    code: Annotated[str, Field(min_length=1, max_length=40), Tri]
    name: Annotated[str, Field(min_length=1, max_length=200), Tri]


class MapAccountsInput(BaseModel):
    """What the model is given: codes and names (no amount field exists) and the keys."""

    model_config = _cfg()

    accounts: Annotated[list[MapAccount], Field(min_length=1, max_length=MAX_ACCOUNTS), Tri]
    published_keys: Annotated[list[str], Field(min_length=1, max_length=500), Int]


class MappedAccount(BaseModel):
    model_config = _cfg()

    code: Annotated[str, Field(min_length=1, max_length=40), Tri]
    key: Annotated[str | None, Field(max_length=40), Int] = None
    confidence: Annotated[float, Int] = 0.0


class MapAccountsOutput(BaseModel):
    """`tax.map_accounts@v1`'s answer: one mapping per account (or abstention)."""

    model_config = _cfg()

    mappings: Annotated[list[MappedAccount], Field(max_length=MAX_ACCOUNTS), Tri]


@dataclass(frozen=True)
class Mapping:
    code: str
    key: str
    confidence: float


@dataclass(frozen=True)
class Settled:
    kept: tuple[Mapping, ...]
    abstained: tuple[tuple[str, str], ...]  # (account code, reason code)


def redact_amounts(name: str) -> str:
    """The name with anything that reads as an amount replaced (ADR-050: the model never sees
    a figure to compute on)."""
    return _AMOUNT.sub("[amount]", name)


def model_input(accounts: Sequence[tuple[str, str]], published: Sequence[str]) -> MapAccountsInput:
    """The model's whole input: unique codes in the given order, names redacted."""
    seen: dict[str, MapAccount] = {}
    for code, name in accounts:
        if code not in seen:
            seen[code] = MapAccount(code=code, name=redact_amounts(name))
    return MapAccountsInput(
        accounts=list(seen.values()), published_keys=sorted(dict.fromkeys(published))
    )


def settle(
    answer: MapAccountsOutput | None, given: MapAccountsInput, *, minimum: float = MIN_CONFIDENCE
) -> Settled:
    """Code's last word (module docstring): every given account is kept or abstained, once."""
    published = frozenset(given.published_keys)
    answered: dict[str, MappedAccount] = {}
    repeated: set[str] = set()
    for m in answer.mappings if answer is not None else ():
        if m.code in answered:
            repeated.add(m.code)
        answered.setdefault(m.code, m)
    kept: list[Mapping] = []
    abstained: list[tuple[str, str]] = []
    for account in given.accounts:
        m = answered.get(account.code)
        if m is None:
            abstained.append((account.code, "no_answer"))
        elif account.code in repeated:
            abstained.append((account.code, "answered_twice"))
        elif m.key is None:
            abstained.append((account.code, "abstained"))
        elif m.key not in published:
            abstained.append((account.code, "key_not_published"))
        elif not 0.0 <= m.confidence <= 1.0:
            abstained.append((account.code, "confidence_out_of_range"))
        elif m.confidence < minimum:
            abstained.append((account.code, "low_confidence"))
        else:
            kept.append(Mapping(account.code, m.key, m.confidence))
    return Settled(tuple(kept), tuple(abstained))


@dataclass(frozen=True)
class MapResult:
    outcome: str  # proposed · nothing_to_propose · refused
    proposal_id: UUID | None
    kept: int
    abstained: tuple[tuple[str, str], ...]


async def _judge(
    agent: AgentContext, given: MapAccountsInput, return_id: UUID
) -> MapAccountsOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2
    from abacus.modules.tax.entity_tri import entity_return_subjects

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder()
        .task(given.model_dump(), untrusted=("accounts",))  # names from the client's books
        .subjects(*await entity_return_subjects(agent.tenant, return_id))
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=MapAccountsOutput,
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
    return cast(MapAccountsOutput, result.output)


async def map_accounts(
    agent: AgentContext,
    return_id: UUID,
    client_entity_id: UUID,
    tax_year: int,
    accounts: Sequence[tuple[str, str]],
    published: Sequence[str],
) -> MapResult:
    """One run of the capability over a return's accounts: the model's suggestions, settled by
    code, as one proposal through C17 (module docstring)."""
    from abacus.modules.agents.api import ToolCallIn, call_tool

    given = model_input(accounts, published)
    answer = await _judge(agent, given, return_id)
    if answer is None:
        return MapResult("refused", None, 0, tuple((a.code, "refused") for a in given.accounts))
    settled = settle(answer, given)
    if not settled.kept:
        return MapResult("nothing_to_propose", None, 0, settled.abstained)
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
                "mappings": [
                    {"account_code": m.code, "form_line_key": m.key, "confidence": m.confidence}
                    for m in settled.kept
                ],
            },
        ),
    )
    if not proposed.ok:
        return MapResult("refused", None, 0, settled.abstained)
    proposal = UUID(str(cast(dict[str, object], proposed.result)["proposal_id"]))
    return MapResult("proposed", proposal, len(settled.kept), settled.abstained)


__all__ = [
    "CAPABILITY",
    "MIN_CONFIDENCE",
    "PROPOSE_TOOL",
    "MapAccount",
    "MapAccountsInput",
    "MapAccountsOutput",
    "MapResult",
    "MappedAccount",
    "Settled",
    "map_accounts",
    "model_input",
    "redact_amounts",
    "settle",
]
