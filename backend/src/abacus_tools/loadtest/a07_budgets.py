"""A-07-T45: release and archive p95 budgets under the x25 load profile (ADR-079; A-07 §10).

The load run (`python -m abacus_tools.loadtest.run`, Q-03-T112's profile at x25) reports each
measured p95 by name; `breaches` compares them with these budgets. Checked on staging, where the
pipeline's load job runs; locally the numbers are not representative.
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
    Budget("report_release", Decimal(3000), "POST …/report/release to 202, then G8 recorded"),
    Budget("archive_lock_enqueue", Decimal(500), "POST …/archive/lock to the workflow started"),
    Budget("archive_seal_northwind", Decimal(120_000), "the Northwind seal activity end to end"),
    Budget("archived_guard_per_row", Decimal(2), "the guard trigger's overhead per written row"),
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
