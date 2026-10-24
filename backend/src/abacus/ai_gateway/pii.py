"""The TIN backstop on model context (ADR-167 §2; Q-02 AC-22; Q-02-T32). PROTECTED.

Before any network call, `call` scans the system prompt and every part of the assembled context
(the firm, engagement and examples layers, the task JSON and each `<untrusted>` block) for an
unmasked SSN, ITIN or EIN form that passes its validity rules (`kernel.tin_patterns`). A match
refuses the call with boundary reason `pii_in_context` (`boundary.refuse`): audited with the
reason and the part's name, never the value, never retried or rerouted, on every route.

P-03's masked agent material is the main control; this is the second line. A refusal is a defect
report against the context builder that let the value through, never a reason to loosen the scan.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from abacus.ai_gateway.context import AssembledContext
from abacus.kernel.tin_patterns import find_tins, normalised

ContextPart = Literal["instructions", "firm", "engagement", "examples", "task", "untrusted"]
# Audited by index (`Ref(part=...)`): append only, so recorded indices keep their meaning.
PARTS: Final[tuple[ContextPart, ...]] = (
    "instructions",
    "firm",
    "engagement",
    "examples",
    "task",
    "untrusted",
)
_UNTRUSTED: Final = re.compile(r'<untrusted name="[^"]*">\n.*?\n</untrusted>', re.DOTALL)


def _in_untrusted(task: str, start: int) -> bool:
    return any(block.start() <= start < block.end() for block in _UNTRUSTED.finditer(task))


def part_with_tin(system: str, context: AssembledContext) -> ContextPart | None:
    """The first part of this call's input holding an unmasked TIN form, or None."""
    if find_tins(system):
        return "instructions"
    for layer in context.layers:
        text = normalised(layer.text)
        matches = find_tins(text)
        if not matches:
            continue
        if layer.name != "task":
            return layer.name
        return "untrusted" if any(_in_untrusted(text, m.start) for m in matches) else "task"
    return None


__all__ = ["PARTS", "ContextPart", "part_with_tin"]
