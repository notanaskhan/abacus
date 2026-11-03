"""A-04-T29: mode `ic` (A-04 §3.6 AC6.1, AC6.2, AC6.5; AUD-09; DEC-2220). PROTECTED (red).

The Internal Control draft writes the Exceptions sheet's rows as **suggestions**: matter,
description, COSO component and a proposed severity (never concluded), each cited to evidence.
A misstatement candidate's amount is kept apart from the control matter, and **code** compares it
to performance materiality and the clearly trivial threshold (ADR-050): "48,600 below PM 189,150
and above CT 12,610". The mode's mapping hands the model code's PM and CT and that comparison as
facts, never the materiality arithmetic. A person adopts rows; adopted rows are recorded
through `internal_control.record_exceptions` (the proposals carry their suggestion ids).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from abacus.modules.agents.api import ModeInputs, SourcePaper
from abacus.modules.assurance import materiality
from abacus.modules.assurance.draft_mappings import documents_for_areas
from abacus.modules.identity.api import AgentContext

MODE: Final = "ic"
IC_AREAS: Final = frozenset({"internal_control", "walkthroughs", "control_testing"})
Position = Literal["above_pm", "between", "below_ct"]


@dataclass(frozen=True)
class Comparison:
    amount: Decimal
    pm: Decimal
    ct: Decimal
    position: Position

    @property
    def narration(self) -> str:
        """Code's sentence, in whole dollars without "$" (AC6.5)."""
        a, pm, ct = (f"{x:,.0f}" for x in (self.amount, self.pm, self.ct))
        if self.position == "above_pm":
            return f"{a} above PM {pm}"
        if self.position == "below_ct":
            return f"{a} below CT {ct}"
        return f"{a} below PM {pm} and above CT {ct}"


def compare(amount: Decimal, pm: Decimal, ct: Decimal) -> Comparison:
    """Where a misstatement candidate sits against PM and CT (amounts are absolute)."""
    value = abs(amount)
    if value > pm:
        position: Position = "above_pm"
    elif value <= ct:
        position = "below_ct"
    else:
        position = "between"
    return Comparison(value, pm, ct, position)


def _fact(name: str, value: object) -> tuple[str, dict[str, object]]:
    kind = "decimal" if isinstance(value, Decimal) else "text"
    return (name, {"t": kind, "v": str(value)})


def comparison_facts(
    pm: Decimal, ct: Decimal, amounts: Sequence[tuple[int, Decimal]]
) -> tuple[tuple[str, dict[str, object]], ...]:
    out = [_fact("performance_materiality", pm), _fact("clearly_trivial", ct)]
    for row, amount in amounts:
        out.append(_fact(f"row_{row}_compared_to_materiality", compare(amount, pm, ct).narration))
    return tuple(out)


async def ic_inputs(actor: AgentContext, paper: SourcePaper) -> ModeInputs:
    """`ic`'s inputs: the walkthrough notes and control evidence (masked), and code's PM and CT."""
    documents = await documents_for_areas(actor, paper, IC_AREAS)
    versions = await materiality.versions_of(actor.tenant, paper.work_item_id)
    current = materiality.in_force(versions)
    facts: tuple[tuple[str, dict[str, object]], ...] = ()
    if current is not None:
        facts = comparison_facts(current.pm, current.ct, ())
    return ModeInputs(documents=documents.documents, facts=facts)
