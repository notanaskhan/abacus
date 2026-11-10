"""A-05-T55: mode `ebp_form5500` (A-05 §3 F9; EBP-07; DEC-2710). Red zone.

The model reads the draft Form 5500's Schedule H and Part IV (masked page text; OCR where scanned,
P-11) and drafts each line and answer with its page citation, proposes the documented basis
difference behind a code-computed difference, and drafts the Note 8 sentence and the 4i and 4a
rows. It never ties or classifies: code computes every difference (`compute/ebp/form5500`), and a
person classifies a line as a reconciling item (`ebp_form5500.document_reconciling_item`). Its
outputs are C3 suggestions only.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.modules.agents.api import ModeInputs, SourcePaper
from abacus.modules.assurance.draft_mappings import documents_for_areas
from abacus.modules.identity.api import AgentContext

MODE: Final = "ebp_form5500"
FORM5500_AREAS: Final = frozenset({"form5500", "schedule_h", "part_iv", "contributions"})
_DIFFERENCES = text(
    """
    SELECT l.line_code, l.difference FROM ebp_form5500_lines l
      JOIN ebp_form5500_drafts d ON d.id = l.draft_id
     WHERE l.work_item_id = :w AND d.status <> 'superseded' AND l.difference IS NOT NULL
       AND l.difference <> 0
     ORDER BY l.line_code
    """
)
_LATE = text(
    "SELECT COALESCE(sum(principal), 0) FROM ebp_late_remittances "
    "WHERE work_item_id = :w AND schedule_h_4a"
)


def difference_facts(
    differences: list[tuple[str, Decimal]], late_total: Decimal
) -> tuple[tuple[str, dict[str, object]], ...]:
    """Code's numbers by name: the model cites them by reference, never computes them."""
    facts: list[tuple[str, dict[str, object]]] = [
        (f"diff.{code}", {"t": "decimal", "v": str(amount)}) for code, amount in differences
    ]
    facts.append(("late_deposits_4a", {"t": "decimal", "v": str(late_total)}))
    return tuple(facts)


async def form5500_inputs(actor: AgentContext, paper: SourcePaper) -> ModeInputs:
    """`ebp_form5500`'s inputs: the draft form's and the supporting pages (masked), and code's
    differences and the late deposits as facts."""
    documents = await documents_for_areas(actor, paper, FORM5500_AREAS)
    async with tenant_session(actor.tenant) as session:
        differences = [
            (str(r.line_code), Decimal(r.difference))
            for r in await session.execute(_DIFFERENCES, {"w": paper.work_item_id})
        ]
        late_total = Decimal(
            (await session.execute(_LATE, {"w": paper.work_item_id})).scalar_one()
        )
    return ModeInputs(
        documents=documents.documents,
        waiting_on=documents.waiting_on,
        facts=difference_facts(differences, late_total),
    )
