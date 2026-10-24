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
from abacus.kernel.tin_patterns import find_tins

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
_ESCAPE: Final = re.compile(r'\\(["\\/bfnrt]|u[0-9a-fA-F]{4})')
_ESCAPES: Final = {"b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}


def _unescaped(match: re.Match[str]) -> str:
    code = match.group(1)
    if code.startswith("u"):
        return chr(int(code[1:], 16))
    return _ESCAPES.get(code, code)


def _decoded(text: str) -> str:
    """The values as written, not their JSON encoding: the task layer is JSON, so a newline, tab
    or `<` beside a TIN (or a tab between its groups) is an escape sequence in the text."""
    return _ESCAPE.sub(_unescaped, text)


def _holds_tin(text: str) -> bool:
    return bool(find_tins(_decoded(text)))


def _task_segments(task: str) -> list[tuple[ContextPart, str]]:
    """The task layer split into its trusted JSON and its `<untrusted>` blocks, found in the
    encoded text (an encoded value cannot open or close a block)."""
    segments: list[tuple[ContextPart, str]] = []
    at = 0
    for block in _UNTRUSTED.finditer(task):
        segments.append(("task", task[at : block.start()]))
        segments.append(("untrusted", block.group()))
        at = block.end()
    segments.append(("task", task[at:]))
    return segments


def part_with_tin(system: str, context: AssembledContext) -> ContextPart | None:
    """The first part of this call's input holding an unmasked TIN form, or None. An untrusted
    block is named before the task JSON around it."""
    if _holds_tin(system):
        return "instructions"
    for layer in context.layers:
        if layer.name != "task":
            if _holds_tin(layer.text):
                return layer.name
            continue
        hits = {part for part, text in _task_segments(layer.text) if _holds_tin(text)}
        if hits:
            return "untrusted" if "untrusted" in hits else "task"
    return None


__all__ = ["PARTS", "ContextPart", "part_with_tin"]
