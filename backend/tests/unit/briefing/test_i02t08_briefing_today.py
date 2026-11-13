"""I-02-T08 (TASK-7718; I-02 §6; DEC-4721): `briefing.today` v1's code validation.

Row acceptance: "On FakeModel a why line with 28,600 or 'I approved' is repaired or stored as
unverified and never displayed, and the step replays from its committed history."
"""

from __future__ import annotations

import uuid
from datetime import date

from abacus.modules.agents.api import spec_v2
from abacus.modules.agents.blocks import AgentBlocks, Fact
from abacus.modules.agents.briefing.facts import BriefingFacts, GateFact
from abacus.modules.agents.briefing.today import (
    CAPABILITY,
    EngagementBriefing,
    WhyLine,
    validate,
)

G754, GCAP = uuid.uuid4(), uuid.uuid4()
FACTS = BriefingFacts(
    engagement_id=uuid.uuid4(),
    viewer_user_id=uuid.uuid4(),
    gates=(
        GateFact(G754, "decision", "decision", uuid.uuid4(), None, date(2026, 9, 15), True, None),
        GateFact(GCAP, "sign_off", "workpaper", uuid.uuid4(), None, None, False, None),
    ),
    facts={
        "section_754_placeholder": Fact(
            id="section_754_placeholder", kind="money", value="28595", basis="code"
        ),
        "tie_out_item_l_m2": Fact(
            id="tie_out_item_l_m2", kind="money", value="6200", basis="code"
        ),
    },
    citations=(),
    subjects=(),
    facts_hash="0" * 64,
)
RECS = {str(G754): "do_not_elect", str(GCAP): None}


def _p(*segments: dict[str, object]) -> AgentBlocks:
    return AgentBlocks.model_validate({"parts": [{"kind": "p", "segments": list(segments)}]})


def _text(t: str) -> dict[str, object]:
    return {"kind": "text", "text": t}


def _fact(f: str) -> dict[str, object]:
    return {"kind": "fact", "fact_id": f}


def _briefing(
    why754: AgentBlocks, whycap: AgentBlocks, rec: str | None = "do_not_elect"
) -> EngagementBriefing:
    return EngagementBriefing(
        summary=_p(_text("Two items wait on you for Ridgeline.")),
        why=[
            WhyLine(gate_id=str(G754), line=why754, recommendation=rec),
            WhyLine(gate_id=str(GCAP), line=whycap),
        ],
    )


GOOD_754 = _p(_text("The §743(b) placeholder is "), _fact("section_754_placeholder"), _text("."))
GOOD_CAP = _p(_text("Capital Accounts is off "), _fact("tie_out_item_l_m2"), _text("."))


def test_a_cited_briefing_passes() -> None:
    assert validate(_briefing(GOOD_754, GOOD_CAP), FACTS, RECS) == []


def test_a_typed_number_28600_is_refused() -> None:
    bad = _p(_text("The §743(b) placeholder is 28,600."))
    codes = validate(_briefing(bad, GOOD_CAP), FACTS, RECS)
    assert any(c.startswith("blocks:") for c in codes) or "uncited_line" in codes


def test_i_approved_is_refused() -> None:
    bad = _p(
        _text("I approved the capital fix; it is off "), _fact("tie_out_item_l_m2"), _text(".")
    )
    assert "reserved_verb" in validate(_briefing(GOOD_754, bad), FACTS, RECS) or any(
        c.startswith("blocks:") for c in validate(_briefing(GOOD_754, bad), FACTS, RECS)
    )


def test_a_missing_gate_and_a_changed_recommendation_are_refused() -> None:
    one = EngagementBriefing(
        summary=_p(_text("One item.")), why=[WhyLine(gate_id=str(G754), line=GOOD_754)]
    )
    assert "gate_coverage" in validate(one, FACTS, RECS)
    assert "recommendation_fidelity" in validate(
        _briefing(GOOD_754, GOOD_CAP, rec="elect"), FACTS, RECS
    )


def test_the_spec_is_a_tool_less_workflow_on_its_suite() -> None:
    spec = spec_v2(CAPABILITY)
    assert spec.prompt == "briefing.today@v1"
    assert spec.evaluation_suite == "evals/briefing_today"
    assert not [t for group in spec.tools.values() for t in group]  # type: ignore[union-attr] -- a test double stands in for the typed object
