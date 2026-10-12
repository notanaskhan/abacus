"""Mechanical checks on an upload (SPEC-029 goals 5 and 6; TASK-055; ADR-050, ADR-111). PROTECTED.

Pure code over what extraction read (TASK-054) and what the engagement and the ledger say. Each
check gives `passed`, `problem` or `not_applicable` (with why), an audience (`client` for
document problems a client can fix, `firm` for ledger cross-checks, Q3), and only values code
computed: dates, amounts, an account code, an item reference. Nothing is guessed: a value the
document doesn't print, or a cell without a saved result, makes a check `not_applicable`.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from abacus.modules.evidence.document_fields import parse_amount

CHECKER_VERSION: Final = "v1"
STALE_DAYS: Final = 45  # SPEC-029 Q6
STATEMENT_DAYS: Final = 31  # a statement with only its end date printed covers this many days

Outcome = Literal["passed", "problem", "not_applicable"]
Audience = Literal["client", "firm"]
_SUFFIXES: Final = frozenset(
    {"inc", "incorporated", "llc", "llp", "lp", "ltd", "limited", "corp", "corporation", "co"}
    | {"company", "pc", "pllc", "the", "and"}
)


@dataclass(frozen=True)
class CheckResult:
    code: str
    outcome: Outcome
    audience: Audience = "client"
    reason: str | None = None
    expected_date: date | None = None
    found_date: date | None = None
    amount: Decimal | None = None
    difference: Decimal | None = None
    account_code: str | None = None
    ref_item_id: UUID | None = None


@dataclass(frozen=True)
class ExtractedFields:
    """The extraction's columns (TASK-054) and, for agings and schedules, its JSON."""

    status: str
    reason: str | None
    period_start: date | None
    period_end: date | None
    as_of: date | None
    entity_name: str | None
    opening: Decimal | None
    closing: Decimal | None
    credits: Decimal | None
    debits: Decimal | None
    document: Mapping[str, object] | None = None


def normalised_name(name: str) -> str:
    """Case, punctuation and legal suffixes dropped: "Example Co., Inc." → "example"."""
    words = re.findall(r"[a-z0-9]+", name.casefold().replace("&", " and "))
    return " ".join(w for w in words if w not in _SUFFIXES)


def _na(code: str, reason: str, audience: Audience = "client") -> CheckResult:
    return CheckResult(code, "not_applicable", audience, reason)


def readable(fields: ExtractedFields) -> CheckResult:
    if fields.status == "unreadable":
        return CheckResult("unreadable", "problem", reason=fields.reason)
    if fields.status == "not_extracted":
        return _na("unreadable", fields.reason or "not_extracted")
    return CheckResult("unreadable", "passed")


def duplicate(other_item: UUID | None, found: bool) -> CheckResult:
    """The same file on another version of this engagement (AC-8)."""
    if not found:
        return CheckResult("duplicate", "passed")
    return CheckResult("duplicate", "problem", ref_item_id=other_item)


def statement_checks(fields: ExtractedFields, year_end: date, entity: str) -> list[CheckResult]:
    """`stale_as_of`, `wrong_period`, `wrong_entity`, `totals_dont_add_up` (AC-6)."""
    results: list[CheckResult] = []
    end = fields.period_end
    if end is None:
        results.append(_na("stale_as_of", "no_period"))
        results.append(_na("wrong_period", "no_period"))
    else:
        start = fields.period_start or end - timedelta(days=STATEMENT_DAYS - 1)
        stale = end < year_end - timedelta(days=STALE_DAYS)
        results.append(
            CheckResult(
                "stale_as_of",
                "problem" if stale else "passed",
                expected_date=year_end,
                found_date=end,
            )
        )
        if stale:
            results.append(_na("wrong_period", "stale"))
        else:
            covers = start <= year_end <= end
            results.append(
                CheckResult(
                    "wrong_period",
                    "passed" if covers else "problem",
                    expected_date=year_end,
                    found_date=end,
                )
            )
    if fields.entity_name is None or not entity:
        results.append(_na("wrong_entity", "no_name"))
    else:
        found, expected = normalised_name(fields.entity_name), normalised_name(entity)
        same = bool(found) and found == expected
        results.append(CheckResult("wrong_entity", "passed" if same else "problem"))
    values = (fields.opening, fields.credits, fields.debits, fields.closing)
    if any(v is None for v in values):
        results.append(_na("totals_dont_add_up", "not_printed"))
    else:
        opening, credits, debits, closing = (v or Decimal(0) for v in values)
        difference = closing - (opening + credits - debits)
        results.append(
            CheckResult(
                "totals_dont_add_up",
                "passed" if difference == 0 else "problem",
                amount=closing,
                difference=difference,
            )
        )
    return results


