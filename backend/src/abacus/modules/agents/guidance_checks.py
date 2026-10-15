"""Code checks on a drafted guidance text before anyone sees it (SPEC-035 §4.3; TASK-072).
PROTECTED.

Form, not judgement (ADR-050): length, no contact details or links, no amounts, dates or years, no
model talk or instructions to the auditor, not a copy of the request, and no names that weren't
in the input (D2). A draft that fails any check is recorded with its reasons and never shown.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Final

from abacus.modules.agents.handoff import GuidanceDraft

_URL: Final = re.compile(r"https?://|www\.|\b[a-z0-9-]+\.(?:com|net|org|io|co)\b", re.I)
_EMAIL: Final = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")
_PHONE: Final = re.compile(r"(?:\+?\d[\s().-]?){7,}")
_AMOUNT: Final = re.compile(r"[$€£]\s?\d|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|\b\d+\.\d{2}\b")
_YEAR: Final = re.compile(r"\b(?:19|20)\d{2}\b")
_MONTH: Final = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE: Final = re.compile(
    rf"\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b|\b{_MONTH}\s+\d{{1,2}}\b|\b\d{{1,2}}\s+{_MONTH}",
    re.I,
)
_MODEL_TALK: Final = re.compile(
    r"\bas an ai\b|\blanguage model\b|\bI\b|\bI'm\b|\bI am\b|\bmy\b", re.I
)
_TO_AUDITOR: Final = re.compile(
    r"(?:^|[.!?]\s+)(?:auditor|reviewer)s?\s*:|\bnote to the (?:auditor|reviewer)\b"
    r"|\bno testing\b"
    r"|\bignore (?:the|all|previous)\b"
    r"|\bno (?:documents?|evidence) (?:is|are) (?:needed|required)\b",
    re.I,
)
_NAME: Final = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")
# Document and audit words that may be capitalised without coming from the input (D2).
ALLOWED_NAMES: Final = frozenset(
    {
        "trial balance",
        "general ledger",
        "balance sheet",
        "income statement",
        "bank statement",
        "bank statements",
        "accounts receivable",
        "accounts payable",
        "fixed assets",
        "form w",
        "board of directors",
        "certificate of insurance",
    }
)
MAX_OVERLAP: Final = 0.8


def _words(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"[a-z0-9]+", folded)


def _overlap(draft: str, description: str) -> float:
    words, source = _words(draft), set(_words(description))
    return sum(w in source for w in words) / len(words) if words else 0.0


def invented_names(text: str, given: Iterable[str]) -> list[str]:
    """Capitalised multi-word names not in the input and not a sentence's opening words."""
    source = " ".join(given).casefold()
    found: list[str] = []
    for match in _NAME.finditer(text):
        name = match.group(1)
        start = match.start()
        before = text[:start].rstrip()
        sentence_start = not before or before[-1] in ".!?:;\"'("
        candidate = name.casefold()
        if candidate in ALLOWED_NAMES or any(a in candidate for a in ALLOWED_NAMES):
            continue
        if candidate in source:
            continue
        if sentence_start and len(name.split()) <= 2:
            continue  # "Your Company" style openings
        found.append(name)
    return found


def check_draft(
    draft: GuidanceDraft, *, description: str, area: str, year_end_year: int | None = None
) -> list[str]:
    """The reason codes a draft fails on; empty when it may be shown."""
    texts = [draft.why, draft.good_looks_like]
    joined = " ".join(texts)
    reasons: list[str] = []
    if not draft.why.strip() or not draft.good_looks_like.strip():
        reasons.append("empty")
    if _URL.search(joined):
        reasons.append("link")
    if _EMAIL.search(joined):
        reasons.append("email")
    if _PHONE.search(joined):
        reasons.append("phone")
    if _AMOUNT.search(joined):
        reasons.append("amount")
    # Any specific date or year, the engagement's own too: guidance is copied on roll-forward
    # (SPEC-031 AC-8), where a date would be wrong (TASK-072).
    if _DATE.search(joined) or _YEAR.search(joined):
        reasons.append("date")
    if _MODEL_TALK.search(joined):
        reasons.append("model_talk")
    if _TO_AUDITOR.search(joined):
        reasons.append("instruction")
    if max(_overlap(t, description) for t in texts) > MAX_OVERLAP:
        reasons.append("copies_description")
    if invented_names(joined, (description, area)):
        reasons.append("invented_name")
    return reasons
