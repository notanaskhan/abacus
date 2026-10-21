"""The mechanical body check: no SSN, TIN, account number or tax amount in an outbound email
(SPEC-050 AC-15; ADR-065, ADR-052). Deterministic code, never a model (ADR-050).

Email is not a secure channel for taxpayer identifiers or the figures of a return. This is the
last check before a message leaves, after the scope check (`scope.py`) has passed; a body that
fails it is blocked and nothing is sent. It is deliberately blunt: a false positive blocks a
message a person can rewrite, a false negative puts a taxpayer ID in a mailbox.

Findings are kinds, never the text that matched, so a log line or an audit row cannot carry the
identifier. A cue word (account, routing, tax and so on) is required for the looser patterns, so
ordinary numbers (dates, counts, phone numbers) pass.
"""

from __future__ import annotations

import re
from typing import Final

# NNN-NN-NNNN or NNN NN NNNN (a Social Security number or an ITIN, which has the same shape).
_SSN: Final = re.compile(r"(?<![\w-])\d{3}[- ]\d{2}[- ]\d{4}(?![\w-])")
# 12-3456789 (an Employer Identification Number).
_EIN: Final = re.compile(r"(?<![\w-])\d{2}-\d{7}(?![\w-])")
# Nine digits run together after a cue naming a taxpayer identifier.
_TIN_CUE: Final = re.compile(
    r"(?i)\b(?:ssn|social security|itin|ein|tin|taxpayer id\w*|tax id\w*)\b"
    r"[^\n]{0,30}?(?<!\d)\d{9}(?!\d)"
)
# An account or routing number: eight to seventeen digits, close after a cue.
_ACCOUNT: Final = re.compile(
    r"(?i)\b(?:account|acct|a/c|routing|aba|iban|bank)\b[^\n]{0,30}?(?<![\d-])\d{8,17}(?![\d-])"
)
# A figure of a return: an amount close to a tax word, either way round.
_AMOUNT: Final = r"[$€£]\s?\d[\d,]*(?:\.\d{1,2})?"
_TAX_WORD: Final = r"(?:tax(?:es)?|withh?eld|withholding|refund|liabilit(?:y|ies)|overpayment)"
_TAX_AMOUNT: Final = re.compile(
    rf"(?i)\b{_TAX_WORD}\b[^\n]{{0,40}}?{_AMOUNT}|{_AMOUNT}[^\n]{{0,40}}?\b{_TAX_WORD}\b"
)

_RULES: Final = (
    ("ssn", _SSN),
    ("tin", _EIN),
    ("tin", _TIN_CUE),
    ("account_number", _ACCOUNT),
    ("tax_amount", _TAX_AMOUNT),
)


def blocked_kinds(*texts: str) -> list[str]:
    """The kinds of sensitive content in the texts (a subject and a body), in a fixed order and
    without repeats. Empty means the message may go."""
    found: list[str] = []
    for kind, pattern in _RULES:
        if kind not in found and any(pattern.search(text) for text in texts):
            found.append(kind)
    return found


class MessageBlocked(Exception):
    """The body check refused the message; nothing was sent. `kinds` says why, never what."""

    def __init__(self, kinds: list[str]) -> None:
        super().__init__("message blocked: " + ", ".join(kinds))
        self.kinds = kinds


def ensure_sendable(*texts: str) -> None:
    kinds = blocked_kinds(*texts)
    if kinds:
        raise MessageBlocked(kinds)
