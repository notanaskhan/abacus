"""Likely-to-extend signals (T-03-T04; T-03 §3 F4; TAX-13 c) as a pure function.

A return not yet filed and within the parameter file's window of its original due date is
proposed as likely to extend for each signal it shows: a K-1 it is waiting for, an incomplete
binder, an engagement not yet accepted (Thornbury's 706, CLI-07), or the preparer's flag. Code
proposes; a person flags or clears the row (`filing_extension.flag_likely`). The date is an
input: nothing here reads a clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from abacus.modules.tax.compute.payments import Parameters

Signal = Literal["k1_outstanding", "binder_incomplete", "engagement_not_accepted", "preparer_flag"]
ORDER: tuple[Signal, ...] = (
    "k1_outstanding",
    "binder_incomplete",
    "engagement_not_accepted",
    "preparer_flag",
)


@dataclass(frozen=True)
class ReturnFacts:
    original_due_on: date
    filed: bool
    extension_filed: bool
    k1s_outstanding: int
    binder_open_items: int
    engagement_accepted: bool
    preparer_flagged: bool


def signals(facts: ReturnFacts, as_of: date, params: Parameters) -> tuple[Signal, ...]:
    """The signals in display order; empty for a filed or extended return or outside the
    window. A return past its original due date and still unfiled stays in the window."""
    if facts.filed or facts.extension_filed:
        return ()
    if (facts.original_due_on - as_of).days > params.likely_window_days:
        return ()
    found: set[Signal] = set()
    if facts.k1s_outstanding > 0:
        found.add("k1_outstanding")
    if facts.binder_open_items > 0:
        found.add("binder_incomplete")
    if not facts.engagement_accepted:
        found.add("engagement_not_accepted")
    if facts.preparer_flagged:
        found.add("preparer_flag")
    return tuple(s for s in ORDER if s in found)
