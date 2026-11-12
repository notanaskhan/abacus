"""P-10-T52: runtime v2 and SSE p95 budgets under the x25 load profile (ADR-079; P-10 §10).

The load run (`python -m abacus_tools.loadtest.run`, Q-03-T112's profile at x25) reports each
measured p95 by name; `breaches` compares them with these budgets. Checked on staging, where the
pipeline's load job runs; locally the numbers are not representative.

P-10-T51 (DEC-4412) adds the runtime load test's own targets (`scenarios/runtime_v2.yaml`: 1,500
streams and 50 parallel engagement runs): commit to SSE delivery p95 at or under 2 s, read from the
API's `realtime.delivered` lines (`SseDeliveryLagMs` on staging), and database connections under
70% of max_connections at the run's peak (`AWS/RDS DatabaseConnections`, Maximum).
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
    Budget("sse_commit_to_event", Decimal(2000), "realtime_events commit to the stream read"),
)
RUNTIME_STREAMS: Final = 1500
RUNTIME_ENGAGEMENT_RUNS: Final = 50
DB_CONNECTIONS_CEILING: Final = Decimal("0.70")
# The runtime scenario measures these; plan approve is T52's run (a plan approves once).
RUNTIME_BUDGETS: Final = frozenset({"stream_first_byte", "sse_commit_to_event"})


def breaches(
    measured_p95_ms: Mapping[str, Decimal], names: frozenset[str] | None = None
) -> list[str]:
    """Each budget (of `names`, or all) a run exceeded or did not measure, for the load report."""
    found: list[str] = []
    for budget in BUDGETS:
        if names is not None and budget.name not in names:
            continue
        seen = measured_p95_ms.get(budget.name)
        if seen is None:
            found.append(f"{budget.name}: not measured")
        elif seen > budget.p95_ms:
            found.append(f"{budget.name}: p95 {seen} ms > {budget.p95_ms} ms")
    return found


def connection_breach(peak_connections: int, max_connections: int) -> str | None:
    """The database ceiling: the run's peak at or above 70% of max_connections is a breach."""
    if max_connections <= 0:
        return "db_connections: max_connections unknown"
    share = Decimal(peak_connections) / Decimal(max_connections)
    if share >= DB_CONNECTIONS_CEILING:
        return f"db_connections: peak {peak_connections} of {max_connections} >= 70%"
    return None


def runtime_report(
    measured_p95_ms: Mapping[str, Decimal], peak_connections: int, max_connections: int
) -> list[str]:
    """Every P-10-T51 breach: the p95 budgets and the connection ceiling. Empty means it met."""
    found = breaches(measured_p95_ms, RUNTIME_BUDGETS)
    ceiling = connection_breach(peak_connections, max_connections)
    return [*found, ceiling] if ceiling else found
