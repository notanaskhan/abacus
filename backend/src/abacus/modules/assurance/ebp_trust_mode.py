"""A-05-T36: mode `ebp_trust` (A-05 §3 F6; EBP-06; DEC-2249). PROTECTED (red).

The model reads the certified Summary of Net Trust Assets (masked page text) and drafts each fund
line for both dates and the certification points with their page citations, as suggestions. It
never totals: code foots the adopted lines, and a person adopts them as the plan's trial balance
through the ADR P-58 ledger path (`ledger.api.record_document_snapshot`, A-05-T28), which refuses
any line without a verified citation. A certification point is a person's evaluation, insert-only
and human-only (0665, A-05-T35).
"""

from __future__ import annotations

from typing import Final

from abacus.modules.agents.api import ModeInputs, SourcePaper
from abacus.modules.assurance.draft_mappings import documents_for_areas
from abacus.modules.identity.api import AgentContext

MODE: Final = "ebp_trust"
TRUST_AREAS: Final = frozenset({"trust", "investments", "certification"})


async def trust_inputs(actor: AgentContext, paper: SourcePaper) -> ModeInputs:
    """`ebp_trust`'s inputs: the trust report's pages (masked); no figures from code to total."""
    documents = await documents_for_areas(actor, paper, TRUST_AREAS)
    return ModeInputs(documents=documents.documents, facts=())
