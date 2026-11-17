"""`assurance.read_materiality` on C17 (W-02-T11; W-02 §6; ADR-233, ADR-049; DEC-4716).

The engagement's planning materiality as decided (the newest version): overall, performance
materiality and its percentage, the clearly trivial threshold and its percentage, the benchmark
and the version. Read only; the agent never sets, proposes or decides materiality (the
recommender's card is a person's decision, A-04). The runtime authorised `materiality.read`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import agent_tool
from abacus.modules.identity.api import AgentContext

Int = classified("internal")
Conf = classified("confidential")


class MaterialityIn(BaseModel):
    """The frozen workbench suite's arguments (S41 end pass, DEC-4733): the engagement, and a
    version (the latest when omitted)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID, Int]
    version: Annotated[int | None, Field(ge=1), Int] = None


class MaterialityOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decided: Annotated[bool, Int]
    version: Annotated[int | None, Int] = None
    overall: Annotated[Decimal | None, Conf] = None
    performance: Annotated[Decimal | None, Conf] = None
    performance_pct: Annotated[Decimal | None, Conf] = None
    clearly_trivial: Annotated[Decimal | None, Conf] = None
    clearly_trivial_pct: Annotated[Decimal | None, Conf] = None
    benchmark: Annotated[str | None, Conf] = None


@agent_tool(
    name="assurance.read_materiality", kind="read", action="materiality.read",
    data_class="confidential", input_model=MaterialityIn, output_model=MaterialityOut,
    records_read="materiality_version",
)  # fmt: skip
async def read_materiality(agent: AgentContext, args: MaterialityIn) -> MaterialityOut:
    from abacus.modules.assurance import materiality

    found = await materiality.record(agent, args.engagement_id)  # type: ignore[arg-type] -- the run's context
    if not found.versions:
        return MaterialityOut(decided=False)
    if args.version is None:
        v = found.versions[-1]
    else:
        v = next(
            (x for x in found.versions if getattr(x, "version_no", None) == args.version), None
        )
        if v is None:
            raise NotFound("materiality_version")
    return MaterialityOut(
        decided=True,
        version=getattr(v, "version_no", None),
        overall=getattr(v, "overall", None),
        performance=getattr(v, "pm", None),
        performance_pct=getattr(v, "pm_pct", None),
        clearly_trivial=getattr(v, "ct", None),
        clearly_trivial_pct=getattr(v, "ct_pct", None),
        benchmark=getattr(v, "benchmark_key", None),
    )


__all__ = ["read_materiality"]


# --- A-08-T23: the fieldwork modes' two propose tools (suggestions only) ------------------------


class ExplanationIn(BaseModel):
    """A flux line's explanation as a suggestion: drivers name code's facts, never a figure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: Annotated[UUID, Int]
    line_key: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"), Int]
    explanation_fact_ids: Annotated[list[str], Field(min_length=1, max_length=20), Int]
    citation_ids: Annotated[list[UUID], Field(max_length=20), Int] = []

    def tool_targets(self, agent: AgentContext) -> object:
        from abacus.modules.agents.api import ToolTargets

        return ToolTargets((agent.engagement_id,) if agent.engagement_id is not None else ())


class ReconciliationProposalIn(BaseModel):
    """A confirmation's reconciling items as a suggestion; code computes what is unreconciled."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    confirmation_id: Annotated[UUID, Int]
    items: Annotated[list[ReconcilingItemIn], Field(min_length=1, max_length=20), Int]

    def tool_targets(self, agent: AgentContext) -> object:
        from abacus.modules.agents.api import ToolTargets

        return ToolTargets((agent.engagement_id,) if agent.engagement_id is not None else ())


class ProposedOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    suggestion_id: Annotated[UUID, Int]


@agent_tool(
    name="assurance.propose_explanation", kind="propose", action="suggestion.create",
    data_class="confidential", input_model=ExplanationIn, output_model=ProposedOut,
)  # fmt: skip
async def propose_explanation(agent: AgentContext, args: ExplanationIn) -> ProposedOut:
    from abacus.modules.agents.api import create_suggestion
    from abacus.modules.engagements.api import work_item_engagement

    if await work_item_engagement(agent.tenant, args.work_item_id) != agent.engagement_id:
        raise NotFound("work_item")
    made = await create_suggestion(
        agent,
        engagement_id=agent.engagement_id,  # type: ignore[arg-type] -- checked above
        target_type="analytics_line",
        target_id=args.work_item_id,
        field_key=f"explanation:{args.line_key}"[:120],
        proposed_value={"t": "json", "v": {"facts": list(args.explanation_fact_ids)}},
        citation_ids=list(args.citation_ids),
    )
    return ProposedOut(suggestion_id=made)


