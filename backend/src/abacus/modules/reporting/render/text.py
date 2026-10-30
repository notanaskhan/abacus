"""Text that reaches a page (ADR-052; SPEC-520 AC-8; P-11 §4.4).

Every string a render places on paper, whether firm wording from a template or a variable value
resolved from client data, passes through `literal()`: HTML-escaped, control characters dropped,
zero-width and bidi-override characters removed, and the value isolated in `<bdi>` so a
right-to-left run cannot reorder the line around it. Nothing is ever interpreted: `<script>`,
`=HYPERLINK(…)` and `{{…}}` print as the characters they are.

`missing_glyph`: the vendored faces carry the @fontsource "latin" subset and nothing else, and the
image ships no fallback font, so a character outside that range would render as a box or vanish.
`uncovered()` names such characters before WeasyPrint runs, so the render refuses instead.
"""

from __future__ import annotations

import unicodedata
from html import escape
from typing import Final

# Zero-width and invisible formatting characters, and every bidi embedding, override or isolate.
_DROP: Final = frozenset(
    {0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0xFEFF}
    | set(range(0x202A, 0x202F))  # embeddings and overrides
    | set(range(0x2066, 0x206A))  # isolates
)
_KEEP_CONTROLS: Final = frozenset({"\n", "\t"})

# The @fontsource "latin" subset's unicode-range: the faces in `fonts/` cover exactly this.
_COVERED_RANGES: Final = (
    (0x0020, 0x007E),
    (0x00A0, 0x00FF),
    (0x0131, 0x0131),
    (0x0152, 0x0153),
    (0x02BB, 0x02BC),
    (0x02C6, 0x02C6),
    (0x02DA, 0x02DA),
    (0x02DC, 0x02DC),
    (0x0304, 0x0304),
    (0x0308, 0x0308),
    (0x0329, 0x0329),
    (0x2000, 0x206F),
    (0x20AC, 0x20AC),
    (0x2122, 0x2122),
    (0x2191, 0x2191),
    (0x2193, 0x2193),
    (0x2212, 0x2212),
    (0x2215, 0x2215),
    (0xFFFD, 0xFFFD),
)


def clean(value: str) -> str:
    """`value` without control, zero-width or bidi formatting characters (newlines and tabs
    stay; the layout turns them into spaces)."""
    out: list[str] = []
    for ch in unicodedata.normalize("NFC", value):
        if ord(ch) in _DROP:
            continue
        if unicodedata.category(ch) == "Cc" and ch not in _KEEP_CONTROLS:
            continue
        out.append(" " if ch in _KEEP_CONTROLS else ch)
    return "".join(out)


def literal(value: str, *, isolate: bool = False) -> str:
    """HTML for `value` printed exactly as characters (AC-8). `isolate` wraps a variable's value
    in `<bdi>` so its direction cannot leak into the surrounding line."""
    text = escape(clean(value), quote=True)
    return f"<bdi>{text}</bdi>" if isolate else text


def _covered(ch: str) -> bool:
    point = ord(ch)
    return any(low <= point <= high for low, high in _COVERED_RANGES)


def uncovered(texts: list[str]) -> list[str]:
    """Distinct characters the vendored faces cannot draw, as `U+XXXX`, sorted."""
    found = {ch for text in texts for ch in clean(text) if not _covered(ch)}
    return sorted(f"U+{ord(ch):04X}" for ch in found)
