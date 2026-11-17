"""`consolidation.elimination_proposer` v1 (A-09-T34; A-09 §6; SPEC-658 F4; ADR-019, ADR-050,
ADR-052, ADR-066; DEC-5522). Red zone (an agent path). Workflow shape: code's steps around one
model call and one propose-only tool.

**Code computes every amount.** From each mapped entity's FS lines (C9 v2) and the structure,
code finds the intercompany pairs and builds the candidates: investment against the subsidiary's
contributed capital (E1, by the parent's level), intercompany sales against the buyer's cost of
goods sold (E2), unrealized profit in the buyer's ending inventory (E3), intercompany balances
(E4) and intercompany rent (E5). A pair whose two sides differ is not proposed (a person looks).

**The model writes words and points at a cell.** It is given each candidate's key, kind,
entities, captions and code's figures, and (for E3) the buyer's inventory workbook as
`<untrusted>` cells; it writes a description and a note and, for E3, names the cell that holds
the inventory bought from the seller. It never states a number code did not give it.

**Code has the last word.** E3's base is the value of the cell the model named, read by code and
cited through C4 (`sheet_cell`, verified by evidence's verifier with that value); its amount is
that value times the seller's gross margin, both computed by code (1,000,000 x 24.0% = 240,000,
the margin 14,400,000 ÷ 60,000,000). A candidate whose words carry a number code did not give,
or whose E3 cell is missing or unverified, is not proposed. Each kept candidate becomes one
`proposed` elimination through `assurance.propose_eliminations`, naming its run; approving and
posting stay a person's (the agent is denied both). Synthetic firms only until cleared
(`client_data: none`), behind the variant flag `prompt.consolidation.elimination_proposer`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Annotated, Final, Literal, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified

if TYPE_CHECKING:
    from abacus.modules.identity.api import AgentContext, AuthContext

CAPABILITY: Final = "consolidation.elimination_proposer"
PROPOSE_TOOL: Final = "assurance.propose_eliminations"
MAX_DESCRIPTION: Final = 200
MAX_NOTE: Final = 500
ZERO: Final = Decimal("0")
DOLLAR: Final = Decimal("1")
Int = classified("internal")
Conf = classified("confidential")
Kind = Literal["investment", "intercompany_sales", "unrealized_profit", "balances", "rent"]
_NUMBER: Final = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- code's inputs and candidates -----------------------------------------------------------


@dataclass(frozen=True)
class EntityTb:
    """One mapped entity: its key in the structure, its name, its level and parent, and its FS
    lines' net (debits positive)."""

    key: str
    client_entity_id: UUID
    name: str
    level: int
    parent_key: str | None
    lines: Mapping[str, Decimal]


@dataclass(frozen=True)
class Line:
    caption: str
    entity_key: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO


@dataclass(frozen=True)
class Candidate:
    key: str
    kind: Kind
    level: int
    entities: tuple[str, ...]
    lines: tuple[Line, ...]
    figures: tuple[Decimal, ...]  # every number the words may cite
    computation: str
    seller_margin: Decimal | None = None  # E3: exact, from the seller's lines
    buyer_key: str | None = None
    seller_key: str | None = None

    @property
    def amount(self) -> Decimal:
        return sum((ln.debit for ln in self.lines), ZERO)


def _norm(caption: str) -> str:
    return (
        re.sub(r"\s+", " ", caption.replace("\N{EM DASH}", "-").replace("\N{EN DASH}", "-"))
        .strip()
        .lower()
    )


def _find(lines: Mapping[str, Decimal], test: Callable[[str], bool]) -> tuple[str, Decimal] | None:
    for caption, amount in lines.items():
        if test(_norm(caption)) and amount != ZERO:
            return caption, amount
    return None


def _is_receivable(c: str) -> bool:
    return "intercompany receivable" in c or c.startswith("due from")


def _is_payable(c: str) -> bool:
    return "intercompany payable" in c or c.startswith("due to")


def _is_ic_sales(c: str) -> bool:
    return "sales" in c and "intercompany" in c


def _is_sales(c: str) -> bool:
    return "net sales" in c or c == "sales" or c.startswith("sales -")


def _is_cogs(c: str) -> bool:
    return "cost of goods sold" in c or c.startswith("cost of sales")


