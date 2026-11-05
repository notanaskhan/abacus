"""Plan expenses and limits (A-05-T43; A-05 §4.4 `expenses`; EBP-09; DEC-2307): pure functions.

Expenses foot to Schedule H 2i (38,400 = 2i(1) 6,000 + 2i(2) 32,400), invoices less credits equal
paid from plan (41,500 - 3,100), and the ERISA budget account rolls (1,200 + 2,650 - 3,100 = 750).
Limits come from `reference/irs_plan_limits.yaml` **by plan year**, and a missing year is a refusal,
never a prior year's limit. Decimal only.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Final, cast

import yaml

ENGINE_NAME: Final = "ebp_expenses"
ENGINE_VERSION: Final = "1"
_LIMITS: Final = Path(__file__).parent / "reference" / "irs_plan_limits.yaml"
_ZERO: Final = Decimal(0)


class LimitsUnavailable(Exception):
    """No limits on file for this plan year; a prior year's are never substituted."""


@cache
def _limits_file() -> Mapping[str, Mapping[str, str]]:
    raw = yaml.safe_load(_LIMITS.read_text())
    return cast(Mapping[str, Mapping[str, str]], raw["limits"])


def limits_for(plan_year: int) -> Mapping[str, Decimal]:
    found = _limits_file().get(str(plan_year))
    if found is None:
        raise LimitsUnavailable(str(plan_year))
    return {key: Decimal(value) for key, value in found.items()}


@dataclass(frozen=True)
class Expense:
    line_key: str
    invoiced: Decimal
    credits: Decimal
    paid_from_plan: Decimal
    schedule_h_line: str
    has_disclosure: bool


@dataclass(frozen=True)
class ExpenseTie:
    invoiced: Decimal
    credits: Decimal
    paid: Decimal
    by_line: Mapping[str, Decimal]
    invoices_tie: bool
    exceptions: tuple[str, ...]  # line keys with no 408(b)(2) disclosure, or that do not foot
    inputs_hash: str
    engine_version: str = ENGINE_VERSION


def tie(expenses: Sequence[Expense]) -> ExpenseTie:
    invoiced = sum((e.invoiced for e in expenses), _ZERO)
    credits = sum((e.credits for e in expenses), _ZERO)
    paid = sum((e.paid_from_plan for e in expenses), _ZERO)
    by_line: dict[str, Decimal] = {}
    for expense in expenses:
        by_line[expense.schedule_h_line] = (
            by_line.get(expense.schedule_h_line, _ZERO) + expense.paid_from_plan
        )
    exceptions = tuple(
        e.line_key
        for e in expenses
        if not e.has_disclosure or e.invoiced - e.credits != e.paid_from_plan
    )
    body = sorted(
        f"{e.line_key}|{e.invoiced}|{e.credits}|{e.paid_from_plan}|{e.schedule_h_line}"
        f"|{e.has_disclosure}"
        for e in expenses
    )
    return ExpenseTie(
        invoiced,
        credits,
        paid,
        by_line,
        invoiced - credits == paid,
        exceptions,
        hashlib.sha256(json.dumps(body).encode()).hexdigest(),
    )


@dataclass(frozen=True)
class BudgetRoll:
    beginning: Decimal
    revenue_share: Decimal
    applied: Decimal
    ending: Decimal


def budget_account(lines: Sequence[tuple[str, Decimal]]) -> BudgetRoll:
    """`(kind, amount)` rows: `beginning`, `revenue_share` and `applied` (entered positive)."""
    beginning = sum((a for k, a in lines if k == "beginning"), _ZERO)
    revenue = sum((a for k, a in lines if k == "revenue_share"), _ZERO)
    applied = sum((a for k, a in lines if k == "applied"), _ZERO)
    return BudgetRoll(beginning, revenue, applied, beginning + revenue - applied)


def within_limit(amount: Decimal, limit_key: str, plan_year: int) -> bool:
    return amount <= limits_for(plan_year)[limit_key]
