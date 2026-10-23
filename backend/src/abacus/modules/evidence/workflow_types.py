"""The upload processing workflow's inputs and outcomes (SPEC-029; TASK-054). PROTECTED.

Identifiers only: the workflow never carries file content or extracted text (ADR-017).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

VERSION: Final = "version"  # an evidence version (an item upload, or an assigned inbox file)
INBOX: Final = "inbox"  # an inbox file waiting to be assigned


@dataclass(frozen=True)
class UploadInput:
    tenant_id: str
    kind: str  # VERSION | INBOX
    source_id: str


@dataclass(frozen=True)
class LegalHoldInput:
    """`LegalHoldApply` and `LegalHoldRelease` (Q-02-T29): the hold, by identifier only."""

    tenant_id: str
    hold_id: str


# Activity error types the hold workflows don't retry (the hold isn't in the tenant).
HOLD_NOT_FOUND: Final = "NotFound"