def _is_rent_income(c: str) -> bool:
    return "rental income" in c and "intercompany" in c


def _is_rent_expense(c: str) -> bool:
    return "rent expense" in c and "intercompany" in c


def _is_capital(c: str) -> bool:
    return "common stock" in c or "contributed capital" in c


def _is_inventory(c: str) -> bool:
    return c.startswith("inventory")


def _ancestors(e: EntityTb, by_key: Mapping[str, EntityTb]) -> list[str]:
    out: list[str] = []
    key = e.parent_key
    while key is not None and key in by_key:
        out.append(key)
        key = by_key[key].parent_key
    return out


def _common_level(a: EntityTb, b: EntityTb, by_key: Mapping[str, EntityTb]) -> int:
    """The level of the lowest entity both sit under (the elimination's level); 1 if none."""
    ups = _ancestors(b, by_key)
    for key in _ancestors(a, by_key):
        if key in ups:
            return by_key[key].level
    return 1


def _money(value: Decimal) -> Decimal:
    return value.quantize(DOLLAR, rounding=ROUND_HALF_UP)


def seller_margin(seller: EntityTb) -> Decimal | None:
    """Gross margin on total sales (third-party and intercompany), exact: 14,400,000 ÷
    60,000,000 = 0.24. None when the seller shows no sales."""
    sales = -sum((v for c, v in seller.lines.items() if _is_sales(_norm(c))), ZERO)
    cogs = sum((v for c, v in seller.lines.items() if _is_cogs(_norm(c))), ZERO)
    if sales <= ZERO:
        return None
    return (sales - cogs) / sales


def _token(name: str) -> str:
    return _norm(name).replace(",", "").replace(".", "").replace(" co", "").strip()


def candidates(entities: Sequence[EntityTb]) -> list[Candidate]:
    """Every elimination code can see (module docstring), in a stable order. E3 is built
    without its base: its amount waits for the cited cell."""
    by_key = {e.key: e for e in entities}
    out: list[Candidate] = []
    # E1: investment in each child against the child's contributed capital, by the parent.
    for parent in sorted(entities, key=lambda e: (e.level, e.name)):
        children = [e for e in entities if e.parent_key == parent.key]
        lines: list[Line] = []
        figures: list[Decimal] = []
        for caption, amount in parent.lines.items():
            c = _norm(caption)
            if not c.startswith("investment in ") or amount <= ZERO:
                continue
            target = _token(caption[len("investment in ") :])
            child = next((ch for ch in children if target and target in _token(ch.name)), None)
            if child is None:
                continue
            capital = _find(child.lines, _is_capital)
            if capital is None or -capital[1] != amount:
                continue
            lines += [
                Line(capital[0], child.key, debit=amount),
                Line(caption, parent.key, credit=amount),
            ]
            figures.append(amount)
        if lines:
            total = sum(figures, ZERO)
            out.append(
                Candidate(
                    key=f"investment:{parent.key}",
                    kind="investment",
                    level=parent.level,
                    entities=(parent.key, *sorted({ln.entity_key for ln in lines} - {parent.key})),
                    lines=tuple(lines),
                    figures=(total, *figures),
                    computation=" + ".join(f"{f:,.0f}" for f in figures) + f" = {total:,.0f}",
                )
            )
    # E4 (and the counterparty for E2 and E3): a receivable against an equal payable.
    pairs: list[tuple[EntityTb, EntityTb]] = []
    for seller in entities:
        rec = _find(seller.lines, _is_receivable)
        if rec is None:
            continue
        for buyer in entities:
            pay = _find(buyer.lines, _is_payable) if buyer.key != seller.key else None
            if pay is None or rec[1] != -pay[1]:
                continue
            pairs.append((seller, buyer))
            out.append(
                Candidate(
                    key=f"balances:{seller.key}:{buyer.key}",
                    kind="balances",
                    level=_common_level(seller, buyer, by_key),
                    entities=(seller.key, buyer.key),
                    lines=(
                        Line(pay[0], buyer.key, debit=rec[1]),
                        Line(rec[0], seller.key, credit=rec[1]),
                    ),
                    figures=(rec[1],),
                    computation=f"{rec[1]:,.0f} due from = {rec[1]:,.0f} due to",
                )
            )
    # E2 and E3: the seller's intercompany sales and the buyer it sells to.
    for seller, buyer in pairs:
        ic = _find(seller.lines, _is_ic_sales)
        cogs = _find(buyer.lines, _is_cogs)
        if ic is None or cogs is None:
            continue
        sold = -ic[1]
        level = _common_level(seller, buyer, by_key)
        out.append(
            Candidate(
                key=f"intercompany_sales:{seller.key}:{buyer.key}",
                kind="intercompany_sales",
                level=level,
                entities=(seller.key, buyer.key),
                lines=(Line(ic[0], seller.key, debit=sold), Line(cogs[0], buyer.key, credit=sold)),
                figures=(sold,),
                computation=f"{sold:,.0f} sold {seller.name} → {buyer.name}",
            )
        )
        margin = seller_margin(seller)
        inventory = _find(buyer.lines, _is_inventory)
        if margin is not None and margin > ZERO and inventory is not None:
            out.append(
                Candidate(
                    key=f"unrealized_profit:{seller.key}:{buyer.key}",
                    kind="unrealized_profit",
                    level=level,
                    entities=(seller.key, buyer.key),
                    lines=(Line(cogs[0], buyer.key), Line(inventory[0], buyer.key)),
                    figures=(),
                    computation="",
                    seller_margin=margin,
                    buyer_key=buyer.key,
                    seller_key=seller.key,
                )
            )
    # E5: intercompany rent, income against expense.
    for lessor in entities:
        income = _find(lessor.lines, _is_rent_income)
        if income is None:
            continue
        for lessee in entities:
            expense = _find(lessee.lines, _is_rent_expense) if lessee.key != lessor.key else None
            if expense is None or -income[1] != expense[1]:
                continue
            out.append(
                Candidate(
                    key=f"rent:{lessor.key}:{lessee.key}",
                    kind="rent",
                    level=_common_level(lessor, lessee, by_key),
                    entities=(lessor.key, lessee.key),
                    lines=(
                        Line(income[0], lessor.key, debit=expense[1]),
                        Line(expense[0], lessee.key, credit=expense[1]),
                    ),
                    figures=(expense[1],),
                    computation=f"{expense[1]:,.0f} rent",
                )
            )
    return out


