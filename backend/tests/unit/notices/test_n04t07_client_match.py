"""N-04-T07 (N-04 US-2.3; DEC-2326): code's client match. A name narrows and never widens."""

from __future__ import annotations

from uuid import UUID, uuid4

from abacus.modules.notices.intake_read import ClientMatch, match_client

SANTOS, STEIN = UUID(int=1), UUID(int=2)


def test_one_entity_with_the_last_four_is_matched_by_tin() -> None:
    assert match_client("2208", None, {SANTOS: "Maria Santos"}) == ClientMatch(SANTOS, "tin", ())


def test_a_matching_name_settles_between_two_entities() -> None:
    both = {SANTOS: "Maria Santos", STEIN: "Ada Stein"}
    assert match_client("2208", " maria santos ", both) == ClientMatch(SANTOS, "name_tin", ())


def test_two_entities_and_no_name_are_the_persons_pick() -> None:
    both = {SANTOS: "Maria Santos", STEIN: "Ada Stein"}
    assert match_client("2208", None, both) == ClientMatch(None, None, (SANTOS, STEIN))


def test_a_name_on_no_candidate_does_not_guess_between_them() -> None:
    both = {SANTOS: "Maria Santos", STEIN: "Ada Stein"}
    assert match_client("2208", "Someone Else", both).client_entity_id is None


def test_no_last_four_or_no_entity_is_the_client_picker() -> None:
    assert match_client(None, "Maria Santos", {uuid4(): "x"}) == ClientMatch(None, None, ())
    assert match_client("2208", "Maria Santos", {}) == ClientMatch(None, None, ())
