"""`ledger.tb_mapper` mode `tax_lines` (T-06-T38; TASK-8829; T-06 §6, §7; SPEC-702 F6, AC-36;
AUD-38 a, b; ADR-019, ADR-050, ADR-052, ADR-167; DEC-5831). RED: an agent path.

A trial balance handed to a tax return (C12) carries last year's tax-line code for each account the
target return already mapped (`ledger.tb_handoff.preview`, `prior_year`). This mode suggests a
code for the accounts that have none, for the tax team to adopt:

- **Consent first.** The target taxpayer's §7216 consents (use and AI disclosure, for the target
  return's filing entity and tax year) are checked by code before anything else
  (`target_consented`). Without them the mode makes no gateway call and every new account travels
  blank (`no_consent`; AUD-38's "all 7 travel blank"). The gateway checks the same subject again
  (C19 condition 6) on the call it does make.
- **Names and numbers only.** The model sees each new account's number and name (anything that
  reads as an amount redacted), last year's mapped accounts of the taxpayer (number, name, code)
  as evidence and the tax-line catalogue; no balance, side or amount field exists in its input.
- **Code has the last word** (`settle`): a code outside the catalogue, a missing, repeated or
  unknown account, an explanation over 140 characters, or a suggestion whose cited evidence
  account does not carry the same code, leaves the account blank. A judgment account is blank
  whatever the model said: code's own list (`JUDGMENT`: §461(h) accruals, de minimis and
  small-items policies, meals and entertainment, penalties and fines, political and lobbying
  costs, income tax expense, related-party items) and the model's `judgment` flag both force it,
  with an explanation (code's fixed sentence first, ADR-050).
- **Suggestions only.** Kept codes become C17 suggestions on the source work item
  (`tb_handoff_tax_line`) through `tax.suggest_tax_lines`; the person handing off sees them in the
  preview and the tax team adopts them on the return. The agent never maps or hands off.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AgentContext

if TYPE_CHECKING:
    from abacus.ai_gateway.context import DataSubject

CAPABILITY: Final = "ledger.tb_mapper"
MODE: Final = "tax_lines"
PROMPT: Final = "ledger.tb_mapper.tax_lines@v1"
PROPOSE_TOOL: Final = "tax.suggest_tax_lines"
SUGGESTION_TARGET: Final = "tb_handoff_tax_line"
MAX_ACCOUNTS: Final = 300
MAX_EXPLANATION: Final = 140
Int = classified("internal")
Tri = classified("restricted", tri=True)

# What reads as an amount in a name (as `tax.account_mapper`): a currency sign, a grouped or
# decimal number, or five or more digits. Account numbers travel apart, never redacted.
_AMOUNT: Final = re.compile(
    r"[$€£]\s?-?\d[\d,]*(?:\.\d+)?|\(?-?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?|-?\d+\.\d{2}\b|\b\d{5,}\b"
)

# Code's judgment classes: a name that matches is always blank, with this sentence.
JUDGMENT: Final[tuple[tuple[str, re.Pattern[str], str], ...]] = (
    (
        "accrual_461h",
        re.compile(
            r"\baccru\w*\b.*\b(bonus(es)?|vacation|pto|warrant(y|ies)|legal|incentives?|"
            r"rewards?|loyalty|rebates?|litigation|self-insur\w*|severance)\b"
            r"|\bcompensated absences\b|\b(bonus|warranty) accru",
            re.I,
        ),
        "Accrued liability: deduction timing under §461(h) is the tax team's judgment.",
    ),
    (
        "de_minimis",
        re.compile(r"\bde minimis\b|\bsmall (tools|equipment|items)\b|\bsmall-items\b", re.I),
        "De minimis or small-items policy: capitalisation is the tax team's judgment.",
    ),
    (
        "meals",
        re.compile(r"\bmeals?\b|\bentertainment\b", re.I),
        "Meals or entertainment: the deductible share is the tax team's judgment.",
    ),
    (
        "penalties",
        re.compile(r"\bpenalt(y|ies)\b|\bfines?\b", re.I),
        "Penalties or fines: deductibility is the tax team's judgment.",
    ),
    (
        "political",
        re.compile(r"\bpolitical\b|\blobbying\b", re.I),
        "Political or lobbying cost: deductibility is the tax team's judgment.",
    ),
    (
        "income_tax",
        re.compile(r"\bincome tax(es)?\b|\bdeferred tax\b|\btax provision\b", re.I),
        "Income tax expense or deferred tax: the book-tax treatment is the tax team's judgment.",
    ),
    (
        "related_party",
        re.compile(
            r"\brelated[- ]party\b|\bdue (to|from) (officer|shareholder|member|partner)", re.I
        ),
        "Related-party item: its treatment is the tax team's judgment.",
    ),
)
MODEL_JUDGMENT: Final = "The agent marked this a judgment account for the tax team."


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class TaxLineAccount(BaseModel):
    """A new account: its number and (redacted) name; no balance field exists."""

    model_config = _cfg()

    account_no: Annotated[str, Field(min_length=1, max_length=40), Tri]
    name: Annotated[str, Field(min_length=1, max_length=200), Tri]


class TaxLineEvidence(BaseModel):
    """Last year's mapped account of the same taxpayer: number, name and the person's code."""

    model_config = _cfg()

    account_no: Annotated[str, Field(min_length=1, max_length=40), Tri]
    name: Annotated[str, Field(min_length=1, max_length=200), Tri]
    tax_line_code: Annotated[str, Field(min_length=1, max_length=80), Int]


class TaxLine(BaseModel):
    model_config = _cfg()

    code: Annotated[str, Field(min_length=1, max_length=80), Int]
    caption: Annotated[str, Field(min_length=1, max_length=200), Int]


class TaxLinesInput(BaseModel):
    model_config = _cfg()

    accounts: Annotated[list[TaxLineAccount], Field(min_length=1, max_length=MAX_ACCOUNTS), Tri]
    evidence: Annotated[list[TaxLineEvidence], Field(max_length=2000), Tri]
    catalogue: Annotated[list[TaxLine], Field(min_length=1, max_length=1000), Int]


class TaxLineSuggestion(BaseModel):
    model_config = _cfg()

    account_no: Annotated[str, Field(min_length=1, max_length=40), Tri]
    tax_line_code: Annotated[str | None, Field(max_length=80), Int] = None
    evidence_account_no: Annotated[str | None, Field(max_length=40), Tri] = None
    judgment: Annotated[bool, Int] = False
    explanation: Annotated[str, Field(max_length=400), Tri] = ""


class TaxLinesOutput(BaseModel):
    """`ledger.tb_mapper.tax_lines@v1`'s answer: one suggestion (or blank) per new account."""

    model_config = _cfg()

    suggestions: Annotated[list[TaxLineSuggestion], Field(max_length=MAX_ACCOUNTS), Tri]


