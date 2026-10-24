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


@dataclass(frozen=True)
class BackfillInput:
    """P-03-T05: the trust layer backfill's cursor. Ids only: the last version and inbox file
    it reached (ordered by id), how many it has handed to `upload.words` so far, and how many of
    those failed after their retries (passed, never retried in this run)."""

    tenant_id: str
    after_version: str | None = None
    after_inbox: str | None = None
    done: int = 0
    failed: int = 0


@dataclass(frozen=True)
class WithdrawalPurgeInput:
    """`EvidenceWithdrawalPurge` (P-06-T19; ADR-162 §7): the withdrawn version, and how long to
    wait before the next erase attempt (the window first, then what the attempt answered)."""

    tenant_id: str
    evidence_version_id: str
    wait_seconds: int
    attempts: int = 0
