"""T-04-T53: the tax review workspace's p95 budgets under the busy-season profile (ADR-079;
T-04 §10).

The load run (`python -m abacus_tools.loadtest.run`, Q-03-T112's profile at the busy-season
multiplier) reports each measured p95 by name; `breaches` compares them with these budgets. Checked
on staging, where the pipeline's load job runs; locally the numbers are not representative.
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
    Budget(
        "review_tree",
        Decimal(300),
        "GET /v1/tax-returns/{id}/review-tree for a return of 41 documents (Feld 2025)",
    ),
    Budget("worksheet_fields", Decimal(250), "GET /v1/tax-returns/{id}/worksheets/{form}/fields"),
    Budget("approve", Decimal(500), "POST of a field or section approval to 200"),
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
