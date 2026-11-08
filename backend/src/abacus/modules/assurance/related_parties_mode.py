"""A-05-T56: mode `related_parties` (A-05 F11; AUD-27; AU-C 550; DEC-2711). Red zone.

The model compares the vendor and customer masters with the minutes and the HR roster and proposes
candidates, each with what matched and the document that shows it. It never names a person from
the minutes or the roster (a director is "a director, Feb 12, 2026 board minutes"), never counts
(code reports how many records were compared) and never concludes: a person screens a candidate
out with a reason or raises an exception (AUD-27, A-05-T53).
"""

from __future__ import annotations

from typing import Final

from abacus.modules.agents.api import ModeInputs, SourcePaper
from abacus.modules.assurance.draft_mappings import documents_for_areas
from abacus.modules.identity.api import AgentContext

MODE: Final = "related_parties"
RELATED_PARTY_AREAS: Final = frozenset(
    {"related_parties", "minutes", "vendor_master", "customer_master", "hr_roster"}
)


async def related_party_inputs(actor: AgentContext, paper: SourcePaper) -> ModeInputs:
    """The masters, minutes and roster (masked page text); nothing for the model to count."""
    documents = await documents_for_areas(actor, paper, RELATED_PARTY_AREAS)
    return ModeInputs(documents=documents.documents, waiting_on=documents.waiting_on, facts=())
