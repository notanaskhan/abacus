"""The runtime load test's verdict (P-10-T51; TASK-7428; DEC-4412): one run's report against the
row's targets, offline.

    python -m abacus_tools.loadtest.runtime_report --report <runtime_v2-*.json> \
        --api-log <api log, JSON lines> --peak-connections <n> --max-connections <n>

- **Stream first event** (`stream_first_byte`): the stream group's p95 in the runner's report.
- **Commit to delivery** (`sse_commit_to_event`): the nearest-rank p95 of `lag_ms` over the API's
  `realtime.delivered` lines in the run's window (the same samples the staging alarm reads as
  `SseDeliveryLagMs`). Other lines are ignored; a line that is not JSON is skipped.
- **Connections**: the run's peak against 70% of max_connections (RDS `DatabaseConnections`,
  Maximum, on the perf stack).

Prints each breach (`p10_budgets.runtime_report`) and the measured values as Markdown for the
load report; exit 0 when every target is met, 1 otherwise, 2 when an input is unreadable.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

from abacus_tools.loadtest import p10_budgets
from abacus_tools.loadtest.stats import percentile

DELIVERED: Final = "realtime.delivered"
STREAM_GROUP: Final = "stream_first_byte"


@dataclass(frozen=True)
class Measured:
    p95_ms: dict[str, Decimal]
    delivered_reads: int
    peak_connections: int
    max_connections: int


def delivery_lags(lines: Iterable[str]) -> list[float]:
    """`lag_ms` of every `realtime.delivered` line (JSON lines; anything else skipped)."""
    lags: list[float] = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        found = cast(dict[str, object], row)
        lag = found.get("lag_ms")
        if found.get("event") == DELIVERED and isinstance(lag, int | float):
            lags.append(float(lag))
    return lags


def stream_p95(report: Mapping[str, object]) -> Decimal | None:
    groups = cast(list[dict[str, object]], report.get("groups") or [])
    for group in groups:
        if group.get("name") == STREAM_GROUP and group.get("p95_ms") is not None:
            return Decimal(str(group["p95_ms"]))
    return None


def measure(
    report: Mapping[str, object],
    log_lines: Iterable[str],
    *,
    peak_connections: int,
    max_connections: int,
) -> Measured:
    found: dict[str, Decimal] = {}
    first = stream_p95(report)
    if first is not None:
        found[STREAM_GROUP] = first
    lags = delivery_lags(log_lines)
    lag = percentile(lags, 95)
    if lag is not None:
        found["sse_commit_to_event"] = Decimal(str(lag))
    return Measured(found, len(lags), peak_connections, max_connections)


def verdict(measured: Measured) -> list[str]:
    return p10_budgets.runtime_report(
        measured.p95_ms, measured.peak_connections, measured.max_connections
    )


def markdown(measured: Measured, breaches: list[str]) -> str:
    rows = [
        "| Target | Budget | Measured |",
        "|---|---|---|",
    ]
    for budget in p10_budgets.BUDGETS:
        if budget.name not in p10_budgets.RUNTIME_BUDGETS:
            continue
        seen = measured.p95_ms.get(budget.name)
        rows.append(
            f"| {budget.name} p95 | {budget.p95_ms} ms | "
            f"{'not measured' if seen is None else f'{seen} ms'} |"
        )
    share = (
        Decimal(measured.peak_connections) / Decimal(measured.max_connections) * 100
        if measured.max_connections > 0
        else None
    )
    rows.append(
        f"| database connections | under 70% | {measured.peak_connections} of "
        f"{measured.max_connections}" + (f" ({share:.0f}%)" if share is not None else "") + " |"
    )
    head = "Met every target." if not breaches else "Missed: " + "; ".join(breaches) + "."
    return f"{head}\n\n" + "\n".join(rows) + f"\n\n{measured.delivered_reads} delivered reads.\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The runtime load test's verdict.")
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--api-log", required=True, type=Path)
    parser.add_argument("--peak-connections", required=True, type=int)
    parser.add_argument("--max-connections", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        report = cast(dict[str, object], json.loads(args.report.read_text(encoding="utf-8")))
        lines = args.api_log.read_text(encoding="utf-8").splitlines()
    except (OSError, ValueError) as exc:
        print(f"unreadable input: {type(exc).__name__}", file=sys.stderr)
        return 2
    measured = measure(
        report,
        lines,
        peak_connections=args.peak_connections,
        max_connections=args.max_connections,
    )
    breaches = verdict(measured)
    sys.stdout.write(markdown(measured, breaches))
    return 1 if breaches else 0


if __name__ == "__main__":
    sys.exit(main())
