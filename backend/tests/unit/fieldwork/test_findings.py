"""SPEC-043 (TASK-107): the summary of uncorrected misstatements, by code (ADR-050)."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import cast

from abacus.modules.fieldwork.findings import summarise
from abacus.modules.fieldwork.models import Misstatement
from abacus.modules.identity.authz.matrix import RULES

D = Decimal


def _m(kind: str, amount: str, corrected: bool = False) -> Misstatement:
    return cast(Misstatement, SimpleNamespace(kind=kind, amount=D(amount), corrected=corrected))


def test_ac3_totals_uncorrected_above_trivial_by_kind() -> None:
    by_kind, total, position = summarise(
        [
            _m("factual", "12000"),
            _m("factual", "-3000"),
            _m("judgmental", "40000"),
            _m("projected", "4000"),  # at or below clearly trivial: left out
            _m("factual", "90000", corrected=True),  # corrected: left out
        ],
        overall=D("150000"),
        performance=D("100000"),
        trivial=D("5000"),
    )
    totals = {k.kind: (k.count, k.total) for k in by_kind}
    assert totals == {
        "factual": (1, D("12000")),
        "judgmental": (1, D("40000")),
        "projected": (0, D("0")),
    }
    assert total == D("52000")
    assert position == "below_performance"


def test_ac3_position_against_materiality() -> None:
    _, _, at_performance = summarise(
        [_m("factual", "-100000")], D("150000"), D("100000"), D("5000")
    )
    _, _, at_overall = summarise([_m("factual", "160000")], D("150000"), D("100000"), D("5000"))
    _, _, unknown = summarise([_m("factual", "1")], None, None, None)
    assert at_performance == "at_or_above_performance"
    assert at_overall == "at_or_above_overall"
    assert unknown == "unknown"


def test_ac4_people_raise_and_record_never_the_agent() -> None:
    assert RULES["finding.raise"].decisions.get("staff") == "allow"
    assert RULES["misstatement.set"].decisions.get("staff") in (None, "deny")
    assert RULES["finding.raise"].decisions.get("agent") == "deny"
    assert RULES["misstatement.set"].decisions.get("agent") == "deny"