def _map(value: object) -> Mapping[str, object] | None:
    """A JSON object from the extraction document, or None."""
    return cast(Mapping[str, object], value) if isinstance(value, dict) else None


def _seq(value: object) -> list[object]:
    """A JSON array from the extraction document, or empty."""
    return cast(list[object], value) if isinstance(value, list) else []


def _amounts(values: object) -> list[Decimal | None]:
    return [parse_amount(v) for v in _seq(values)]


def aging_checks(fields: ExtractedFields, year_end: date) -> list[CheckResult]:
    """`wrong_period`, `totals_dont_add_up` (AC-7)."""
    results: list[CheckResult] = []
    if fields.as_of is None:
        results.append(_na("wrong_period", "no_as_of"))
    else:
        results.append(
            CheckResult(
                "wrong_period",
                "passed" if fields.as_of == year_end else "problem",
                expected_date=year_end,
                found_date=fields.as_of,
            )
        )
    aging = _map(fields.document.get("aging")) if fields.document is not None else None
    if aging is None:
        results.append(_na("totals_dont_add_up", "no_table"))
        return results
    grand = _amounts(aging.get("grand_total"))
    lines: list[tuple[list[Decimal | None], Decimal | None]] = []
    for row in _seq(aging.get("rows")):
        found = _map(row)
        if found is not None:
            lines.append((_amounts(found.get("buckets")), parse_amount(found.get("total"))))
    checked = False
    for buckets, total in lines:  # each row: its buckets make its total
        if total is None or any(b is None for b in buckets):
            continue
        checked = True
        difference = total - sum((b or Decimal(0) for b in buckets), Decimal(0))
        if difference != 0:
            return [
                *results,
                CheckResult("totals_dont_add_up", "problem", amount=total, difference=difference),
            ]
    if grand and grand[-1] is not None:  # the rows make the total row
        grand_total = grand[-1]
        totals = [t for _, t in lines]
        if lines and all(t is not None for t in totals):
            checked = True
            difference = grand_total - sum((t or Decimal(0) for t in totals), Decimal(0))
            if difference != 0:
                return [
                    *results,
                    CheckResult(
                        "totals_dont_add_up", "problem", amount=grand_total, difference=difference
                    ),
                ]
        for column, expected in enumerate(grand[:-1]):  # each bucket column
            values = [b[column] if column < len(b) else None for b, _ in lines]
            if expected is None or any(v is None for v in values):
                continue
            checked = True
            difference = expected - sum((v or Decimal(0) for v in values), Decimal(0))
            if difference != 0:
                return [
                    *results,
                    CheckResult(
                        "totals_dont_add_up", "problem", amount=expected, difference=difference
                    ),
                ]
    results.append(
        CheckResult("totals_dont_add_up", "passed")
        if checked
        else _na("totals_dont_add_up", "no_values")
    )
    return results


def schedule_checks(fields: ExtractedFields) -> list[CheckResult]:
    """`totals_dont_add_up`: a row labelled Total against the numbers above it (AC-7)."""
    tables = _seq(fields.document.get("tables")) if fields.document is not None else []
    checked = False
    for table in tables:
        found_table = _map(table)
        rows = _seq(found_table.get("rows")) if found_table is not None else []
        sums: dict[int, Decimal] = {}
        for row in rows:
            cells: Sequence[object] = _seq(row)
            label = str(cells[0]).strip().casefold() if cells else ""
            if label.startswith("total"):
                for column, cell in enumerate(cells[1:], start=1):
                    found = parse_amount(cell)
                    if found is None or column not in sums:
                        continue
                    checked = True
                    difference = found - sums[column]
                    if difference != 0:
                        return [
                            CheckResult(
                                "totals_dont_add_up",
                                "problem",
                                amount=found,
                                difference=difference,
                            )
                        ]
                sums = {}
                continue
            for column, cell in enumerate(cells[1:], start=1):
                found = parse_amount(cell)
                if found is not None:
                    sums[column] = sums.get(column, Decimal(0)) + found
    return [
        CheckResult("totals_dont_add_up", "passed")
        if checked
        else _na("totals_dont_add_up", "no_total_row")
    ]
