"""SPEC-025 AC-7 (TASK-044): why an engagement isn't open to client data, in order."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from abacus.modules.engagements.models import EngagementAcceptance, EngagementLetter
from abacus.modules.engagements.setup import (
    _blocked,  # pyright: ignore[reportPrivateUsage] -- the gate's pure rule, tested directly
)


def _acceptance(decision: str = "accepted", concluded: bool = True) -> EngagementAcceptance:
    return cast(
        EngagementAcceptance,
        SimpleNamespace(
            decision=decision, independence_concluded_at=datetime.now(UTC) if concluded else None
        ),
    )


def _letter(status: str) -> EngagementLetter:
    return cast(EngagementLetter, SimpleNamespace(status=status))


def _code(
    acceptance: EngagementAcceptance | None, letter: EngagementLetter | None, needs_letter: bool
) -> str | None:
    found = _blocked(acceptance, letter, needs_letter)
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