@dataclass(frozen=True)
class Kept:
    account_no: str
    tax_line_code: str
    evidence_account_no: str
    explanation: str


@dataclass(frozen=True)
class Blank:
    account_no: str
    reason: str  # a code: judgment, no_answer, abstained, code_not_in_catalogue, ...
    explanation: str | None = None  # judgment accounts only (AUD-38 b)


@dataclass(frozen=True)
class Settled:
    kept: tuple[Kept, ...]
    blank: tuple[Blank, ...]


def redact_amounts(name: str) -> str:
    return _AMOUNT.sub("[amount]", name)


def judgment_of(name: str) -> str | None:
    """Code's judgment sentence for an account name, or None."""
    for _key, pattern, sentence in JUDGMENT:
        if pattern.search(name):
            return sentence
    return None


def model_input(
    accounts: Sequence[tuple[str, str]],
    evidence: Sequence[tuple[str, str, str]],
    catalogue: Sequence[tuple[str, str]],
) -> TaxLinesInput:
    """(number, name) per new account, (number, name, code) per prior-year account and the
    catalogue; names redacted, accounts unique by number, the catalogue by code."""
    seen: dict[str, TaxLineAccount] = {}
    for no, name in accounts:
        seen.setdefault(no, TaxLineAccount(account_no=no, name=redact_amounts(name)))
    prior: dict[str, TaxLineEvidence] = {}
    for no, name, code in evidence:
        prior.setdefault(
            no, TaxLineEvidence(account_no=no, name=redact_amounts(name), tax_line_code=code)
        )
    lines = dict(catalogue)
    return TaxLinesInput(
        accounts=list(seen.values()),
        evidence=list(prior.values()),
        catalogue=[TaxLine(code=k, caption=v) for k, v in sorted(lines.items())],
    )


