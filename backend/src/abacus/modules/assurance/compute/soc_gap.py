"""The SOC 1 period gap by code (A-04-T31; A-04 AC7.1; DEC-2236; ADR-050).

A SOC 1 Type 2 report covers a period; the audit needs the plan year. The gap is the plan-year
days the report's period does not cover, before its start and after its end, counted inclusively.
Keystone's report covers Oct 1, 2024 to Sep 30, 2025 against the 2025 plan year, so the gap is
Oct 1 to Dec 31, 2025: 92 days. A received bridge letter marks the gap bridged; it never shrinks
the count. Pure: no I/O, no clock; every result carries its engine stamp.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

ENGINE_NAME: Final = "soc_gap"
ENGINE_VERSION: Final = "1"


@dataclass(frozen=True)
class Stamp:
    engine_name: str
    engine_version: str
    inputs_hash: str


@dataclass(frozen=True)
class Gap:
    start: date | None  # the first uncovered day, or None when the period covers the year
    end: date | None
    days: int
    bridged: bool
    stamp: Stamp


def _stamp(**parts: object) -> Stamp:
    body = json.dumps(
        {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            **{k: str(v) for k, v in parts.items()},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return Stamp(ENGINE_NAME, ENGINE_VERSION, hashlib.sha256(body.encode("utf-8")).hexdigest())


def gap(
    *,
    plan_year_start: date,
    plan_year_end: date,
    period_start: date,
    period_end: date,
    bridge_received: bool,
) -> Gap:
    """Uncovered plan-year days. When both ends are uncovered the reported range runs from the
    first uncovered day to the last; `days` counts only the uncovered days."""
    if plan_year_end < plan_year_start or period_end < period_start:
        raise ValueError("a period ends before it starts")
    before = (
        (min(period_start, plan_year_end + timedelta(days=1)) - plan_year_start).days
        if period_start > plan_year_start
        else 0
    )
    after = (
        (plan_year_end - max(period_end, plan_year_start - timedelta(days=1))).days
        if period_end < plan_year_end
        else 0
    )
    days = max(before, 0) + max(after, 0)
    days = min(days, (plan_year_end - plan_year_start).days + 1)
    start = (
        plan_year_start if before > 0 else (period_end + timedelta(days=1) if after > 0 else None)
    )
    end = (
        plan_year_end if after > 0 else (period_start - timedelta(days=1) if before > 0 else None)
    )
    stamp = _stamp(
        plan_year_start=plan_year_start,
        plan_year_end=plan_year_end,
        period_start=period_start,
        period_end=period_end,
        bridge_received=bridge_received,
    )
    return Gap(start, end, days, bridge_received and days > 0, stamp)