def unrealized_profit(candidate: Candidate, cell_value: Decimal) -> Candidate:
    """E3 with its base: the cited cell's value times the seller's margin, by code."""
    margin = candidate.seller_margin or ZERO
    amount = _money(cell_value * margin)
    cogs, inventory = candidate.lines
    pct = (margin * 100).quantize(Decimal("0.1"))
    return Candidate(
        key=candidate.key,
        kind=candidate.kind,
        level=candidate.level,
        entities=candidate.entities,
        lines=(
            Line(cogs.caption, cogs.entity_key, debit=amount),
            Line(inventory.caption, inventory.entity_key, credit=amount),
        ),
        figures=(cell_value, pct, amount),
        computation=f"{cell_value:,.0f} \N{MULTIPLICATION SIGN} {pct}% = {amount:,.0f}",
        seller_margin=margin,
        buyer_key=candidate.buyer_key,
        seller_key=candidate.seller_key,
    )


# --- the model's input and output ----------------------------------------------------------


class ProposerLine(BaseModel):
    model_config = _cfg()

    caption: Annotated[str, Field(max_length=200), Conf]
    entity: Annotated[str, Field(max_length=200), Conf]
    side: Annotated[Literal["debit", "credit"], Int]
    amount: Annotated[str | None, Field(max_length=30), Conf] = None  # E3: none until cited


class ProposerCandidate(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(max_length=200), Int]
    kind: Annotated[Kind, Int]
    lines: Annotated[list[ProposerLine], Field(max_length=10), Conf]
    figures: Annotated[list[str], Field(max_length=10), Conf]
    margin_pct: Annotated[str | None, Field(max_length=10), Conf] = None


class ProposerSheet(BaseModel):
    model_config = _cfg()

    name: Annotated[str, Field(max_length=120), Conf]
    rows: Annotated[list[list[str]], Field(max_length=400), Conf]


class ProposerInput(BaseModel):
    """What the model is given: code's candidates and, for E3, the workbook's masked cells."""

    model_config = _cfg()

    candidates: Annotated[list[ProposerCandidate], Field(min_length=1, max_length=40), Conf]
    sheets: Annotated[list[ProposerSheet], Field(max_length=5), Conf] = []


