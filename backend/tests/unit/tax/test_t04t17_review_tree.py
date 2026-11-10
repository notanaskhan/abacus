"""T-04-T17 (TASK-6616; SPEC-649; DEC-37): a viewer's approval level comes from their functions on
the return. Row acceptance: "Samuel's tree shows Review 37 for 41 documents and 36 after one
approval, Kevin cannot approve at manager level, and a final-approval request with a Draft K-1
answers 409 with blocker draft_k1." The database half is the end pass's integration suite."""

from __future__ import annotations

from abacus.modules.tax.review_tree import LEVELS, levels_held, viewer_level


def test_functions_map_to_the_three_levels() -> None:
    assert levels_held(frozenset({"preparer"})) == {"preparer"}
    assert levels_held(frozenset({"detail_reviewer", "first_level_reviewer"})) == {"detail"}
    assert levels_held(frozenset({"manager_reviewer"})) == {"manager"}
    assert levels_held(frozenset({"signer", "preparer"})) == {"manager", "preparer"}
    assert levels_held(frozenset({"eqr", "specialist"})) == frozenset()


def test_the_viewer_level_is_the_highest_held() -> None:
    assert viewer_level(frozenset({"preparer", "detail"})) == "detail"
    assert viewer_level(frozenset()) is None
    assert LEVELS == ("preparer", "detail", "manager")


def test_kevin_a_detail_reviewer_holds_no_manager_level() -> None:
    assert "manager" not in levels_held(frozenset({"detail_reviewer"}))
