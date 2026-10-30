"""N-01-T17: the rule classifier and the code flags (pure)."""

from __future__ import annotations

import uuid
from dataclasses import replace

from abacus.modules.communications.triage_flags import FlagFacts, ambiguous, code_flags
from abacus.modules.evidence.classifier import classify, normalised_name, rules

_BASE = FlagFacts(
    media_type="application/pdf",
    has_text_layer=True,
    tax_year=2025,
    tin_last4=None,
    corrected=None,
    confidence=0.95,
    low_confidence_below=0.6,
)


def _facts(**over: object) -> FlagFacts:
    return replace(_BASE, **over)


def test_rules_file_loads_and_is_versioned() -> None:
    assert rules().version
    assert any(f.family == "1095-C" for f in rules().families)


def test_name_and_text_agree_on_family_and_year() -> None:
    found = classify(
        "Feld_1095C_2025.pdf",
        ["Form 1095-C Employer-Provided Health Insurance Offer and Coverage Tax year 2025"],
        page_count=2,
    )
    assert (found.form_family, found.form_code, found.tax_year) == ("1095-C", "1095-C", 2025)
    assert found.confidences["form_family"] == 0.95 and found.confidences["tax_year"] == 0.95
    assert found.page_count == 2 and found.kind == "tax_form"


def test_w2c_is_the_w2_family_and_corrected() -> None:
    found = classify("Collins_W-2c_2025.pdf", [], page_count=1, tin_last4s=["7713", "1234"])
    assert (found.form_family, found.form_code, found.corrected) == ("W-2", "W-2c", True)
    assert found.taxpayer_tin_last4 == "7713"


def test_a_form_number_is_never_read_as_a_year() -> None:
    assert classify("Stein_CP2000.pdf", [], page_count=1).tax_year is None
    assert normalised_name("Iyer_2025_1099-DIV.PDF") == "iyer 2025 1099 div"


def test_conflicting_years_take_the_text_at_low_confidence() -> None:
    found = classify("Feld_1095C_2024.pdf", ["Form 1095-C Tax year 2025"], page_count=1)
    assert found.tax_year == 2025 and found.confidences["tax_year"] == 0.5


def test_unknown_document_is_other() -> None:
    found = classify("IMG_0042.heic", [], page_count=1)
    assert (found.form_family, found.kind, found.overall) == ("Other", "other", 0.0)


def test_wrong_year_and_duplicate_block_bulk() -> None:
    version = uuid.uuid4()
    flags = code_flags(
        _facts(tax_year=2024, duplicate_version_id=version, expected_years=frozenset({2025}))
    )
    assert [(f.kind, f.severity) for f in flags] == [
        ("duplicate_hash", "block_bulk"),
        ("wrong_year", "block_bulk"),
    ]
    assert flags[0].ref_evidence_version_id == version


def test_tin_mismatch_forces_hold_and_a_match_does_not() -> None:
    (flag,) = code_flags(_facts(tin_last4="7713", entity_last4s=frozenset({"7731"})))
    assert (flag.kind, flag.severity) == ("tin_mismatch", "force_hold")
    assert flag.facts == {"detected_last4": "7713", "record_last4": ["7731"]}
    assert code_flags(_facts(tin_last4="2208", entity_last4s=frozenset({"2208", "1111"}))) == []


def test_unreadable_scan_or_heic_and_no_low_confidence_with_it() -> None:
    for media, text in (("image/heic", False), ("application/pdf", False)):
        kinds = [
            f.kind
            for f in code_flags(_facts(media_type=media, has_text_layer=text, confidence=0.0))
        ]
        assert kinds == ["unreadable"]


def test_low_confidence_replacement_and_corrected() -> None:
    old = uuid.uuid4()
    flags = code_flags(_facts(confidence=0.5, replacement_version_id=old, corrected=True))
    assert [(f.kind, f.severity) for f in flags] == [
        ("possible_replacement", "info"),
        ("corrected_form", "info"),
        ("low_confidence", "block_bulk"),
    ]


def test_ambiguous_candidates_within_five_points_below_ninety() -> None:
    assert ambiguous([61, 58]) == (61, 58)
    assert ambiguous([92, 89]) is None  # the top is sure enough
    assert ambiguous([80, 70]) is None  # far enough apart
    assert ambiguous([80]) is None
    (flag,) = code_flags(_facts(candidate_scores=(58, 61)))
    assert (flag.kind, flag.severity, flag.facts) == (
        "ambiguous_candidates",
        "block_bulk",
        {"top": 61, "second": 58},
    )
