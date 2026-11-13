"""The facts and options code computes for the recommender's tax modes (T-05-T49; T-05 F10;
ADR-050; DEC-4709). Pure; the caller reads the return (T-05-T52 raises the cards and the question).

- `convention_706d`: the three Reg. §1.706-4(c) conventions, each with the day the transfer
  closes the books under it; facts: the transfer date and the capital moved (E7's figure, given).
- `section_754`: elect and do not elect; facts: the transfer date, the price paid, the capital
  moved and the §743(b) placeholder = price - capital moved (Ridgeline: 360,000 - 331,405 =
  28,595), computed here by code.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Final

from abacus.modules.agents.api import (
    RecommendModeClause,
    RecommendModeFact,
    RecommendModeFacts,
    RecommendModeOption,
)
from abacus.modules.tax.compute.entity.allocation import boundary

_TITLES: Final = {
    "calendar_day": "Calendar day",
    "semi_monthly": "Semi-monthly",
    "monthly": "Monthly",
}


def _day(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year}"


def _money(amount: Decimal) -> str:
    return f"{amount:,.0f}"


def convention_facts(
    transfer: date,
    capital_moved: Decimal,
    clauses: Sequence[tuple[str, str, str]] = (),
) -> RecommendModeFacts:
    """Options from code with the day each closes the books; clauses are (ref, label, text)."""
    options = tuple(
        RecommendModeOption(key, f"{title} (books close {_day(boundary(transfer, key))})")  # type: ignore[arg-type] -- the run's context reads as its initiator
        for key, title in _TITLES.items()
    )
    return RecommendModeFacts(
        mode="convention_706d",
        options=options,
        facts=(
            RecommendModeFact("fact:transfer_date", "Transfer", _day(transfer)),
            RecommendModeFact("fact:capital_moved", "Capital moved", _money(capital_moved)),
        ),
        clauses=tuple(RecommendModeClause(r, label, t) for r, label, t in clauses),
    )


def section_754_facts(
    transfer: date,
    price: Decimal,
    capital_moved: Decimal,
    clauses: Sequence[tuple[str, str, str]] = (),
) -> RecommendModeFacts:
    placeholder = price - capital_moved
    return RecommendModeFacts(
        mode="section_754",
        options=(
            RecommendModeOption("elect", "Elect under §754"),
            RecommendModeOption("do_not_elect", "Do not elect"),
        ),
        facts=(
            RecommendModeFact("fact:transfer_date", "Transfer", _day(transfer)),
            RecommendModeFact("fact:price", "Price paid", _money(price)),
            RecommendModeFact("fact:capital_moved", "Capital moved", _money(capital_moved)),
            RecommendModeFact("fact:placeholder_743b", "§743(b) placeholder", _money(placeholder)),
        ),
        clauses=tuple(RecommendModeClause(r, label, t) for r, label, t in clauses),
    )


__all__ = ["convention_facts", "section_754_facts"]