@agent_tool(
    name="assurance.propose_reconciliation", kind="propose", action="suggestion.create",
    data_class="confidential", input_model=ReconciliationProposalIn, output_model=ProposedOut,
)  # fmt: skip
async def propose_reconciliation(
    agent: AgentContext, args: ReconciliationProposalIn
) -> ProposedOut:
    from sqlalchemy import text

    from abacus.kernel.db import tenant_session
    from abacus.modules.agents.api import create_suggestion

    async with tenant_session(agent.tenant) as session:
        engagement = await session.scalar(
            text("SELECT engagement_id FROM confirmations WHERE id = :c"),
            {"c": args.confirmation_id},
        )
    if engagement != agent.engagement_id:
        raise NotFound("confirmation")
    made = await create_suggestion(
        agent,
        engagement_id=agent.engagement_id,  # type: ignore[arg-type] -- checked above
        target_type="confirmation",
        target_id=args.confirmation_id,
        field_key="reconciling_items",
        proposed_value={
            "t": "json",
            "v": {"items": [{"kind": i.kind, "amount": str(i.amount)} for i in args.items]},
        },
        citation_ids=[c for i in args.items for c in i.citation_ids][:20],
    )
    return ProposedOut(suggestion_id=made)


class ReconcilingItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Annotated[str, Field(min_length=1, max_length=60), Conf]
    amount: Annotated[Decimal, Conf]  # a figure from the respondent's reply or the ledger, cited
    citation_ids: Annotated[list[UUID], Field(min_length=1, max_length=5), Int]


ReconciliationProposalIn.model_rebuild()


# --- A-08-T23: sampling.read_selected_entry (je_testing's selected entry) ----------------------
# Declared here, over sampling's read (`sampling.api.selected_entry`): sampling never imports
# agents (ADR-008). The key and the display come from the client's ledger: untrusted.
class SelectedEntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sample_set_version_id: Annotated[UUID, Int]
    position: Annotated[int, Field(ge=1, le=10_000), Int]


class SelectedEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: Annotated[str, Int]  # `<version>:<position>`
    position: Annotated[int, Int]
    record_key: Annotated[str, Conf]
    selection_reason: Annotated[str, Int]
    amount: Annotated[Decimal | None, Conf] = None
    score: Annotated[str | None, Int] = None


@agent_tool(
    name="sampling.read_selected_entry", kind="read", action="sample_set.read",
    data_class="confidential", input_model=SelectedEntryIn, output_model=SelectedEntryOut,
    untrusted=("record_key",), records_read="sample_item",
)  # fmt: skip
async def read_selected_entry(agent: AgentContext, args: SelectedEntryIn) -> SelectedEntryOut:
    from abacus.modules.sampling.api import selected_entry

    found = await selected_entry(agent.tenant, args.sample_set_version_id, args.position)
    if found is None or found.engagement_id != agent.engagement_id:
        raise NotFound("sample_item")
    return SelectedEntryOut(
        id=f"{args.sample_set_version_id}:{found.position}",
        position=found.position,
        record_key=found.record_key,
        selection_reason=found.selection_reason,
        amount=found.amount,
        score=found.score,
    )


# --- A-09-T29 (DEC-5409): ledger.tb_mapper's one propose tool ---------------------------------


class AccountSuggestionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account_code: Annotated[str, Field(min_length=1, max_length=40), Conf]
    line_id: Annotated[str, Field(min_length=1, max_length=120), Int]
    confidence: Annotated[Literal["high", "medium", "low"], Int]
    reasoning: Annotated[str, Field(max_length=140), Conf]


class AccountSuggestionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mapping_set_id: Annotated[UUID, Int]
    suggestions: Annotated[list[AccountSuggestionIn], Field(min_length=1, max_length=300), Conf]

    def tool_targets(self, agent: AgentContext) -> object:
        from abacus.modules.agents.api import ToolTargets

        return ToolTargets((agent.engagement_id,) if agent.engagement_id is not None else ())


class SuggestedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    suggestion_ids: Annotated[list[UUID], Int]


