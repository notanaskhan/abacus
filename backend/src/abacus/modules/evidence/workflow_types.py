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
class BackfillInput:
    """P-03-T05: the trust layer backfill's cursor. Ids only: the last version and inbox file
    it reached (ordered by id), how many it has handed to `upload.words` so far, and how many of
    those failed after their retries (passed, never retried in this run)."""

    tenant_id: str
    after_version: str | None = None
    after_inbox: str | None = None
    done: int = 0
    failed: int = 0
