"""AC-15: the handoff contract and typed citations (TASK-011a interface contract, "Handoff and
citations"; ADR-054, ADR-066).

A citation names a spreadsheet cell and optionally the text or number the agent says it holds; the
handoff proposes one of two actions with a confidence and a short rationale. Expectations come from
the contract, not the implementation.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from pydantic import ValidationError

from abacus.modules.agents.api import Citation, Handoff, ScreeningOutput, VerifiedCitation


def _output(**changes: object) -> dict[str, object]:
    return {
        "action": "ready_for_review",
        "confidence": 0.9,
        "rationale": "Debits equal credits.",
        "citations": [],
        "unverified": [],
        **changes,
    }


# --- Citation ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cell", ["A1", "B12", "C34", "Z9", "AA10", "AAA1", "XFD1048576", "A1234567", "AAA1234567"]
)
def test_ac15_a_cell_reference_in_the_allowed_shape_is_accepted(cell: str) -> None:
    assert Citation(cell=cell).cell == cell


@pytest.mark.parametrize(
    "cell",
    [
        "",
        "a1",
        "A0",
        "A01",
        "A",
        "1A",
        "1",
        "AAAA1",
        "A12345678",
        "A1 ",
        " A1",
        "A1\n",
        "A-1",
        "A$1",
        "$A$1",
        "A1:B2",
        "Sheet1!A1",
        "A1;",
        "À1",
        "A" + chr(0x661),
    ],
)
def test_ac15_a_cell_reference_outside_the_allowed_shape_is_refused(cell: str) -> None:
    with pytest.raises(ValidationError):
        Citation(cell=cell)


def test_ac15_a_quote_of_two_hundred_characters_is_accepted() -> None:
    assert Citation(cell="A1", quote="q" * 200).quote == "q" * 200


def test_ac15_a_quote_over_two_hundred_characters_is_refused() -> None:
    with pytest.raises(ValidationError):
        Citation(cell="A1", quote="q" * 201)


def test_ac15_a_citation_may_carry_only_a_cell() -> None:
    citation = Citation(cell="A1")
    assert citation.quote is None
    assert citation.value is None


def test_ac15_a_value_is_a_decimal_never_a_float() -> None:
    citation = Citation.model_validate({"cell": "C2", "value": "1200.50"})
    assert citation.value == Decimal("1200.50")
    assert isinstance(citation.value, Decimal)


def test_ac15_a_value_that_is_not_a_number_is_refused() -> None:
    with pytest.raises(ValidationError):
        Citation.model_validate({"cell": "C2", "value": "twelve"})


def test_ac15_a_citation_with_an_extra_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        Citation.model_validate({"cell": "A1", "note": "because"})


def test_ac15_a_citation_without_a_cell_is_refused() -> None:
    with pytest.raises(ValidationError):
        Citation.model_validate({"quote": "Total"})


def test_ac15_a_citation_is_immutable() -> None:
    citation = Citation(cell="A1")
    with pytest.raises(ValidationError):
        citation.cell = "B2"


# --- ScreeningOutput -----------------------------------------------------------------------------


def test_ac15_a_valid_output_is_accepted() -> None:
    output = ScreeningOutput.model_validate(_output())
    assert output.action == "ready_for_review"
    assert output.confidence == 0.9
    assert output.citations == []
    assert output.unverified == []


@pytest.mark.parametrize("action", ["ready_for_review", "needs_revision"])
def test_ac15_the_two_proposable_actions_are_accepted(action: str) -> None:
    assert ScreeningOutput.model_validate(_output(action=action)).action == action


@pytest.mark.parametrize(
    "action",
    [
        "accepted",
        "accept",
        "rejected",
        "waived",
        "confirmed",
        "ready",
        "READY_FOR_REVIEW",
        "",
        None,
    ],
)
def test_ac15_an_action_that_is_a_human_decision_or_unknown_is_refused(action: object) -> None:
    with pytest.raises(ValidationError):
        ScreeningOutput.model_validate(_output(action=action))


@pytest.mark.parametrize("confidence", [0, 0.0, 0.5, 1, 1.0])
def test_ac15_a_confidence_from_zero_to_one_is_accepted(confidence: float) -> None:
    assert ScreeningOutput.model_validate(_output(confidence=confidence)).confidence == confidence


@pytest.mark.parametrize("confidence", [-0.01, -1, 1.01, 7, 100, "high", None])
def test_ac15_a_confidence_outside_zero_to_one_is_refused(confidence: object) -> None:
    with pytest.raises(ValidationError):
        ScreeningOutput.model_validate(_output(confidence=confidence))


@pytest.mark.parametrize("length", [1, 2, 1_999, 2_000])
def test_ac15_a_rationale_of_one_to_two_thousand_characters_is_accepted(length: int) -> None:
    assert len(ScreeningOutput.model_validate(_output(rationale="r" * length)).rationale) == length


@pytest.mark.parametrize("rationale", ["", "r" * 2_001, "r" * 10_000, None, 5])
def test_ac15_a_rationale_empty_or_too_long_is_refused(rationale: object) -> None:
    with pytest.raises(ValidationError):
        ScreeningOutput.model_validate(_output(rationale=rationale))


def test_ac15_an_output_with_an_extra_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        ScreeningOutput.model_validate(_output(decision="accept"))


@pytest.mark.parametrize(
    "missing", ["action", "confidence", "rationale", "citations", "unverified"]
)
def test_ac15_an_output_missing_a_field_is_refused(missing: str) -> None:
    raw = _output()
    del raw[missing]
    with pytest.raises(ValidationError):
        ScreeningOutput.model_validate(raw)


def test_ac15_an_output_with_an_invalid_citation_is_refused() -> None:
    with pytest.raises(ValidationError):
        ScreeningOutput.model_validate(_output(citations=[{"cell": "a1"}]))


def test_ac15_an_output_carries_typed_citations_and_notes() -> None:
    output = ScreeningOutput.model_validate(
        _output(
            citations=[{"cell": "C34", "value": "100.00"}, {"cell": "B34", "quote": "Total"}],
            unverified=["bank statements"],
        )
    )
    assert [c.cell for c in output.citations] == ["C34", "B34"]
    assert all(isinstance(c, Citation) for c in output.citations)
    assert output.unverified == ["bank statements"]


def test_ac15_an_unverified_note_must_be_a_string() -> None:
    with pytest.raises(ValidationError):
        ScreeningOutput.model_validate(_output(unverified=[1]))


def test_ac15_an_output_parses_from_json_text_as_the_gateway_does() -> None:
    body = json.dumps(_output(citations=[{"cell": "C2", "value": "5.00"}]))
    assert ScreeningOutput.model_validate_json(body).citations[0].value == Decimal("5.00")


def test_ac15_json_that_is_not_an_object_is_refused() -> None:
    for body in ("[]", '"ready"', "null", "7", "plain prose", ""):
        with pytest.raises(ValidationError):
            ScreeningOutput.model_validate_json(body)


def test_ac15_an_output_is_immutable() -> None:
    output = ScreeningOutput.model_validate(_output())
    with pytest.raises(ValidationError):
        output.action = "needs_revision"


def test_ac15_the_screening_output_is_a_handoff() -> None:
    assert issubclass(ScreeningOutput, Handoff)
    assert {"confidence", "rationale", "citations", "unverified"} <= set(Handoff.model_fields)
    assert "action" not in Handoff.model_fields  # each agent declares what it may propose
    assert "action" in ScreeningOutput.model_fields


# --- VerifiedCitation ----------------------------------------------------------------------------


def test_ac15_a_verified_citation_records_the_outcome_and_the_reason() -> None:
    verified = VerifiedCitation(cell="A1", quote=None, value="1.50", verified=False, reason="x")
    assert (verified.cell, verified.value, verified.verified, verified.reason) == (
        "A1",
        "1.50",
        False,
        "x",
    )
    assert json.loads(verified.model_dump_json())["verified"] is False
