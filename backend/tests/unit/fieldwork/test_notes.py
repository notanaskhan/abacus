"""SPEC-041 (TASK-103): a note's state from its events, and who may raise, respond and clear."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from abacus.modules.fieldwork.models import ReviewNoteEvent
from abacus.modules.fieldwork.notes import state_of
from abacus.modules.identity.authz.matrix import RULES

FIRM = ("engagement_partner", "manager", "senior", "staff", "reviewer")


def _events(*kinds: str) -> list[ReviewNoteEvent]:
    return [cast(ReviewNoteEvent, SimpleNamespace(kind=k)) for k in kinds]


def _allowed(action: str) -> set[str]:
    return {r for r in FIRM if RULES[action].decisions.get(r) == "allow"}


def test_ac6_a_note_with_no_events_is_open() -> None:
    assert state_of([]) == "open"


def test_ac2_a_response_makes_it_responded_and_a_reply_reopens_it() -> None:
    assert state_of(_events("responded")) == "responded"
    assert state_of(_events("responded", "reopened")) == "open"


def test_ac3_cleared_is_final_state() -> None:
    assert state_of(_events("responded", "cleared")) == "cleared"


def test_ac1_reviewers_raise_including_the_eqr_never_staff_or_the_agent() -> None:
    assert _allowed("review_note.raise") == {"engagement_partner", "manager", "senior", "reviewer"}
    assert RULES["review_note.raise"].decisions.get("agent") == "deny"


def test_ac2_preparers_respond() -> None:
    assert "staff" in _allowed("review_note.respond")
    assert RULES["review_note.respond"].decisions.get("agent") == "deny"


def test_ac3_clearing_is_for_reviewers_and_never_the_agent() -> None:
    assert "staff" not in _allowed("review_note.clear")
    assert RULES["review_note.clear"].decisions.get("agent") == "deny"