def settle(
    answer: TaxLinesOutput | None, given: TaxLinesInput, names: Mapping[str, str]
) -> Settled:
    """Code's last word (module docstring): every given account is kept or blank, once. `names`
    are the unredacted names (code's judgment list reads them; the model never does)."""
    catalogue = {line.code for line in given.catalogue}
    evidence = {e.account_no: e.tax_line_code for e in given.evidence}
    answered: dict[str, TaxLineSuggestion] = {}
    repeated: set[str] = set()
    for s in answer.suggestions if answer is not None else ():
        if s.account_no in answered:
            repeated.add(s.account_no)
        answered.setdefault(s.account_no, s)
    kept: list[Kept] = []
    blank: list[Blank] = []
    for account in given.accounts:
        no = account.account_no
        s = answered.get(no)
        sentence = judgment_of(names.get(no, account.name))
        if sentence is not None:
            blank.append(Blank(no, "judgment", sentence))
        elif s is not None and s.judgment and no not in repeated:
            blank.append(Blank(no, "judgment", MODEL_JUDGMENT))
        elif s is None:
            blank.append(Blank(no, "no_answer"))
        elif no in repeated:
            blank.append(Blank(no, "answered_twice"))
        elif s.tax_line_code is None:
            blank.append(Blank(no, "abstained"))
        elif s.tax_line_code not in catalogue:
            blank.append(Blank(no, "code_not_in_catalogue"))
        elif (
            s.evidence_account_no is None or evidence.get(s.evidence_account_no) != s.tax_line_code
        ):
            blank.append(Blank(no, "evidence_missing"))
        elif len(s.explanation) > MAX_EXPLANATION:
            blank.append(Blank(no, "explanation_too_long"))
        else:
            kept.append(Kept(no, s.tax_line_code, s.evidence_account_no, s.explanation.strip()))
    return Settled(tuple(kept), tuple(blank))


Outcome = Literal["suggested", "nothing_to_suggest", "no_consent", "refused"]


@dataclass(frozen=True)
class TaxLinesResult:
    outcome: Outcome
    suggestions: Mapping[str, tuple[str, UUID]]  # account number -> (code, suggestion id)
    blank: tuple[Blank, ...]
    gateway_calls: int
    explanations: Mapping[str, str] = field(default_factory=dict[str, str])


async def target_subject(tenant: TenantContext, target_return_id: UUID) -> DataSubject | None:
    from abacus.modules.engagements.api import work_item_tri_subject

    return await work_item_tri_subject(tenant, target_return_id)


async def target_consented(tenant: TenantContext, subject: DataSubject | None) -> bool:
    """Both §7216 consents of the target taxpayer for its year (fail closed: unknown is no)."""
    from abacus.kernel.clock import now as business_now
    from abacus.modules.organisations.api import TriSubject, covering_consents

    if subject is None or subject.entity_id is None or subject.tax_year is None:
        return False
    covered = await covering_consents(
        tenant, [TriSubject(subject.entity_id, subject.tax_year)], await business_now(tenant)
    )
    return covered is not None


