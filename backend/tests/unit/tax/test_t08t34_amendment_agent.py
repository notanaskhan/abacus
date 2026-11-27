"""T-08-T34 (TASK-9007; SPEC-710 AC6.2, AC6.6; ADR-005, ADR-050; DEC-6013; red): the drafter's
`amendment` mode and the recommender's `bba_route`. Row acceptance: "The amendment proposal and
the push-out recommendation are suggestions with verified citations, and neither can record an
election or touch the original." Here: code's facts carry every figure and no digit of a line in
their ids; the Part II answer settles only over those facts and offered pages, never with talking
points; the recommendation's checks refuse an unoffered key, an unknown fact, a free number and a
claimed act; both paths write only suggestions on registered targets (and the drafter a proposed
checkpoint), never an election, a decision or the original return."""

from __future__ import annotations

import inspect
import re
from decimal import Decimal as D
from pathlib import Path

import pytest

from abacus.modules.agents.handoff import DecisionSuggestion
from abacus.modules.agents.recommender_modes import MODES, check, prompt_of
from abacus.modules.tax import amendment_agent as aa
from abacus.modules.tax import practice_modes as pm
from abacus.modules.tax.compute import amendment as calc
from abacus.modules.tax.recommendation_facts import bba_route_facts

PROMPTS = Path(aa.__file__).resolve().parents[2] / "ai_gateway" / "prompts"
FILED = {
    "1040.11": D("212400"),
    "1040.12": D("29200"),
    "1040.15": D("183200"),
    "1040.16": D("37400"),
    "1040.24": D("40386"),
    "1040.33": D("41000"),
}
AMENDED = {
    **FILED,
    "1040.12": D("38660"),
    "1040.15": D("173740"),
    "1040.16": D("35206"),
    "1040.24": D("37678"),
}


def _given() -> pm.ModeInput:
    subjects, facts = aa.amendment_facts(calc.amend("federal", FILED, AMENDED))
    return pm.ModeInput(
        mode="amendment",
        subjects=subjects,
        facts=facts,
        sources=[
            pm.SourceIn(source="sa", title="2025 Form 1098 Lakeview Credit Union", pages=[1])
        ],
        untrusted=["sa page 1: Mortgage interest received from payer(s)/borrower(s) 9,460.00"],
    )


def _answer(**over: object) -> pm.ModeOutput:
    body: dict[str, object] = {
        "key": "part_ii",
        "blocks": {
            "version": 1,
            "parts": [
                {
                    "kind": "p",
                    "segments": [
                        {"kind": "text", "text": "Itemized deductions rise to "},
                        {"kind": "fact", "fact_id": "laa_amended"},
                        {
                            "kind": "text",
                            "text": " for mortgage interest on a lender statement received "
                            "after filing; total tax changes by ",
                        },
                        {"kind": "fact", "fact_id": "total_change"},
                        {"kind": "text", "text": "."},
                    ],
                }
            ],
        },
        "quotes": [{"source": "sa", "page": 1, "quote": "Mortgage interest received"}],
    }
    body.update(over)
    return pm.ModeOutput.model_validate({"subjects": [body]})


def test_t08t34_the_facts_are_codes_and_carry_no_line_digits() -> None:
    subjects, facts = aa.amendment_facts(calc.amend("federal", FILED, AMENDED))
    by_id = {f.id: f.value for f in facts}
    assert by_id["total_change"] == "-2708.00" and by_id["refund_due"] == "2708.00"
    assert [s.key for s in subjects] == ["part_ii"]
    for fact in facts:
        assert not re.search(r"\d", fact.id), fact.id
    # Only changed lines are facts: AGI and payments did not move.
    assert all("1040.11" not in f.basis and "1040.33" not in f.basis for f in facts)


def test_t08t34_part_ii_settles_over_codes_facts_and_renders_its_values() -> None:
    given = _given()
    [part] = pm.settle(given, _answer())
    text = pm.render(part.blocks, given.facts, limit=4000)
    assert "38,660" in text or "38660" in text
    assert "2,708" in text or "2708" in text


