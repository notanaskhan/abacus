"""Code flags on an intake attachment (N-01-T17; N-01 §3.4; INB-02 a, b, c, g; DEC-1177). Pure.

Code flags first; the matcher only proposes. Each flag has a severity the triage sheet and apply
honour (N-01-T18): `block_bulk` keeps the row out of "File n as suggested", `force_hold` leaves
only "Hold — ask client", `info` informs.

| kind | when | severity |
|---|---|---|
| `unreadable` | an image (HEIC too) or a PDF without a text layer, before OCR | block_bulk |
| `duplicate_hash` | the SHA-256 of a client's version or an earlier attachment | block_bulk |
| `wrong_year` | a tax year none of the client's active work items is for | block_bulk |
| `tin_mismatch` | a detected last four that is not on the client's record | force_hold |
| `possible_replacement` | a filed version of the same family, issuer and tax year | info |
| `corrected_form` | a corrected form (W-2c, "Corrected") | info |
| `low_confidence` | the rules' overall confidence below the parameter file's floor | block_bulk |
| `ambiguous_candidates` | two destinations within 5 points and the top below 90 | block_bulk |

`facts` holds identifiers, years and masked last fours only (0293's CHECK keeps it small).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final
from uuid import UUID

CHECKER_VERSION: Final = "flags-1"
_AMBIGUOUS_GAP: Final = 5
_AMBIGUOUS_TOP: Final = 90
_PDF: Final = "application/pdf"


@dataclass(frozen=True)
class FlagFacts:
    """What code knows about one attachment when it flags it."""

    media_type: str
    has_text_layer: bool
    tax_year: int | None
    tin_last4: str | None
    corrected: bool | None
    confidence: float
    low_confidence_below: float
    duplicate_version_id: UUID | None = None
    duplicate_attachment_id: UUID | None = None
    expected_years: frozenset[int] = frozenset()
    entity_last4s: frozenset[str] = frozenset()
    replacement_version_id: UUID | None = None
    candidate_scores: Sequence[int] = field(default_factory=tuple)


@dataclass(frozen=True)
class CodeFlag:
    kind: str
    severity: str
    facts: dict[str, object]
    ref_evidence_version_id: UUID | None = None


def unreadable(media_type: str, has_text_layer: bool) -> bool:
    """A file code can't read yet: an image, or a PDF without a text layer (a scan)."""
    return media_type.startswith("image/") or (media_type == _PDF and not has_text_layer)


def ambiguous(scores: Sequence[int]) -> tuple[int, int] | None:
    """The top two scores when they are within 5 points and the top is below 90."""
    if len(scores) < 2:
        return None
    top, second = sorted(scores, reverse=True)[:2]
    return (top, second) if top - second <= _AMBIGUOUS_GAP and top < _AMBIGUOUS_TOP else None


def code_flags(given: FlagFacts) -> list[CodeFlag]:
    """The flags for one attachment, in a stable order."""
    flags: list[CodeFlag] = []
    cannot_read = unreadable(given.media_type, given.has_text_layer)
    if cannot_read:
        flags.append(CodeFlag("unreadable", "block_bulk", {"media_type": given.media_type}))
    if given.duplicate_version_id is not None or given.duplicate_attachment_id is not None:
        facts: dict[str, object] = {}
        if given.duplicate_version_id is not None:
            facts["duplicate_of_version"] = str(given.duplicate_version_id)
        if given.duplicate_attachment_id is not None:
            facts["duplicate_of_attachment"] = str(given.duplicate_attachment_id)
        flags.append(CodeFlag("duplicate_hash", "block_bulk", facts, given.duplicate_version_id))
    if (
        given.tax_year is not None
        and given.expected_years
        and given.tax_year not in given.expected_years
    ):
        flags.append(
            CodeFlag(
                "wrong_year",
                "block_bulk",
                {"tax_year": given.tax_year, "expected_year": max(given.expected_years)},
            )
        )
    if (
        given.tin_last4 is not None
        and given.entity_last4s
        and given.tin_last4 not in given.entity_last4s
    ):
        flags.append(
            CodeFlag(
                "tin_mismatch",
                "force_hold",
                {"detected_last4": given.tin_last4, "record_last4": sorted(given.entity_last4s)},
            )
        )
    if given.replacement_version_id is not None:
        flags.append(
            CodeFlag(
                "possible_replacement",
                "info",
                {"replaces_version": str(given.replacement_version_id)},
                given.replacement_version_id,
            )
        )
    if given.corrected:
        flags.append(CodeFlag("corrected_form", "info", {}))
    if not cannot_read and given.confidence < given.low_confidence_below:
        flags.append(
            CodeFlag("low_confidence", "block_bulk", {"confidence": round(given.confidence, 2)})
        )
    pair = ambiguous(given.candidate_scores)
    if pair is not None:
        flags.append(
            CodeFlag("ambiguous_candidates", "block_bulk", {"top": pair[0], "second": pair[1]})
        )
    return flags
