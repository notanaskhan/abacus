"""The JE scoring workflow's input (A-08-T12): identifiers only (ADR-090)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JeScoringInput:
    tenant_id: str
    je_test_id: str
    score_version: int
    requested_by: str
