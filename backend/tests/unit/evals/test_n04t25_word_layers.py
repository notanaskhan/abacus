"""N-04-T25 (TASK-6015; DEC-2611): every extract case carries the notice's word layer.

A real run skips an extract case with no word layer and fails the report
(`extract_cases_without_lines`). These checks hold the layers to their labels: each labelled value
is legible on a clean scan; on a degraded scan the respond-by date is garbled, which is why it is
the case's low-confidence field.
"""

from __future__ import annotations

from datetime import date

from abacus_tools.evals.notices_responder import ExtractCase, load

SUITE = load()
EXTRACT = [c for c in SUITE.cases if isinstance(c, ExtractCase)]


def _text(case: ExtractCase) -> str:
    return " ".join(line.text for line in case.document_lines)


def _spelled(value: str) -> str:
    d = date.fromisoformat(value)
    return f"{d:%B} {d.day}, {d:%Y}"


def test_every_extract_case_has_a_word_layer() -> None:
    assert len(EXTRACT) == 12
    assert [c.id for c in EXTRACT if not c.document_lines] == []


def test_the_fake_answers_cite_lines_in_the_layer() -> None:
    for case in EXTRACT:
        refs = {line.ref for line in case.document_lines}
        assert {f.citation for f in case.fake_answer.fields} <= refs, case.id


def test_labelled_number_amount_and_year_are_legible() -> None:
    for case in EXTRACT:
        text, expected = _text(case), {f.field_key: f.value for f in case.expected_fields}
        assert f"Notice number: {expected['notice.number']}." in text, case.id
        assert f"${expected['notice.amount_due']}" in text, case.id
        assert f"Tax year {expected['notice.tax_year']}" in text, case.id


def test_respond_by_is_legible_only_on_clean_scans() -> None:
    for case in EXTRACT:
        expected = {f.field_key: f.value for f in case.expected_fields}
        respond_by = expected["notice.respond_by"]
        legible = _spelled(respond_by) in _text(case)
        assert legible == (case.scan == "clean"), case.id
        assert ("notice.respond_by" in case.low_confidence_fields) == (case.scan == "degraded")
