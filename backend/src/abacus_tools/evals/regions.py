"""`citation_region_resolved`, a report-only metric in the screening, upload_review and matching
suites (P-03-T17; P-03 §6; TASK-1256, DEC-371): the share of a run's verified `document_text`
citations that carry a region (a bbox resolved from the word layer). Reported, never gating: P-03
proposes a threshold of 0.95 only after two nightly runs hold it (S12)."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Final

from abacus_tools.stack import connect_db

METRIC: Final = "citation_region_resolved"


async def region_counts(superuser: str, run_id: uuid.UUID) -> tuple[int, int]:
    """(verified document_text citations the run wrote, those with a bbox)."""
    conn = await connect_db(superuser)
    try:
        row = await conn.fetchrow(
            "SELECT count(*) AS cited, "
            "count(*) FILTER (WHERE jsonb_typeof(locator -> 'bbox') = 'array') AS resolved "
            "FROM citations WHERE created_by_run_id = $1 AND kind = 'document_text' AND verified",
            run_id,
        )
    finally:
        await conn.close()
    return (int(row["cited"]), int(row["resolved"])) if row is not None else (0, 0)


def resolved_share(counts: Iterable[tuple[int, int]]) -> float:
    """Resolved over cited across attempts; 1.0 when nothing was cited (no region is missing)."""
    pairs = list(counts)
    cited = sum(c for c, _ in pairs)
    return sum(r for _, r in pairs) / cited if cited else 1.0


def check_reports(
    reports: Iterable[str], metrics: Iterable[str], thresholded: Iterable[str]
) -> list[str]:
    """A suite's report-only metrics: each known, none also a threshold (it would gate)."""
    known, gated = set(metrics), set(thresholded)
    problems: list[str] = []
    for name in reports:
        if name not in known:
            problems.append(f"unknown report metric {name!r}")
        if name in gated:
            problems.append(f"report metric {name!r} also has a threshold")
    return problems


__all__ = ["METRIC", "check_reports", "region_counts", "resolved_share"]
