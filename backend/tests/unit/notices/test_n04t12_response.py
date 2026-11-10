"""N-04-T12 (TASK-3260; DEC-2240): the notice response, part 1.

Row acceptance: "A draft renders with the watermark, an edit makes L2 stale, Regenerate keeps
the human paragraph, and the partner level answers 409 decision_pending before the decision."
Here: the content hash moves with any block edit (so a sign-off over the old hash is stale),
the sign-off refusals in order, and the registrations.
"""

from __future__ import annotations

from abacus.modules.notices import response
from abacus.modules.notices.response import Block

TEMPLATE = Block("block:1", "template", "block:1", "We agree with the proposed change.", False)
HUMAN = Block("block:2", "human", "block:2", "The 1099-INT from Lakeview was issued late.", True)


def _blocks(*texts: str) -> list[dict[str, str]]:
    return [{"key": f"block:{n}", "text": t} for n, t in enumerate(texts, 1)]


def test_an_edit_moves_the_content_hash_so_an_old_sign_off_goes_stale() -> None:
    before = response.content_hash(_blocks("We agree.", "Enclosed are the 1099-INTs."))
    after = response.content_hash(_blocks("We agree.", "Enclosed are both 1099-INTs."))
    assert before != after
    assert before == response.content_hash(_blocks("We agree.", "Enclosed are the 1099-INTs."))


def test_sign_off_is_refused_with_decision_pending_before_the_decision() -> None:
    assert response.blocked_code(None, None, [TEMPLATE]) == "decision_pending"


def test_a_draft_for_another_position_is_a_position_mismatch() -> None:
    assert response.blocked_code("disagree", "agree", [TEMPLATE, HUMAN]) == "position_mismatch"


def test_a_disagree_response_needs_a_human_explanation() -> None:
    assert response.blocked_code("disagree", "disagree", [TEMPLATE]) == "explanation_required"
    assert response.blocked_code("disagree", "disagree", [TEMPLATE, HUMAN]) is None
    assert response.blocked_code("agree", None, [TEMPLATE]) is None


def test_the_response_reviewable_and_gate_kinds_are_registered() -> None:
    import abacus.modules.notices.api  # noqa: F401  # pyright: ignore[reportUnusedImport]  (registers)
    from abacus.modules.review.slots import reviewable_types

    assert response.TARGET in reviewable_types()


def test_a_draft_from_before_the_decision_answers_no_position() -> None:
    assert response.drafted_for(None, "provisional") is None
    assert response.drafted_for("agree", "decided") == "agree"
    provisional = response.drafted_for("agree", "provisional")
    assert response.blocked_code("agree", provisional, [TEMPLATE]) == "position_mismatch"


def test_a_position_clause_is_on_for_its_position_only() -> None:
    assert response.clause_states_for(None) == {}
    assert response.clause_states_for("disagree") == {
        "agree": False,
        "partially_agree": False,
        "disagree": True,
    }
