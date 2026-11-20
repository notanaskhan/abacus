"""`tax.suggest_tax_lines` (T-06-T38; TASK-8829; DEC-5831): `ledger.tb_mapper` mode `tax_lines`'s
one propose tool. Suggestions only, on the hand-off's source work item; the tax team adopts them on
the return (`modules/tax/tb_mapper_tax_lines.py`). Registered at import."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.agents.api import agent_tool
from abacus.modules.identity.api import AgentContext

Int = classified("internal")
Tri = classified("restricted", tri=True)


class TaxLineSuggestionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    account_no: Annotated[str, Field(min_length=1, max_length=40), Tri]
    tax_line_code: Annotated[str, Field(min_length=1, max_length=80), Int]
    evidence_account_no: Annotated[str, Field(min_length=1, max_length=40), Tri]
    explanation: Annotated[str, Field(max_length=140), Tri]


class TaxLineSuggestionsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_work_item_id: Annotated[UUID, Int]
    target_return_id: Annotated[UUID, Int]
    suggestions: Annotated[list[TaxLineSuggestionIn], Field(min_length=1, max_length=300), Tri]

    def tool_targets(self, agent: AgentContext) -> object:
        from abacus.modules.agents.api import ToolTargets

        return ToolTargets((agent.engagement_id,) if agent.engagement_id is not None else ())


class TaxLineSuggestedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    suggestion_ids: Annotated[list[UUID], Int]


@agent_tool(
    name="tax.suggest_tax_lines", kind="propose", action="suggestion.create", data_class="tri",
    input_model=TaxLineSuggestionsIn, output_model=TaxLineSuggestedOut,
)  # fmt: skip
async def suggest_tax_line_codes(
    agent: AgentContext, args: TaxLineSuggestionsIn
) -> TaxLineSuggestedOut:
    """Suggestions only, on the source work item (the tax team adopts them on the return)."""
    from abacus.kernel.errors import NotFound
    from abacus.modules.agents.api import create_suggestion
    from abacus.modules.engagements.api import work_item_engagement

    engagement_id = await work_item_engagement(agent.tenant, args.source_work_item_id)
    if engagement_id is None or engagement_id != agent.engagement_id:
        raise NotFound("work_item")
    made: list[UUID] = []
    for s in args.suggestions:
        made.append(
            await create_suggestion(
                agent,
                engagement_id=engagement_id,
                target_type="tb_handoff_tax_line",
                target_id=args.source_work_item_id,
                field_key=f"tax_line:{s.account_no}"[:80],
                proposed_value={
                    "t": "json",
                    "v": {
                        "target_return_id": str(args.target_return_id),
                        "tax_line_code": s.tax_line_code,
                        "evidence_account_no": s.evidence_account_no,
                        "explanation": s.explanation,
                    },
                },
                citation_ids=[],
            )
        )
    return TaxLineSuggestedOut(suggestion_ids=made)


__all__ = ["suggest_tax_line_codes"]
