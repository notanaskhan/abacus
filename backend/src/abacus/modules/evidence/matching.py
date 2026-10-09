"""Suggested request items for an inbox file (SPEC-023 Q2; TASK-039). Pure code.

Only the cleaned file name is read, never the file. A suggestion is a proposal with its score and
the words that matched; a person always confirms (ADR-005). This rule baseline is what a later
model matcher must beat (Q3).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from abacus.modules.requests.api import RequestItemView, classify

MAX_SUGGESTIONS: Final = 3
MIN_SCORE: Final = 35
RULE_BONUS: Final = 40
TAKES_EVIDENCE: Final = frozenset({"open", "received", "needs_revision"})
_STOP: Final = frozenset(
    {
        "a",
        "an",
        "and",
        "the",
        "of",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "all",
        "any",
        "per",
        "our",
        "your",
        "copy",
        "final",
        "draft",
        "scan",
        "scanned",
        "file",
        "document",
        "doc",
        "pdf",
        "xlsx",
        "xls",
        "csv",
        "docx",
        "png",
        "jpg",
        "jpeg",
        "v",
        "version",
    }
)
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")
_SPLIT = re.compile(r"[^A-Za-z0-9]+")
_VERSION = re.compile(r"v\d+")


@dataclass(frozen=True)
class Suggestion:
    request_item_id: UUID
    score: int
    matched: tuple[str, ...]


def words(text: str) -> set[str]:
    """Significant lower-case words: camel case and separators split; numbers, short words and
    stop words dropped; the extension (if any) is just another stop word."""
    spaced = _CAMEL.sub(" ", text)
    return {
        w
        for w in (part.lower() for part in _SPLIT.split(spaced))
        if len(w) > 1 and not w.isdigit() and w not in _STOP and not _VERSION.fullmatch(w)
    }


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def suggest(file_name: str, items: Sequence[RequestItemView]) -> list[Suggestion]:
    """Up to three items that take evidence, best first, each scoring at least 35."""
    file_words = {_stem(w) for w in words(file_name)}
    file_rule = classify(file_name, "").rule_id
    found: list[Suggestion] = []
    for item in items:
        if item.status not in TAKES_EVIDENCE:
            continue
        item_words = {_stem(w) for w in words(item.description)}
        matched = sorted(file_words & item_words)
        score = round(100 * len(matched) / len(item_words)) if item_words else 0
        same_rule = (
            file_rule is not None
            and classify(item.description, item.audit_area).rule_id == file_rule
        )
        if same_rule:
            score += RULE_BONUS
        score = min(score, 100)
        if score >= MIN_SCORE:
            found.append(Suggestion(item.id, score, tuple(matched)))
    found.sort(key=lambda s: (-s.score, str(s.request_item_id)))
    return found[:MAX_SUGGESTIONS]
