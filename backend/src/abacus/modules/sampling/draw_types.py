"""The sample draw workflow's input (A-03-T10; A-03 §4.4): identifiers only (ADR-090)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SampleDrawInput:
    tenant_id: str
    version_id: str
    requested_by: str
