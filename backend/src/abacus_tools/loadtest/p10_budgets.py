"""P-10-T52: runtime v2 and SSE p95 budgets under the x25 load profile (ADR-079; P-10 §10).

The load run (`python -m abacus_tools.loadtest.run`, Q-03-T112's profile at x25) reports each
measured p95 by name; `breaches` compares them with these budgets. Checked on staging, where the
pipeline's load job runs; locally the numbers are not representative. P-10-T51 adds the commit to
SSE delivery target (p95 <= 2 s under 1,500 streams) beside these.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final


@dataclass(frozen=True)
class Budget:
    name: str
    p95_ms: Decimal
    note: str


BUDGETS: Final[tuple[Budget, ...]] = (
    Budget("plan_approve", Decimal(400), "POST /v1/agent-runs/{id}/plan/approve to 200"),
    Budget("stream_first_byte", Decimal(500), "GET /v1/events to the first byte (the hello)"),
)


def breaches(measured_p95_ms: Mapping[str, Decimal]) -> list[str]:
    """Each budget a run exceeded or did not measure, worded for the load report."""
    found: list[str] = []
    for budget in BUDGETS:
        seen = measured_p95_ms.get(budget.name)
        if seen is None:
            found.append(f"{budget.name}: not measured")
        elif seen > budget.p95_ms:
            found.append(f"{budget.name}: p95 {seen} ms > {budget.p95_ms} ms")
    return found
