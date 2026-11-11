"""Capability names for the platform's agent-minute reads (P-10-T42; DEC-3401; ADM-14, ENG-06).

The platform module reads no agents table (ADR-008); it asks this labeller. Names are the
handoff's where a screen names the capability (ENG-06: "Document classifier & matcher", "PBC list
builder", "Plan provisions extraction"); a capability no screen names reads as its code. Two of
ENG-06's are history-only codes in the seed (runs #4019 and #4102 completed before the scenario's
recorded runs; no spec defines them yet). `history` is the seed's per-service-line usage-to-date
line for months whose runs are not recorded one by one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

from abacus.kernel.db import TenantContext

CAPABILITY_LABELS: Final[Mapping[str, str]] = {
    "evidence.matcher": "Document classifier & matcher",
    "requests.pbc_list_builder": "PBC list builder",
    "ebp.provisions_extractor": "Plan provisions extraction",
    "audit.engagement_run": "Engagement run",
    "tax.return_drafter": "Return drafter",
    "history": "Earlier runs",
}


async def capability_labels(tenant: TenantContext, keys: Sequence[str]) -> Mapping[str, str]:
    del tenant  # names are the product's, not the firm's
    return {key: CAPABILITY_LABELS[key] for key in keys if key in CAPABILITY_LABELS}