async def _judge(
    agent: AgentContext, given: TaxLinesInput, subject: DataSubject
) -> TaxLinesOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder()
        .task(given.model_dump(), untrusted=("accounts", "evidence"))
        .subjects(subject)
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=PROMPT,
                tier=spec.tier,
                output_schema=TaxLinesOutput,
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
    except Exception:  # a refused call (consent, boundary, budget, schema): all stay blank
        return None
    return cast(TaxLinesOutput, result.output)


def _all_blank(accounts: Sequence[tuple[str, str]], reason: str) -> tuple[Blank, ...]:
    out: list[Blank] = []
    for no, name in dict(accounts).items():
        sentence = judgment_of(name)
        out.append(Blank(no, "judgment", sentence) if sentence else Blank(no, reason))
    return tuple(out)


async def suggest_tax_lines(
    agent: AgentContext,
    *,
    source_work_item_id: UUID,
    target_return_id: UUID,
    new_accounts: Sequence[tuple[str, str]],
    evidence: Sequence[tuple[str, str, str]],
    catalogue: Sequence[tuple[str, str]],
) -> TaxLinesResult:
    """One run over the new accounts (module docstring). Consent is checked before any call."""
    from abacus.modules.agents.api import ToolCallIn, call_tool

    if not new_accounts:
        return TaxLinesResult("nothing_to_suggest", {}, (), 0)
    subject = await target_subject(agent.tenant, target_return_id)
    if subject is None or not await target_consented(agent.tenant, subject):
        return TaxLinesResult("no_consent", {}, _all_blank(new_accounts, "no_consent"), 0)
    if not catalogue:
        return TaxLinesResult(
            "nothing_to_suggest", {}, _all_blank(new_accounts, "no_catalogue"), 0
        )
    given = model_input(new_accounts, evidence, catalogue)
    answer = await _judge(agent, given, subject)
    if answer is None:
        return TaxLinesResult("refused", {}, _all_blank(new_accounts, "refused"), 1)
    settled = settle(answer, given, dict(new_accounts))
    explanations = {b.account_no: b.explanation for b in settled.blank if b.explanation}
    if not settled.kept:
        return TaxLinesResult("nothing_to_suggest", {}, settled.blank, 1, explanations)
    done = await call_tool(
        agent,
        ToolCallIn(
            run_id=agent.agent_run_id,
            step_seq=1,
            attempt=1,
            name=PROPOSE_TOOL,
            arguments={
                "source_work_item_id": str(source_work_item_id),
                "target_return_id": str(target_return_id),
                "suggestions": [
                    {
                        "account_no": k.account_no,
                        "tax_line_code": k.tax_line_code,
                        "evidence_account_no": k.evidence_account_no,
                        "explanation": k.explanation,
                    }
                    for k in settled.kept
                ],
            },
        ),
    )
    if not done.ok:
        return TaxLinesResult("refused", {}, settled.blank, 1, explanations)
    ids = cast(dict[str, list[str]], done.result)["suggestion_ids"]
    made = {
        k.account_no: (k.tax_line_code, UUID(str(i)))
        for k, i in zip(settled.kept, ids, strict=True)
    }
    return TaxLinesResult("suggested", made, settled.blank, 1, explanations)


def register() -> None:
    """At the tax api's import: the suggestion target (the tool registered at this import)."""
    from abacus.modules.agents.api import register_suggestion_target
    from abacus.modules.engagements.api import work_item_engagement

    register_suggestion_target(SUGGESTION_TARGET, engagement_of=work_item_engagement)


__all__ = [
    "CAPABILITY",
    "JUDGMENT",
    "MODE",
    "PROMPT",
    "PROPOSE_TOOL",
    "SUGGESTION_TARGET",
    "Blank",
    "Kept",
    "TaxLinesInput",
    "TaxLinesOutput",
    "TaxLinesResult",
    "judgment_of",
    "model_input",
    "redact_amounts",
    "register",
    "settle",
    "suggest_tax_lines",
    "target_consented",
]