class ProposerCell(BaseModel):
    model_config = _cfg()

    sheet: Annotated[str, Field(max_length=120), Conf]
    cell: Annotated[str, Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,5}$"), Int]


class ProposerEntry(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(max_length=200), Int]
    description: Annotated[str, Field(max_length=400), Conf] = ""
    note: Annotated[str, Field(max_length=1000), Conf] = ""
    evidence: Annotated[ProposerCell | None, Int] = None


class ProposerOutput(BaseModel):
    """`consolidation.elimination_proposer@v1`'s answer: words per candidate, a cell for E3."""

    model_config = _cfg()

    entries: Annotated[list[ProposerEntry], Field(max_length=40), Conf]


@dataclass(frozen=True)
class Kept:
    candidate: Candidate
    description: str
    note: str
    cell: ProposerCell | None = None


@dataclass(frozen=True)
class Settled:
    kept: tuple[Kept, ...]
    blocked: tuple[tuple[str, str], ...]  # (candidate key, reason code)


def _numbers(text: str) -> set[Decimal]:
    out: set[Decimal] = set()
    for token in _NUMBER.findall(text):
        try:
            out.add(Decimal(token.replace(",", "")))
        except ArithmeticError:
            continue
    return out


def _allowed(candidate: Candidate, cell_value: Decimal | None) -> set[Decimal]:
    allowed = {abs(f) for f in candidate.figures}
    if cell_value is not None:
        allowed.add(cell_value)
    if candidate.seller_margin is not None:
        allowed.add((candidate.seller_margin * 100).quantize(Decimal("0.1")))
    return allowed | {Decimal(n) for n in range(0, 13)}  # dates, levels, "E3", months


def provenance_ok(text: str, candidate: Candidate, cell_value: Decimal | None) -> bool:
    """Every number in the words is one code gave (or a small ordinal such as a level)."""
    return _numbers(text) <= _allowed(candidate, cell_value)


def settle(
    answer: ProposerOutput | None,
    given: Sequence[Candidate],
    cell_values: Mapping[str, Decimal | None],
) -> Settled:
    """Code's last word: each candidate is kept once with checked words (and, for E3, a cell
    whose value code read), or blocked with its reason."""
    by_key: dict[str, ProposerEntry] = {}
    twice: set[str] = set()
    for entry in answer.entries if answer is not None else ():
        if entry.key in by_key:
            twice.add(entry.key)
        by_key.setdefault(entry.key, entry)
    kept: list[Kept] = []
    blocked: list[tuple[str, str]] = []
    for candidate in given:
        entry = by_key.get(candidate.key)
        if entry is None:
            blocked.append((candidate.key, "no_answer"))
            continue
        if candidate.key in twice:
            blocked.append((candidate.key, "answered_twice"))
            continue
        description, note = entry.description.strip(), entry.note.strip()
        if not description or len(description) > MAX_DESCRIPTION or len(note) > MAX_NOTE:
            blocked.append((candidate.key, "words_invalid"))
            continue
        value: Decimal | None = None
        final = candidate
        if candidate.kind == "unrealized_profit":
            value = cell_values.get(candidate.key)
            if entry.evidence is None or value is None or value <= ZERO:
                blocked.append((candidate.key, "uncited_number"))
                continue
            final = unrealized_profit(candidate, value)
        if not provenance_ok(f"{description} {note}", final, value):
            blocked.append((candidate.key, "number_not_from_code"))
            continue
        kept.append(Kept(final, description, note, entry.evidence))
    return Settled(tuple(kept), tuple(blocked))


