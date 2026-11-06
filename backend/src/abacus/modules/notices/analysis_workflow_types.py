"""`NoticeAnalysisWorkflow`'s input (N-04-T11): identifiers only; no value reaches its history."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NoticeAnalysisInput:
    tenant_id: str
    notice_id: str
    version: int
