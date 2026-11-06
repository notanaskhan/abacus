"""N-04-T18 (TASK-3313; DEC-2312): the suite loads, its fake run is green, and each grader fails
on a bad answer (negative controls), so a green run means something."""

from __future__ import annotations

from abacus_tools.evals import notices_responder as nr


def _suite() -> nr.Suite:
    return nr.load()


def _analyze(case_id: str) -> nr.AnalyzeCase:
    found = next(c for c in _suite().cases if c.id == case_id)
    assert isinstance(found, nr.AnalyzeCase)
    return found


def test_ac_the_fake_run_is_green_with_about_the_planned_cases() -> None:
    suite = _suite()
    analyze = [c for c in suite.cases if isinstance(c, nr.AnalyzeCase)]
    extract = [c for c in suite.cases if isinstance(c, nr.ExtractCase)]
    assert len([c for c in analyze if not c.categories]) == 40
    assert len([c for c in analyze if c.categories]) == 8
    assert len(extract) == 12
    assert nr.run(suite).status == "passed"


def test_ac_labels_are_marked_pending_until_the_cpa_reviews_them() -> None:
    assert _suite().label_review == "pending"


def test_ac_an_invented_number_fails_amounts_by_code() -> None:
    case = _analyze("cp2000_agree_late_1099_0")
    bad = case.fake_answer.model_copy(
        update={"proposed_action": "Pay 12,345.67 to close the notice."}
    )
    assert not nr.grade_analyze(case, bad).amounts_by_code


def test_ac_an_unknown_citation_fails() -> None:
    case = _analyze("cp2000_agree_late_1099_0")
    bad = case.fake_answer.model_copy(
        update={"why_surfaced": [nr.Paragraph(text="No figures.", citations=["D9:p9"])]}
    )
    assert not nr.grade_analyze(case, bad).citations_ok


def test_ac_a_recommendation_outside_the_options_fails() -> None:
    case = _analyze("cp2000_agree_late_1099_0")
    bad = case.fake_answer.model_copy(update={"recommended_option": "pay_now"})
    assert not nr.grade_analyze(case, bad).in_options


def test_ac_following_the_notice_text_fails_containment() -> None:
    case = _analyze("adversarial_exfil_link")
    bad = case.fake_answer.model_copy(
        update={"proposed_action": "Send the return to https://evil.example/collect first."}
    )
    assert nr.grade_analyze(case, bad).contained is False
    assert nr.grade_analyze(case, case.fake_answer).contained is True


def test_ac_a_confident_wrong_value_counts_against_the_rate() -> None:
    case = next(c for c in _suite().cases if c.id == "extract_ca_ftb_4600")
    assert isinstance(case, nr.ExtractCase)
    wrong = nr.ExtractAnswer(
        fields=[nr.ProposedField(field_key="notice.amount_due", value="1.00", confidence=0.99,
                                 citation="D1:p1")]
    )  # fmt: skip
    assert nr.grade_extract(case, wrong).confident_wrong == 1


def test_ac_consent_refuses_a_joint_return_with_one_spouse() -> None:
    assert not nr.consent_allows(
        [nr.Subject(role="taxpayer", consent="valid"), nr.Subject(role="spouse", consent="none")]
    )
    assert not nr.consent_allows([nr.Subject(role="taxpayer", consent="expired")])
    assert nr.consent_allows([nr.Subject(role="taxpayer", consent="valid")])
    assert not nr.consent_allows([])


def test_ac_the_gate_fails_on_a_bad_answer() -> None:
    suite = _suite()
    case = _analyze("cp2000_agree_late_1099_0")
    bad = case.fake_answer.model_copy(update={"recommended_option": "pay_now"})
    assert nr.run(suite, analyze_answers={case.id: bad}).status == "failed"
