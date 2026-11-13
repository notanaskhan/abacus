"""R-02-T13 (TASK-7809; DEC-3013, DEC-4807): `make seed-demo` writes the portal's attest entries
from the same figures book the portal fixtures read, so seed and fixture mode show the same data.

The fixture side is `apps/web/src/fixtures/seed/portal-r02.foot.test.ts` against the same book;
the governance room is pinned in `test_r02t13_governance_room_slice.py`.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from abacus_tools.synthetic.scenarios.brightwater_hale.completion_slice import ENTRIES

BOOK = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "golden"
        / "scenario"
        / "brightwater_hale"
        / "portal_figures.json"
    ).read_text()
)
ATTEST = BOOK["attest_entries"]
BY_FINDING = {e.finding: e for e in ENTRIES}


def _amount(value: str | None) -> Decimal:
    return Decimal(value) if value not in (None, "0") else Decimal(0)


def test_ac_the_four_attest_entries_are_the_books() -> None:
    kinds = [e.kind for e in ENTRIES]
    assert kinds == ["aje", "rje", "paje", "paje"]
    assert len(ATTEST["names"]) == len(ENTRIES)


def test_ac_aje_1_posts_the_books_accounts_and_amounts() -> None:
    seeded = [(a, _amount(d), _amount(c)) for a, d, c in BY_FINDING["F-05"].lines]
    book = [
        (x["account"], _amount(x["debit"]), _amount(x["credit"])) for x in ATTEST["aje_1_lines"]
    ]
    assert seeded == book
    assert sum(c for _, _, c in seeded) == Decimal(ATTEST["receivable"]["total"])


def test_ac_paje_2_is_the_books_accrued_group_line_by_line() -> None:
    entry = BY_FINDING["F-08"]
    assert entry.description == ATTEST["paje_2_title"]
    debits = [d for _, d, _ in entry.lines if _amount(d)]
    assert debits == ATTEST["accrued"]["lines"]
    assert sum(_amount(c) for _, _, c in entry.lines) == Decimal(ATTEST["accrued"]["total"])


def test_ac_the_uncorrected_net_is_the_books() -> None:
    increase = sum(_amount(d) for _, d, _ in BY_FINDING["F-07"].lines)
    decrease = sum(_amount(c) for _, _, c in BY_FINDING["F-08"].lines)
    figures = BOOK["uncorrected_misstatements"]
    assert (increase, decrease) == (
        Decimal(figures["would_increase"]),
        Decimal(figures["would_decrease"]),
    )
    assert increase - decrease == Decimal(figures["net_effect"])
