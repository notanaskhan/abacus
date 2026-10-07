"""The failure taxonomy's codes (`docs/product/failure-taxonomy.md`, protected), for suite coverage
(SPEC-005 AC-4; ADR-081). A test keeps these sets identical to the document."""

from __future__ import annotations

from typing import Final

FAILURE_CATEGORIES: Final = frozenset(
    {
        "wrong_period",
        "wrong_entity",
        "incomplete",
        "unbalanced",
        "does_not_tie",
        "duplicate",
        "stale",
        "wrong_currency",
        "altered",
        "irrelevant",
        "unreadable",
    }
)
ADVERSARIAL_CATEGORIES: Final = frozenset(
    {
        "prompt_injection",
        "addressed_instruction",
        "formula_injection",
        "unicode_deception",
        "oversized_field",
        "lookalike_name",
    }
)
