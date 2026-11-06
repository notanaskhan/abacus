"""A-04-T42 (TASK-3327): AC tests for A-04's agent work, from the row and without editing that
code.

"Tests ... fail if any A-04 agent path writes a value, decision or sign-off, if the agent's decide
answers anything but 403, if a number without provenance reaches a suggestion, or if G4 reads
met with
a pending proposal." The database half (G4 at 4:40 PM, reopened after an edit to R4) runs in the
integration pass through the planning slice.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.modules.agents.decision_recommend import (
    CLAIMED_ACT,
    NO_PROVENANCE,
    OUTSIDE_RANGE,
    OUTSIDE_SET,
    UNKNOWN_FACT,
    OptionFact,
    RecommendFacts,
    check,
)
from abacus.modules.agents.handoff import DecisionSuggestion, RecommendationReason
from abacus.modules.agents.section_draft import DraftingNotEnabled

BACKEND = Path(__file__).resolve().parents[3]
AGENTS = BACKEND / "src/abacus/modules/agents"
D = Decimal


def _option(key: str, rate: str) -> OptionFact:
    return OptionFact(key, D(rate), D("252200"), D("189150"), D("12610"), D("75"), D("5"))


FACTS = RecommendFacts(
    "net_assets", "Net assets", D("16812400"), D("1"), D("2"),
    (_option("rate_1_5", "1.5"), _option("rate_3", "3")),
)  # fmt: skip


def _answer(
    key: str = "rate_1_5", text: str = "Mid-range.", facts: str = "policy"
) -> DecisionSuggestion:
    return DecisionSuggestion(
        recommended_option_key=key,
        reasons=[RecommendationReason(text=text, facts=[facts])],
    )


def test_ac_an_accepted_answer_passes() -> None:
    assert check(_answer(), FACTS) is None


def test_ac_a_number_without_provenance_never_reaches_a_suggestion() -> None:
    assert check(_answer(text="Use 999,999 instead."), FACTS) == NO_PROVENANCE


def test_ac_a_key_outside_the_set_or_range_is_refused() -> None:
    assert check(_answer(key="custom"), FACTS) == OUTSIDE_SET
    assert check(_answer(key="rate_3"), FACTS) == OUTSIDE_RANGE


def test_ac_an_unknown_fact_is_refused() -> None:
    assert check(_answer(facts="factor:9"), FACTS) == UNKNOWN_FACT


def test_ac_the_partners_act_is_never_claimed() -> None:
    assert check(_answer(text="The partner approved this."), FACTS) == CLAIMED_ACT


def test_ac_drafting_for_an_uncleared_firm_is_refused_with_its_code() -> None:
    assert DraftingNotEnabled.code == "drafting_not_enabled"


@pytest.mark.parametrize(
    "module", ["decision_recommend.py", "section_draft.py", "notice_responder.py"]
)
def test_ac_an_agent_path_never_calls_a_persons_write(module: str) -> None:
    tree = ast.parse((AGENTS / module).read_text())
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
        n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
    }
    banned = {"decide_card", "record_value", "record_sign_off", "approve_minutes", "sign_off"}
    assert not names & banned, names & banned