@pytest.mark.parametrize(
    ("over", "reason"),
    [
        ({"talking_points": {"version": 1, "parts": []}}, "talking_points_not_offered"),
        (
            {"quotes": [{"source": "sa", "page": 9, "quote": "Mortgage interest received"}]},
            "page_not_offered",
        ),
        ({"key": "other"}, "subjects_not_answered"),
    ],
)
def test_t08t34_part_ii_is_refused_off_its_facts_or_pages(
    over: dict[str, object], reason: str
) -> None:
    with pytest.raises(pm.OutputRefused) as refused:
        pm.settle(_given(), _answer(**over))
    assert (refused.value.facts or {}).get("reason") == reason


def test_t08t34_a_free_number_in_part_ii_is_refused() -> None:
    free = {
        "version": 1,
        "parts": [
            {"kind": "p", "segments": [{"kind": "text", "text": "Tax falls by 2,708 dollars."}]}
        ],
    }
    with pytest.raises(pm.OutputRefused):
        pm.settle(_given(), _answer(blocks=free))


def test_t08t34_bba_route_options_and_facts_are_codes() -> None:
    facts = bba_route_facts(D("40000"), D("14800"))
    assert facts.mode == "bba_route" and "bba_route" in MODES
    assert [o.key for o in facts.options] == ["pay_imputed_underpayment", "push_out"]
    assert {f.ref: f.value for f in facts.facts} == {
        "fact:adjustments": "40,000",
        "fact:imputed_underpayment": "14,800",
    }
    assert prompt_of("bba_route") == "decisions.recommend.bba_route@v1"
    assert (PROMPTS / "decisions.recommend.bba_route" / "v1.txt").exists()
    assert (PROMPTS / "tax.return_drafter.amendment" / "v1.txt").exists()


def _suggestion(key: str, reason: str, refs: list[str]) -> DecisionSuggestion:
    return DecisionSuggestion.model_validate(
        {"recommended_option_key": key, "reasons": [{"text": reason, "facts": refs}]}
    )


def test_t08t34_the_recommendation_is_checked_by_code() -> None:
    facts = bba_route_facts(D("40000"), D("14800"))
    good = _suggestion(
        "push_out", "The partners can absorb an adjustment of 40,000.", ["fact:adjustments"]
    )
    assert check(good, facts) is None
    assert check(_suggestion("elect_out", "No.", ["fact:adjustments"]), facts) is not None
    assert check(_suggestion("push_out", "Fine.", ["fact:rate"]), facts) is not None
    assert (
        check(_suggestion("push_out", "A rate of 37% applies.", ["fact:adjustments"]), facts)
        is not None
    )  # a number that is no fact's figure
    assert (
        check(
            _suggestion("push_out", "The partner elected to push out.", ["fact:adjustments"]),
            facts,
        )
        is not None
    )  # a claimed act


def test_t08t34_acceptance_neither_path_records_an_election_or_touches_the_original() -> None:
    source = inspect.getsource(aa)
    for forbidden in (
        "INSERT INTO aar_elections",
        "UPDATE tax_returns",
        "decide_card",
        "UPDATE amendments",
        "return_supersessions",
        "approve(",
    ):
        assert forbidden not in source, forbidden
    assert aa.CHECKPOINT_NAME == "Amendment draft"
    # The only writes: two suggestion targets, the agent's Part II version and the proposal.
    assert set(re.findall(r"target_type=([A-Z_]+)", source)) == {
        "PART_II_TARGET",
        "ELECTION_TARGET",
    }
    assert source.count("propose_checkpoint(") == 1


def test_t08t34_the_drafter_spec_holds_the_scopes_the_mode_uses() -> None:
    from abacus.modules.agents.api import spec_v2

    spec = spec_v2(aa.CAPABILITY)
    assert {"suggestion.create", "checkpoint.propose", "evidence.read"} <= set(spec.task_scope)
    assert "tri" in spec.data_classes
