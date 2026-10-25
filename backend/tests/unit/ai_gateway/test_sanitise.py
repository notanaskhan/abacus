"""SPEC-006 AC-1/AC-2 (ADR-065): links leave model text unless allowlisted; TASK-5007 adds the
homoglyph-scheme case the word boundary used to hide."""

from __future__ import annotations

import pytest

from abacus.ai_gateway.sanitise import REMOVED, sanitise_text


@pytest.mark.parametrize(
    "text",
    [
        "see https://evil.example/x",
        "see www.evil.example",
        "see [here](https://evil.example)",
        "![x](https://evil.example/p.png)",
        '<a href="https://evil.example">x</a>',
        "open \u04bbttps://evil.example now",  # Cyrillic shha, then "ttps://"
        "glued:https://evil.example",
    ],
)
def test_ac1_links_are_removed(text: str) -> None:
    out = sanitise_text(text)
    assert REMOVED in out
    assert "evil.example" not in out


@pytest.mark.parametrize("text", ["The trial balance ties", "W2 and 1099 forms", "ratio 3:1"])
def test_ac2_plain_text_is_unchanged(text: str) -> None:
    assert sanitise_text(text) == text