@agent_tool(
    name="assurance.suggest_account_mappings", kind="propose", action="suggestion.create",
    data_class="confidential", input_model=AccountSuggestionsIn, output_model=SuggestedOut,
)  # fmt: skip
async def suggest_account_mappings(
    agent: AgentContext, args: AccountSuggestionsIn
) -> SuggestedOut:
    """Suggestions only: a person adopts each on AUD-31; the set is confirmed by a person."""
    from abacus.modules.agents.api import create_suggestion
    from abacus.modules.ledger import api as ledger

    found = await ledger.mapping_set_by_id(agent.tenant, args.mapping_set_id)
    if found is None or found.engagement_id != agent.engagement_id:
        raise NotFound("mapping_set")
    made: list[UUID] = []
    for s in args.suggestions:
        made.append(
            await create_suggestion(
                agent,
                engagement_id=found.engagement_id,
                target_type="account_mapping",
                target_id=args.mapping_set_id,
                field_key=f"fs_line:{s.account_code}"[:120],
                proposed_value={
                    "t": "json",
                    "v": {
                        "line_id": s.line_id,
                        "confidence": s.confidence,
                        "reasoning": s.reasoning,
                    },
                },
                citation_ids=[],
            )
        )
    return SuggestedOut(suggestion_ids=made)


# --- A-09-T34 (DEC-5522): consolidation.elimination_proposer's one propose tool -------------


class EliminationLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    caption: Annotated[str, Field(min_length=1, max_length=200), Conf]
    client_entity_id: Annotated[UUID, Int]
    debit: Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=2), Conf]
    credit: Annotated[Decimal, Field(ge=0, max_digits=20, decimal_places=2), Conf]


class EliminationCellIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_version_id: Annotated[UUID, Int]
    sheet: Annotated[str, Field(min_length=1, max_length=120), Conf]
    cell: Annotated[str, Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,5}$"), Int]
    value: Annotated[Decimal, Field(gt=0, max_digits=20, decimal_places=2), Conf]


class EliminationProposalIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: Annotated[str, Field(min_length=1, max_length=200), Int]
    level: Annotated[int, Field(ge=1, le=3), Int]
    description: Annotated[str, Field(min_length=1, max_length=200), Conf]
    note: Annotated[str, Field(max_length=500), Conf] = ""
    computation: Annotated[str, Field(max_length=500), Conf]
    lines: Annotated[list[EliminationLineIn], Field(min_length=2, max_length=20), Conf]
    cell: Annotated[EliminationCellIn | None, Conf] = None


class EliminationProposalsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: Annotated[UUID, Int]
    consolidation_id: Annotated[UUID, Int]
    proposals: Annotated[list[EliminationProposalIn], Field(min_length=1, max_length=40), Conf]

    def tool_targets(self, agent: AgentContext) -> object:
        from abacus.modules.agents.api import ToolTargets

        return ToolTargets((agent.engagement_id,) if agent.engagement_id is not None else ())


class EliminationsProposedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    entry_ids: Annotated[list[UUID], Int]
    blocked: Annotated[int, Field(ge=0), Int]  # proposals whose cell did not verify


@agent_tool(
    name="assurance.propose_eliminations", kind="propose", action="elimination.agent_propose",
    data_class="confidential", input_model=EliminationProposalsIn,
    output_model=EliminationsProposedOut,
)  # fmt: skip
async def propose_eliminations(
    agent: AgentContext, args: EliminationProposalsIn
) -> EliminationsProposedOut:
    """Proposed eliminations only, each naming its run; a person approves and posts on AUD-33.
    A proposal whose evidence cell does not verify through C4 (with code's value) is blocked."""
    from abacus.kernel.uow import uow
    from abacus.modules.adjustments.api import eliminations as adj
    from abacus.modules.evidence.api import CitationAnchor, CitationClaim, record_citations

    made: list[UUID] = []
    blocked = 0
    for p in args.proposals:
        citation_ids: list[UUID] = []
        if p.cell is not None:
            anchor = CitationAnchor(
                "consolidation", args.consolidation_id, p.key[:120], None, agent.engagement_id
            )
            claim = CitationClaim(
                "sheet_cell",
                {
                    "evidence_version_id": str(p.cell.evidence_version_id),
                    "sheet": p.cell.sheet,
                    "cell": p.cell.cell,
                },
                value=str(p.cell.value),
            )
            async with uow(agent.tenant) as tx:
                recorded = await record_citations(tx, actor=agent, anchor=anchor, claims=[claim])
            if not recorded or not recorded[0].verified:
                blocked += 1
                continue
            citation_ids.append(recorded[0].id)
        view = await adj.propose_by_agent(
            agent,
            work_item_id=args.work_item_id,
            consolidation_id=args.consolidation_id,
            level=p.level,
            description=p.description,
            lines=[
                adj.EliminationLine(ln.caption, ln.client_entity_id, ln.debit, ln.credit)
                for ln in p.lines
            ],
            computation=p.computation,
            citation_ids=citation_ids,
        )
        made.append(view.id)
    return EliminationsProposedOut(entry_ids=made, blocked=blocked)
