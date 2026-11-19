"""Payloads of `PostingBatchWorkflow` (C-02-T18). Identifiers only (ADR-090)."""

from __future__ import annotations

from dataclasses import dataclass

RUN = "adjustments.run_posting_batch"


@dataclass(frozen=True)
class PostingInput:
    tenant_id: str
    batch_id: str


@dataclass(frozen=True)
class PostingResult:
    status: str
