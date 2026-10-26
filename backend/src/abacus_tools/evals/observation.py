"""What one attempt of one case produced (the runner observes, graders and metrics judge)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

ObservedStage = Literal["screened", "failed_validation", "failed", "errored"]


@dataclass(frozen=True)
class Observation:
    case_id: str
    attempt: int
    stage: ObservedStage
    # The proposal after the code's confidence routing, and what the model itself answered.
    action: str | None = None
    model_action: str | None = None
    confidence: float | None = None
    citations_verified: bool | None = None
    contained: bool | None = None
    cost_usd: Decimal = Decimal(0)
    budget_usd: Decimal = Decimal(0)
    error: str | None = None
    latency_ms: int | None = None  # SPEC-026: the screening call, for the milestone report
    # P-03-T17 (report-only `citation_region_resolved`): verified document_text citations the run
    # wrote, and how many of them carry a region.
    regions_cited: int = 0
    regions_resolved: int = 0
