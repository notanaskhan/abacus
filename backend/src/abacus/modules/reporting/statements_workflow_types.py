"""The statements workflows' inputs (A-06 §4.5): identifiers only; no figure reaches history."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FsDraftInput:
    tenant_id: str
    run_id: str
    engagement_id: str
    work_item_id: str


@dataclass(frozen=True)
class TieOutInput:
    tenant_id: str
    statement_version_id: str