def model_input(
    given: Sequence[Candidate],
    names: Mapping[str, str],
    sheets: Mapping[str, Sequence[Sequence[str]]] | None = None,
) -> ProposerInput:
    def lines_of(c: Candidate) -> list[ProposerLine]:
        pending = c.kind == "unrealized_profit"  # E3's amount waits for the cited cell
        out: list[ProposerLine] = []
        for i, ln in enumerate(c.lines):
            debit = ln.debit > ZERO or (pending and i == 0)
            out.append(
                ProposerLine(
                    caption=ln.caption,
                    entity=names.get(ln.entity_key, ln.entity_key),
                    side="debit" if debit else "credit",
                    amount=None if pending else f"{max(ln.debit, ln.credit):,.0f}",
                )
            )
        return out

    return ProposerInput(
        candidates=[
            ProposerCandidate(
                key=c.key,
                kind=c.kind,
                lines=lines_of(c),
                figures=[f"{f:,.0f}" for f in c.figures],
                margin_pct=None
                if c.seller_margin is None
                else f"{(c.seller_margin * 100).quantize(Decimal('0.1'))}",
            )
            for c in given
        ],
        sheets=[
            ProposerSheet(name=name, rows=[list(r) for r in rows][:400])
            for name, rows in (sheets or {}).items()
        ][:5],
    )


# --- the run ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposeResult:
    outcome: Literal["proposed", "nothing_to_propose", "refused", "unavailable"]
    proposed: int
    blocked: tuple[tuple[str, str], ...] = field(default_factory=tuple[tuple[str, str], ...])
    run_id: UUID | None = None


