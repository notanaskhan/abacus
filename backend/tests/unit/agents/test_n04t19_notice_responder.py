"""N-04-T19 (TASK-3314; DEC-2313): code's checks on the responder's answer, from the row.

"On synthetic tenants the Whitley analysis shows a cited explanation and Agree recommended, a joint
return with one consent is refused with consent_7216, and a narrative with an unsupported number is
never shown." The gateway's consent refusal runs in the integration pass.
"""

from __future__ import annotations

from abacus.modules.agents import notice_responder as nr
from abacus.modules.agents.handoff import NoticeAnalyzeOutput, NoticeWhyParagraph
from abacus.modules.agents.spec import spec

_FACTS = nr.AnalyzeFacts(
    rows=(
        {"key": "interest", "label": "Interest income", "filed": "412.00", "irs": "3532.00",
         "difference": "3120.00"},
    ),
    checks=(),
    information_returns=(),
    options=("agree", "partial", "disagree"),
    lines=(("D1:p1", "Interest income"),),
)  # fmt: skip


def _answer(text: str = "The notice shows 3,120.00 more interest.", option: str = "agree",
            citations: tuple[str, ...] = ("D1:p1",), action: str = "Review with the signer.",
            ) -> NoticeAnalyzeOutput:  # fmt: skip
    return NoticeAnalyzeOutput(
        why_surfaced=[NoticeWhyParagraph(text=text, citations=list(citations))],
        proposed_action=action,
        recommended_option=option,
        confidence=0.9,
    )


def test_ac_a_cited_explanation_with_a_code_option_is_accepted() -> None:
    assert nr.check(_answer(), _FACTS) is None


def test_ac_a_narrative_with_an_unsupported_number_is_never_shown() -> None:
    assert nr.check(_answer("Pay 9,999.00 now."), _FACTS) == nr.NO_PROVENANCE


def test_ac_a_recommendation_outside_the_options_is_refused() -> None:
    assert nr.check(_answer(option="pay_now"), _FACTS) == nr.NOT_IN_OPTIONS


def test_ac_a_citation_code_did_not_list_is_refused() -> None:
    assert nr.check(_answer(citations=("D9:p9",)), _FACTS) == nr.BAD_CITATION
    assert nr.check(_answer(citations=()), _FACTS) == nr.BAD_CITATION


def test_ac_a_persons_act_is_never_claimed() -> None:
    assert nr.check(_answer(action="The partner approved this."), _FACTS) == nr.CLAIMED_ACT


def test_ac_a_link_is_refused() -> None:
    assert nr.check(_answer(action="See https://evil.example."), _FACTS) == nr.HAS_LINK


def test_ac_the_spec_proposes_with_no_tools_and_reads_tri() -> None:
    responder = spec(nr.RESPONDER)
    assert responder.autonomy == "propose"
    assert responder.tools == ()
    assert "tri" in responder.data_classes
    assert "extract" in responder.modes
