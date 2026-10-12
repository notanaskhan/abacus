"""Suggested request items for an inbox file (SPEC-023 Q2; TASK-039; SPEC-033 TASK-064). Pure code.

The cleaned file name, and (SPEC-033) the facts SPEC-029's extraction read from the file: its kind,
dates, account digits and holder, from the extraction's columns only. A suggestion is a proposal
with its score and fixed-label reasons; a person always confirms (ADR-005). Code computes; the
matcher agent (TASK-065) handles what code can't (ADR-050).
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID

from abacus.modules.evidence.checks import normalised_name
from abacus.modules.evidence.models import UploadExtraction
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


# SPEC-033 (TASK-064 D1): points per content reason; the file name counts at 40%.
KIND_POINTS: Final = 50
DATE_POINTS: Final = 20
ACCOUNT_POINTS: Final = 30
HOLDER_POINTS: Final = 10
NAME_WEIGHT: Final = 0.4
_KINDS: Final = {"bank_statement": frozenset({"bank_statement"})} | {
    "aging": frozenset({"ar_aging", "ap_aging"})  # D2: receivables and payables alike
}


@dataclass(frozen=True)
class Reason:
    code: str  # kind | date | account | holder | file_name
    value: str | None = None  # bank_statement or aging; an ISO date; four digits; words


@dataclass(frozen=True)
class Suggestion:
    request_item_id: UUID
    score: int
    matched: tuple[str, ...]
    source: str = "file_name"  # content when any content reason applies
    reasons: tuple[Reason, ...] = ()


@dataclass(frozen=True)
class ContentFacts:
    """What the extraction read that matching uses (SPEC-033 §4.1)."""

    kind: str | None  # bank_statement | aging | None
    period_start: date | None = None
    period_end: date | None = None
    as_of: date | None = None
    last4: str | None = None
    holder: str | None = None


@dataclass(frozen=True)
class EngagementFacts:
    year_end: date
    entity: str
    needed: Mapping[UUID, frozenset[str]]  # per bank statement item: digits still needed


def facts_of(row: UploadExtraction | None) -> ContentFacts | None:
    """None for an unreadable or not-yet-extracted file: the file name decides alone."""
    if row is None or row.status != "extracted":
        return None
    kind = None
    if row.period_end is not None and (row.closing is not None or row.account_last4 is not None):
        kind = "bank_statement"
    elif row.as_of is not None and row.grand_total is not None:
        kind = "aging"
    return ContentFacts(
        kind, row.period_start, row.period_end, row.as_of, row.account_last4, row.entity_name
    )


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


def _name_score(
    file_words: set[str], file_rule: str | None, item: RequestItemView
) -> tuple[int, tuple[str, ...]]:
    item_words = {_stem(w) for w in words(item.description)}
    matched = tuple(sorted(file_words & item_words))
    score = round(100 * len(matched) / len(item_words)) if item_words else 0
    if file_rule is not None and classify(item.description, item.audit_area).rule_id == file_rule:
        score += RULE_BONUS
    return min(score, 100), matched


def _content(
    item: RequestItemView, facts: ContentFacts, context: EngagementFacts
) -> tuple[int, list[Reason]]:
    """Points and reasons for one item; nothing unless the file is the kind the item asks for."""
    if facts.kind is None or item.document_kind not in _KINDS[facts.kind]:
        return 0, []
    points, reasons = KIND_POINTS, [Reason("kind", facts.kind)]
    year_end = context.year_end
    if facts.kind == "bank_statement":
        start, end = facts.period_start, facts.period_end
        if end is not None and (start or end) <= year_end <= end:
            points += DATE_POINTS
            reasons.append(Reason("date", year_end.isoformat()))
    elif facts.as_of == year_end:
        points += DATE_POINTS
        reasons.append(Reason("date", year_end.isoformat()))
    if facts.last4 is not None and (
        facts.last4 in context.needed.get(item.id, frozenset())
        or facts.last4 in re.sub(r"\D", "", item.description)
    ):
        points += ACCOUNT_POINTS
        reasons.append(Reason("account", facts.last4))
    if facts.holder and context.entity:
        found = normalised_name(facts.holder)
        if found and found == normalised_name(context.entity):
            points += HOLDER_POINTS
            reasons.append(Reason("holder"))
    return points, reasons


def suggest(
    file_name: str,
    items: Sequence[RequestItemView],
    facts: ContentFacts | None = None,
    context: EngagementFacts | None = None,
) -> list[Suggestion]:
    """Up to three items that take evidence, best first, each scoring at least 35. Without
    content facts, the file name decides alone (SPEC-023)."""
    file_words = {_stem(w) for w in words(file_name)}
    file_rule = classify(file_name, "").rule_id
    found: list[Suggestion] = []
    for item in items:
        if item.status not in TAKES_EVIDENCE:
            continue
        name, matched = _name_score(file_words, file_rule, item)
        reasons: list[Reason] = []
        if facts is not None and context is not None:
            points, reasons = _content(item, facts, context)
            score = min(100, points + round(NAME_WEIGHT * name))
        else:
            score = name
        if matched:
            reasons.append(Reason("file_name", ", ".join(matched)))
        if score >= MIN_SCORE:
            content = any(r.code != "file_name" for r in reasons)
            found.append(
                Suggestion(
                    item.id,
                    score,
                    matched,
                    "content" if content else "file_name",
                    tuple(reasons),
                )
            )
    found.sort(key=lambda s: (-s.score, str(s.request_item_id)))
    return found[:MAX_SUGGESTIONS]
