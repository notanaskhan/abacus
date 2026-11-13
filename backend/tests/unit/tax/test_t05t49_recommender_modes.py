"""T-05-T49 (TASK-7706; T-05 F10; DEC-4709): the recommender's convention_706d and section_754
modes. Options always from code, the recommendation inside the allowed set, a cited reason, no
person's act claimed, numbers with provenance; the §743(b) placeholder is code's 28,595."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from abacus.modules.agents.decision_recommend import (
    CLAIMED_ACT,
    NO_PROVENANCE,
    OUTSIDE_SET,
    UNKNOWN_FACT,
)
from abacus.modules.agents.handoff import DecisionSuggestion
from abacus.modules.agents.recommender_modes import MISSING_CITATION, check, prompt_of
from abacus.modules.tax.recommendation_facts import convention_facts, section_754_facts

CLAUSES = [("clause:assignment_3", "Assignment §3", "closing of the books as of June 30, 2025")]
C706 = convention_facts(date(2025, 6, 30), Decimal(331405), CLAUSES)
S754 = section_754_facts(date(2025, 6, 30), Decimal(360000), Decimal(331405))


def _answer(key: str, text: str, facts: list[str]) -> DecisionSuggestion:
    return DecisionSuggestion.model_validate(
        {"recommended_option_key": key, "reasons": [{"text": text, "facts": facts}]}
    )


def test_the_options_are_the_three_conventions_with_their_book_closings() -> None:
    assert [o.key for o in C706.options] == ["calendar_day", "semi_monthly", "monthly"]
    assert C706.options[2].label == "Monthly (books close 6/30/2025)"
    assert {f.value for f in C706.facts} == {"6/30/2025", "331,405"}


def test_a_cited_monthly_recommendation_is_accepted() -> None:
    answer = _answer(
        "monthly",
        "The assignment closes the books at 6/30/2025, which the monthly convention matches.",
        ["clause:assignment_3", "fact:transfer_date"],
    )
    assert check(answer, C706) is None


def test_an_option_outside_the_set_an_unknown_fact_or_an_uncited_answer_is_refused() -> None:
    assert (
        check(_answer("daily", "Daily is closest.", ["fact:transfer_date"]), C706) == OUTSIDE_SET
    )
    assert check(_answer("monthly", "It fits.", ["fact:invented"]), C706) == UNKNOWN_FACT
    assert check(_answer("monthly", "It fits.", ["fact:transfer_date"]), C706) == MISSING_CITATION


def test_a_number_without_provenance_or_a_claimed_act_is_refused() -> None:
    assert (
        check(
            _answer("do_not_elect", "The adjustment is 40,000.", ["fact:placeholder_743b"]), S754
        )
        == NO_PROVENANCE
    )
    assert (
        check(_answer("elect", "The partner elected it.", ["fact:placeholder_743b"]), S754)
        == CLAIMED_ACT
    )


def test_section_754_placeholder_is_code_computed() -> None:
    placeholder = next(f for f in S754.facts if f.ref == "fact:placeholder_743b")
    assert placeholder.value == "28,595"  # 360,000 - 331,405
    answer = _answer(
        "do_not_elect",
        "The 28,595 placeholder is small against the administrative cost of tracking it.",
        ["fact:placeholder_743b"],
    )
    assert check(answer, S754) is None


def test_each_mode_has_its_own_prompt() -> None:
    assert prompt_of("convention_706d") == "decisions.recommend.convention_706d@v1"
    assert prompt_of("section_754") == "decisions.recommend.section_754@v1"
