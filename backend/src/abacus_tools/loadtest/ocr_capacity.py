"""The December x100 OCR capacity plan (P-11-T33; P-11 §cost, R9; ADR-075; RB-68).

Run: python -m abacus_tools.loadtest.ocr_capacity --firms N [--baseline-pages 50] [...]

Code computes what the December drive must reach and whether the Textract quotas and the daily
caps carry it: pages per minute at the peak hour, DetectDocumentText and AnalyzeDocument (FORMS)
TPS, quota headroom, which firms the cap refuses, and the worst-case time to read a 20-page upload
(the worker reads an upload's pages one after another: P-11-T25's `_read`). The perf-stack run
(`loadtest/scenarios/ocr_december.yaml` beside the page drive) measures; this says what the
measurement has to show. Every default marked "inferred" is a planning assumption written down in
RB-68, not a measured figure: replace it with the staging soak's numbers.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal

P95_TARGET_SECONDS = 180  # P-11 exit: "OCR p95 <= 3 min for <= 20 pages"
TARGET_PAGES = 20


@dataclass(frozen=True)
class Inputs:
    firms: int
    baseline_pages_per_firm_day: int = 50  # inferred: the PF-X1 rehearsal day
    multiplier: int = 100  # P-11 exit: December x100
    peak_hour_share: Decimal = Decimal("0.20")  # inferred: a fifth of the day in its busiest hour
    forms_share: Decimal = Decimal("0.30")  # inferred: pages naming a TIN go on to FORMS
    cache_hit_share: Decimal = Decimal("0")  # the page-hash cache; 0 is the cautious case
    detect_tps_quota: Decimal = Decimal("10")  # inferred: confirm in Service Quotas (us-east-2)
    analyze_tps_quota: Decimal = Decimal("10")  # inferred: confirm in Service Quotas
    headroom: Decimal = Decimal("0.80")  # alarm at 80% of quota, as at 80% of the cap
    daily_cap: int = 5000  # OQ-10 default; a firm's own row may differ (0714)
    detect_p95_seconds: Decimal = Decimal("2.0")  # inferred per-page call p95
    analyze_p95_seconds: Decimal = Decimal("4.0")  # inferred per-page FORMS call p95
    rasterise_seconds_per_page: Decimal = Decimal("0.5")  # inferred isolated-child rasterise


@dataclass(frozen=True)
class Plan:
    pages_per_firm_day: int
    capped_pages_per_firm_day: int
    refused_pages_per_firm_day: int
    pages_per_minute: Decimal
    detect_tps: Decimal
    analyze_tps: Decimal
    detect_headroom_tps: Decimal
    analyze_headroom_tps: Decimal
    twenty_page_seconds: Decimal
    failures: tuple[str, ...] = field(default=())


def _up(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_CEILING)


def plan(given: Inputs) -> Plan:
    if given.firms < 1:
        raise ValueError("firms must be at least 1")
    per_firm = given.baseline_pages_per_firm_day * given.multiplier
    capped = min(per_firm, given.daily_cap)
    read_share = Decimal(1) - given.cache_hit_share
    peak_pages_hour = Decimal(capped * given.firms) * given.peak_hour_share * read_share
    per_minute = peak_pages_hour / 60
    detect_tps = per_minute / 60
    analyze_tps = detect_tps * given.forms_share
    detect_room = given.detect_tps_quota * given.headroom
    analyze_room = given.analyze_tps_quota * given.headroom
    # One upload's pages are read in order; a page waits for its own calls only, and under the
    # quota the gateway's retries add the backoff the throttled share would cost (none when
    # within headroom).
    per_page = (
        given.rasterise_seconds_per_page
        + given.detect_p95_seconds
        + given.forms_share * given.analyze_p95_seconds
    )
    twenty = per_page * TARGET_PAGES
    failures: list[str] = []
    if detect_tps > detect_room:
        failures.append(
            f"DetectDocumentText needs {_up(detect_tps)} TPS; 80% of quota is {detect_room}"
        )
    if analyze_tps > analyze_room:
        failures.append(
            f"AnalyzeDocument FORMS needs {_up(analyze_tps)} TPS; 80% of quota is {analyze_room}"
        )
    if twenty > P95_TARGET_SECONDS:
        failures.append(f"a 20-page upload takes {_up(twenty)} s; the target is 180 s")
    return Plan(
        pages_per_firm_day=per_firm,
        capped_pages_per_firm_day=capped,
        refused_pages_per_firm_day=per_firm - capped,
        pages_per_minute=_up(per_minute),
        detect_tps=_up(detect_tps),
        analyze_tps=_up(analyze_tps),
        detect_headroom_tps=detect_room,
        analyze_headroom_tps=analyze_room,
        twenty_page_seconds=_up(twenty),
        failures=tuple(failures),
    )


def firms_within_quota(given: Inputs) -> int:
    """The most firms the DetectDocumentText headroom carries at the peak hour (each at its cap
    or its x100 day, whichever is smaller)."""
    per_firm = min(given.baseline_pages_per_firm_day * given.multiplier, given.daily_cap)
    tps = Decimal(per_firm) * given.peak_hour_share * (Decimal(1) - given.cache_hit_share) / 3600
    return math.floor(given.detect_tps_quota * given.headroom / tps) if tps else 0


def render(given: Inputs, result: Plan) -> str:
    lines = [
        f"firms {given.firms}, x{given.multiplier} of {given.baseline_pages_per_firm_day} "
        f"pages a day = {result.pages_per_firm_day:,} pages per firm a day",
        f"cap {given.daily_cap:,}: {result.capped_pages_per_firm_day:,} read, "
        f"{result.refused_pages_per_firm_day:,} refused (quota_exceeded) per firm a day",
        f"peak hour: {result.pages_per_minute} pages a minute",
        f"DetectDocumentText {result.detect_tps} TPS (80% of quota: {result.detect_headroom_tps})",
        f"AnalyzeDocument FORMS {result.analyze_tps} TPS "
        f"(80% of quota: {result.analyze_headroom_tps})",
        f"a 20-page upload: {result.twenty_page_seconds} s at p95 (target 180 s)",
        f"firms the DetectDocumentText headroom carries: {firms_within_quota(given)}",
    ]
    lines += [f"FAIL: {f}" for f in result.failures] or ["PASS"]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.loadtest.ocr_capacity")
    parser.add_argument("--firms", type=int, required=True)
    parser.add_argument("--baseline-pages", type=int, default=Inputs.baseline_pages_per_firm_day)
    parser.add_argument("--multiplier", type=int, default=Inputs.multiplier)
    parser.add_argument("--cap", type=int, default=Inputs.daily_cap)
    parser.add_argument("--detect-tps-quota", type=Decimal, default=Inputs.detect_tps_quota)
    parser.add_argument("--analyze-tps-quota", type=Decimal, default=Inputs.analyze_tps_quota)
    parser.add_argument("--cache-hit-share", type=Decimal, default=Inputs.cache_hit_share)
    args = parser.parse_args(argv)
    given = Inputs(
        firms=args.firms,
        baseline_pages_per_firm_day=args.baseline_pages,
        multiplier=args.multiplier,
        daily_cap=args.cap,
        detect_tps_quota=args.detect_tps_quota,
        analyze_tps_quota=args.analyze_tps_quota,
        cache_hit_share=args.cache_hit_share,
    )
    result = plan(given)
    print(render(given, result))
    return 1 if result.failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