async def _judge(agent: AgentContext, given: ProposerInput) -> ProposerOutput | None:
    from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, call
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(CAPABILITY)
    context = (
        ContextBuilder()
        .task(given.model_dump(), untrusted=("sheets", "candidates"))  # client names and cells
        .build()
    )
    try:
        result = await call(
            GatewayCall(
                purpose=spec.purpose,
                prompt=spec.prompt,
                tier=spec.tier,
                output_schema=ProposerOutput,
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
    return cast(ProposerOutput, result.output)


def _cell_value(
    sheets: Mapping[str, Sequence[Sequence[str]]], cell: ProposerCell | None
) -> Decimal | None:
    from abacus.modules.evidence.api import citation_cell_text

    if cell is None or cell.sheet not in sheets:
        return None
    text = citation_cell_text(sheets[cell.sheet], cell.cell)
    if text is None:
        return None
    try:
        return Decimal(re.sub(r"[^\d.\-]", "", text) or "x")
    except ArithmeticError:
        return None


async def propose_for(
    agent: AgentContext,
    *,
    work_item_id: UUID,
    consolidation_id: UUID,
    entities: Sequence[EntityTb],
    inventory_version_id: UUID | None,
    sheets: Mapping[str, Sequence[Sequence[str]]],
) -> ProposeResult:
    """One run: code's candidates, the model's words and cell, code's settle, the tool."""
    from abacus.modules.agents.api import ToolCallIn, call_tool

    given = candidates(entities)
    if not given:
        return ProposeResult("nothing_to_propose", 0, run_id=agent.agent_run_id)
    names = {e.key: e.name for e in entities}
    answer = await _judge(agent, model_input(given, names, sheets))
    if answer is None:
        return ProposeResult("refused", 0, tuple((c.key, "refused") for c in given))
    cells = {e.key: e.evidence for e in answer.entries}
    values = {c.key: _cell_value(sheets, cells.get(c.key)) for c in given}
    settled = settle(answer, given, values)
    if not settled.kept:
        return ProposeResult("nothing_to_propose", 0, settled.blocked, agent.agent_run_id)
    client_of = {e.key: str(e.client_entity_id) for e in entities}
    done = await call_tool(
        agent,
        ToolCallIn(
            run_id=agent.agent_run_id,
            step_seq=1,
            attempt=1,
            name=PROPOSE_TOOL,
            arguments={
                "work_item_id": str(work_item_id),
                "consolidation_id": str(consolidation_id),
                "proposals": [
                    {
                        "key": k.candidate.key,
                        "level": k.candidate.level,
                        "description": k.description,
                        "note": k.note,
                        "computation": k.candidate.computation,
                        "lines": [
                            {
                                "caption": ln.caption,
                                "client_entity_id": client_of[ln.entity_key],
                                "debit": str(ln.debit),
                                "credit": str(ln.credit),
                            }
                            for ln in k.candidate.lines
                        ],
                        "cell": None
                        if k.cell is None or inventory_version_id is None
                        else {
                            "evidence_version_id": str(inventory_version_id),
                            "sheet": k.cell.sheet,
                            "cell": k.cell.cell,
                            "value": str(values[k.candidate.key]),
                        },
                    }
                    for k in settled.kept
                ],
            },
        ),
    )
    if not done.ok:
        return ProposeResult("refused", 0, settled.blocked, agent.agent_run_id)
    unverified = int(cast(int, (done.result or {}).get("blocked", 0)))
    blocked = settled.blocked + tuple(("cell", "citation_unverified") for _ in range(unverified))
    proposed = len(cast(list[object], (done.result or {}).get("entry_ids", [])))
    return ProposeResult("proposed", proposed, blocked, agent.agent_run_id)


async def entities_for(
    person: AuthContext, consolidation_id: UUID
) -> tuple[UUID, UUID, list[EntityTb]]:
    """Code's inputs: the consolidation's engagement and work item, and each mapped entity's FS
    lines (C9 v2) with its name, level and parent in the structure (never a guess: an unmapped
    entity is left out)."""
    from abacus.kernel.db import tenant_session
    from abacus.modules.assurance.group_tb import mapped_lines
    from abacus.modules.ledger import api as ledger
    from abacus.modules.organisations.api import client_names

    facts = await ledger.consolidation_facts(person.tenant, consolidation_id)
    lines = await mapped_lines(person.tenant, facts)
    async with tenant_session(person.tenant) as session:
        names = await client_names(session, [e.client_entity_id for e in facts.entities])
    out: list[EntityTb] = []
    for e in facts.entities:
        key = str(e.id)
        if key not in lines:
            continue
        found = names.get(e.client_entity_id)
        totals: dict[str, Decimal] = {}
        for line in lines[key]:
            totals[line.caption] = totals.get(line.caption, ZERO) + line.amount
        out.append(
            EntityTb(
                key=key,
                client_entity_id=e.client_entity_id,
                name=found.client_entity_name if found is not None else key,
                level=e.level,
                parent_key=None if e.parent_id is None else str(e.parent_id),
                lines=totals,
            )
        )
    return facts.engagement_id, facts.work_item_id, out


async def run_proposals(
    person: AuthContext,
    *,
    engagement_id: UUID,
    work_item_id: UUID,
    consolidation_id: UUID,
    entities: Sequence[EntityTb],
    inventory_version_id: UUID | None,
) -> ProposeResult:
    """AUD-33 "Propose eliminations": a person's run; none of it approves or posts. Synthetic
    firms only until the boundary is cleared, and only with the variant flag on."""
    from abacus.ai_gateway import is_synthetic
    from abacus.kernel._flags import PROMPT_CONSOLIDATION_ELIMINATION_PROPOSER
    from abacus.kernel.flags import flag_variant
    from abacus.modules.agents.api import end_capability_run, start_capability_run
    from abacus.modules.engagements.api import get_ref
    from abacus.modules.evidence.api import sheet_rows_for
    from abacus.modules.identity.api import Forbidden, authorise

    if person.tenant.actor_kind != "human" or person.client or person.is_support:
        raise Forbidden("elimination.propose_run", "role")
    await authorise(
        person, "elimination.propose_run", (await get_ref(person, engagement_id)).resource()
    )
    variant = await flag_variant(person.tenant, PROMPT_CONSOLIDATION_ELIMINATION_PROPOSER)
    if variant == "off" or not await is_synthetic(person.tenant):
        return ProposeResult("unavailable", 0)
    agent = await start_capability_run(person, CAPABILITY, engagement_id)
    if agent is None:
        return ProposeResult("refused", 0)
    sheets: dict[str, tuple[tuple[str, ...], ...]] = {}
    if inventory_version_id is not None:
        sheets = await sheet_rows_for(agent, engagement_id, inventory_version_id) or {}
    result = await propose_for(
        agent,
        work_item_id=work_item_id,
        consolidation_id=consolidation_id,
        entities=entities,
        inventory_version_id=inventory_version_id,
        sheets=sheets,
    )
    await end_capability_run(
        agent,
        status="succeeded" if result.outcome == "proposed" else "escalated",
        output={"proposed": result.proposed, "blocked": len(result.blocked)},
    )
    return result


__all__ = [
    "CAPABILITY",
    "PROPOSE_TOOL",
    "Candidate",
    "EntityTb",
    "ProposeResult",
    "ProposerInput",
    "ProposerOutput",
    "candidates",
    "model_input",
    "provenance_ok",
    "run_proposals",
    "seller_margin",
    "settle",
    "unrealized_profit",
]
