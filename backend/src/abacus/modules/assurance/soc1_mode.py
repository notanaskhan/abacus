"""A-04-T35: mode `soc1`, the SOC 1 reader and CUEC mapper (A-04 §3.7 AC7.6; AUD-10; DEC-2247).
PROTECTED (red).

The model reads the service organization's SOC 1 Type 2 report and drafts its facts as
suggestions: period, opinion, objectives tested, subservice carve-outs, exceptions with a proposed
impact, and CUECs with page references (each verified against the word layer by C4 before it is
kept). The mapping hands the model the team's control activities as facts (for CUEC mapping
suggestions) and never a period comparison: `compute/soc_gap.py` computes that after a person
adopts the period (DEC-2236). Reliance stays the engagement partner's card; the mode never
raises it.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.modules.agents.api import ModeInputs, SourcePaper
from abacus.modules.assurance.draft_mappings import documents_for_areas
from abacus.modules.identity.api import AgentContext

MODE: Final = "soc1"
SOC_AREAS: Final = frozenset({"service_organizations", "soc_reports"})


def _fact(name: str, value: str) -> tuple[str, dict[str, object]]:
    return (name, {"t": "text", "v": value})


async def soc1_inputs(actor: AgentContext, paper: SourcePaper) -> ModeInputs:
    """`soc1`'s inputs: the SOC report pages (masked) and the team's control activities."""
    documents = await documents_for_areas(actor, paper, SOC_AREAS)
    async with tenant_session(actor.tenant) as session:
        controls = (
            await session.execute(
                text(
                    "SELECT id, process_name FROM control_activities WHERE work_item_id = :w "
                    "ORDER BY process_name"
                ),
                {"w": paper.work_item_id},
            )
        ).all()
    facts = tuple(
        _fact(f"control_activity_{n}", name) for n, (_, name) in enumerate(controls, start=1)
    )
    return ModeInputs(documents=documents.documents, facts=facts)
