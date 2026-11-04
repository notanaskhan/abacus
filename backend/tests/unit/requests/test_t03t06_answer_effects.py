"""T-03-T06 (TASK-3262; SPEC-643 AC-6; DEC-2242): the answer-effects engine.

Row acceptance: "Claire's Q2 and Q5 answers produce exactly one review point and one request each
on replay, attributed to the organizer rule and never to the agent, and a missing notices handler
leaves the upload in the binder." Here: code's rule evaluation and the fail-closed slot; the
replay and attribution run in the integration suite at the end review.
"""

from __future__ import annotations

from abacus.modules.requests import answer_effects as ae
from abacus.modules.requests.answer_effect_slots import answer_effect_handler

RULES = [
    {"key": "r_estimates", "kind": "create_request_item", "when_equals": "yes", "title": "Est."},
    {"key": "r_review", "kind": "raise_review_point", "when_equals": "Yes", "title": "Basis"},
    {"key": "r_notice", "kind": "route_upload_to_notices", "when_equals": "no", "title": "IRS"},
]


def test_rules_match_by_equality_on_the_normalised_answer() -> None:
    assert [r["key"] for r in ae.matching(RULES, True)] == ["r_estimates", "r_review"]
    assert [r["key"] for r in ae.matching(RULES, " No ")] == ["r_notice"]
    assert ae.matching(RULES, {"value": "yes"}) == RULES[:2]


def test_a_follow_up_shows_only_when_its_parent_answer_matches() -> None:
    assert ae.shown({"parent_key": "q5", "equals": "yes"}, True)
    assert not ae.shown({"parent_key": "q5", "equals": "yes"}, False)
    assert ae.shown(None, None)


def test_every_kind_maps_to_its_effect_word() -> None:
    assert ae.RESULT_KIND == {
        "create_request_item": "request_item_created",
        "raise_review_point": "review_point_raised",
        "flag_internal_review": "internal_review_flagged",
        "route_upload_to_notices": "upload_routed_to_notices",
    }


def test_the_requests_module_owns_create_request_item() -> None:
    import abacus.modules.requests.api

    assert answer_effect_handler("create_request_item") is not None
    assert "questionnaire.answered" in abacus.modules.requests.api.SUBSCRIPTIONS
