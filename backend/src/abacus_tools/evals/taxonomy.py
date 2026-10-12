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
        "draft",  # SPEC-030 (TASK-058)
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

# What each agent's suite must cover (SPEC-005 AC-4): the categories its purpose involves. The
# screener reads whole trial balances from clients' systems, so it meets all of them.
REQUIRED_COVERAGE: Final[dict[str, frozenset[str]]] = {
    "evidence.screener": (FAILURE_CATEGORIES - {"draft"}) | ADVERSARIAL_CATEGORIES,
    # SPEC-030: what code can't decide, and the adversarial content a document can carry.
    "evidence.upload_reviewer": frozenset({"irrelevant", "draft", "altered"})
    | (ADVERSARIAL_CATEGORIES - {"oversized_field", "lookalike_name"}),
}
