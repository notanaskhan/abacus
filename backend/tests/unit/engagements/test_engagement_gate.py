"""SPEC-025 AC-7 (TASK-044): why an engagement isn't open to client data, in order."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from abacus.modules.engagements.acceptance_tables import G1Decision
from abacus.modules.engagements.models import EngagementLetter
from abacus.modules.engagements.setup import (
    _blocked,  # pyright: ignore[reportPrivateUsage] -- the gate's pure rule, tested directly
)

Opened = tuple[G1Decision, bool]  # CLI-07's decision, and whether CLI-08 concluded (DEC-906)


def _acceptance(decision: str = "accepted", concluded: bool = True) -> Opened:
    return G1Decision(decision == "accepted", datetime.now(UTC), None), concluded


def _letter(status: str) -> EngagementLetter:
    return cast(EngagementLetter, SimpleNamespace(status=status))


def _code(
    opened: Opened | None, letter: EngagementLetter | None, needs_letter: bool
) -> str | None:
    # An attest engagement: G1 to G3 all apply (F-03-T13 made the gates per type).
    decision, concluded = opened if opened is not None else (None, False)
    found = _blocked(
        decision,
        letter,
        gates=frozenset({"G1", "G2", "G3"}),
        needs_letter=needs_letter,
        g2=concluded,
    )
    return None if found is None else found.code


def test_ac7_closed_until_acceptance_then_the_conclusion() -> None:
    assert _code(None, None, False) == "acceptance_missing"
    assert _code(_acceptance("declined"), None, False) == "acceptance_declined"
    assert _code(_acceptance(concluded=False), None, False) == "independence_conclusion_missing"
    assert _code(_acceptance(), None, False) is None


def test_ac7_the_letter_blocks_only_when_the_firm_requires_it() -> None:
    assert _code(_acceptance(), None, True) == "letter_missing"
    assert _code(_acceptance(), _letter("sent"), True) == "letter_missing"
    assert _code(_acceptance(), _letter("signed"), True) is None
    assert _code(_acceptance(), _letter("not_required_this_year"), True) is None
