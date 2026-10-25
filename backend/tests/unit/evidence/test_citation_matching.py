"""P-03-T06 (SPEC-322 AC-1 to AC-3; ADR-166 §§2-4; DEC-218, DEC-219): the rules citation
verifiers apply, by code, on the word layer and the extraction, and the match ids they derive."""

from __future__ import annotations

import hashlib
import re
import uuid
from decimal import Decimal

import pytest

from abacus.modules.evidence.citations.matching import (
    MAX_QUOTE,
    amount,
    cell_reason,
    cell_text,
    layer_sha256,
    normalised,
    page_quote_reason,
    quote_at,
    quote_span,
    verify_on_layer,
)
from abacus.modules.evidence.citations.registry import (
    NIL,
    CitationClaim,
    register_citable,
    source_of,
    unverifiable,
)
from abacus.modules.evidence.citations.verifiers import (
    document_match_id,
    sheet_match_id,
    verify_document_text,
)
from abacus.modules.evidence.words import Word

# Line 1: "Total investments 16,500,000.00" at y 84-94; line 2: "Net assets 16,812,400.00".
WORDS = (
    Word("Total", 72.0, 84.0, 94.0, 94.0),
    Word("investments", 97.0, 84.0, 150.0, 94.0),
    Word("16,500,000.00", 153.0, 84.0, 217.0, 94.0),
    Word("Net", 72.0, 184.0, 90.0, 194.0),
    Word("assets", 93.0, 184.0, 120.0, 194.0),
    Word("16,812,400.00", 123.0, 184.0, 187.0, 194.0),
)
TEXT = " ".join(w.text for w in WORDS)
LINE_ONE = (70.0, 82.0, 220.0, 96.0)
# The match id grammar migration 0120 allows.
MATCH_ID = re.compile(r"^[A-Za-z0-9._:#,!@-]{1,160}$")


def test_ac1_a_quote_resolves_to_its_words_and_their_hash() -> None:
    found = verify_on_layer(WORDS, TEXT, box=None, quote="investments 16,500,000.00", value=None)
    assert found.reason is None
    assert found.box == (97.0, 84.0, 217.0, 94.0)
    assert found.sha256 == hashlib.sha256(b"investments 16,500,000.00").digest()
    assert found.sha256 == layer_sha256(WORDS[1:3])


def test_ac1_the_hash_is_of_the_layer_not_of_the_model_text() -> None:
    sloppy = verify_on_layer(WORDS, TEXT, box=None, quote="INVESTMENTS  16,500,000.00", value=None)
    exact = verify_on_layer(WORDS, TEXT, box=None, quote="investments 16,500,000.00", value=None)
    assert sloppy.sha256 == exact.sha256


def test_ac1_a_box_holding_the_quote_tightens_to_the_quotes_words() -> None:
    found = verify_on_layer(WORDS, TEXT, box=LINE_ONE, quote="16,500,000.00", value=None)
    assert (found.reason, found.box) == (None, (153.0, 84.0, 217.0, 94.0))


def test_ac2_a_box_with_no_words_is_bbox_mismatch() -> None:
    found = verify_on_layer(WORDS, TEXT, box=(300, 300, 400, 400), quote=None, value=None)
    assert found.reason == "bbox_mismatch"


def test_ac2_a_quote_elsewhere_on_the_page_is_bbox_mismatch() -> None:
    found = verify_on_layer(WORDS, TEXT, box=LINE_ONE, quote="Net assets", value=None)
    assert found.reason == "bbox_mismatch"


def test_ac2_a_quote_not_on_the_page_is_quote_not_found() -> None:
    for box in (None, LINE_ONE):
        found = verify_on_layer(WORDS, TEXT, box=box, quote="Total liabilities", value=None)
        assert found.reason == "quote_not_found"


def test_ac2_a_value_not_printed_there_is_value_mismatch() -> None:
    assert (
        verify_on_layer(WORDS, TEXT, box=LINE_ONE, quote=None, value=Decimal("16812400")).reason
        == "value_mismatch"
    )
    found = verify_on_layer(WORDS, TEXT, box=LINE_ONE, quote=None, value=Decimal("16500000"))
    assert (found.reason, found.value_text) == (None, "16,500,000.00")


def test_review_lines_scattered_over_the_page_are_not_a_quote() -> None:
    # Security review (#2): each line is on the page, but not together in that form.
    found = verify_on_layer(
        WORDS, TEXT, box=None, quote="Net assets\nTotal investments", value=None
    )
    assert (found.reason, found.box, found.sha256) == ("quote_not_found", None, None)


def test_review_a_quote_matches_on_word_boundaries_only() -> None:
    for fabricated in ("otal investments", "investments 16,500", "16,500,000.0", "assets 16"):
        found = verify_on_layer(WORDS, TEXT, box=None, quote=fabricated, value=None)
        assert found.reason == "quote_not_found", fabricated
        assert not quote_at(fabricated, TEXT), fabricated
    assert quote_at("total investments 16,500,000.00", TEXT)


def test_review_a_claim_with_nothing_to_check_is_not_verified() -> None:
    found = verify_on_layer(WORDS, TEXT, box=None, quote=None, value=None)
    assert (found.reason, found.box) == ("locator_invalid", None)
    assert verify_on_layer((), TEXT, box=None, quote=None, value=None).reason == "locator_invalid"


def test_review_every_verified_result_carries_a_hash_a_region_or_a_value() -> None:
    claims: list[tuple[tuple[float, float, float, float] | None, str | None, Decimal | None]] = [
        (None, "Net assets", None),
        (LINE_ONE, None, None),
        (None, None, Decimal("16500000")),
        (LINE_ONE, "investments", None),
    ]
    for box, quote, value in claims:
        found = verify_on_layer(WORDS, TEXT, box=box, quote=quote, value=value)
        assert found.reason is None
        assert found.sha256 is not None or found.box is not None or found.value_text is not None


@pytest.mark.serial  # a wall-clock budget (DEC-335)
def test_review_the_span_search_is_linear_and_long_quotes_are_bounded() -> None:
    import time

    many = tuple(Word(f"w{i}", 1.0, 1.0, 2.0, 2.0) for i in range(5000))
    quote = " ".join(f"w{i}" for i in range(2500, 2700))
    started = time.perf_counter()
    span = quote_span(many, quote)
    assert span is not None and len(span) == 200
    assert quote_span(many, "w1 w3") is None
    assert time.perf_counter() - started < 1.0
    overlong = " ".join(f"w{i}" for i in range(2500, 2900))
    assert len(overlong) > MAX_QUOTE
    assert quote_span(many, overlong) is None  # never searched
    assert not quote_at(overlong, " ".join(w.text for w in many))


def test_ac3_page_text_alone_verifies_a_quote_with_no_region() -> None:
    found = verify_on_layer(
        (),
        "Total investments 16,500,000.00",
        box=None,
        quote="investments",
        value=Decimal("16500000"),
    )
    assert (found.reason, found.box, found.value_text) == (None, None, "16,500,000.00")
    # A quote matched on page text alone carries the hash of the matched text (security review).
    assert found.sha256 == hashlib.sha256(b"investments").digest()


def test_zero_width_and_case_are_normalised_away() -> None:
    assert normalised("Inve​STMENTS\n  16") == "investments 16"
    assert quote_span(WORDS, "total​ investments") == list(WORDS[:2])


def test_legacy_page_and_cell_reasons() -> None:
    assert page_quote_reason({1: TEXT}, 9, "Total") == "page_not_found"
    assert page_quote_reason({1: TEXT}, 1, "Gross") == "quote_not_found"
    assert page_quote_reason({1: TEXT}, 1, "total investments") is None
    rows = (("Account", "Balance"), ("Cash", "1,650.00"))
    assert cell_text(rows, "B2") == "1,650.00"
    assert cell_text(rows, "C9") is None
    assert cell_reason(None, None, None, None, quote_rule="lines") == "cell_not_found"
    assert (
        cell_reason("1,650.00", amount("1,650.00"), None, Decimal("1650"), quote_rule="lines")
        is None
    )
    assert (
        cell_reason("1,650.00", amount("1,650.00"), None, Decimal("1600"), quote_rule="lines")
        == "value_mismatch"
    )
    assert cell_reason("Cash", None, "cash", None, quote_rule="exact") == "quote_not_found"
    assert cell_reason("Cash", None, "cash", None, quote_rule="lines") is None


@pytest.mark.parametrize(
    ("printed", "number"),
    [
        ("1,650.00", Decimal("1650.00")),
        ("$1,650.00", Decimal("1650.00")),
        ("(1,650.00)", Decimal("-1650.00")),
        ("1,650.00-", Decimal("-1650.00")),
        ("1550", Decimal("1550")),
        ("Total", None),
        ("", None),
    ],
)
def test_amounts_as_printed(printed: str, number: Decimal | None) -> None:
    assert amount(printed) == number


def test_dec219_match_ids_follow_c4_and_fit_the_column() -> None:
    version = uuid.UUID("0f6c1a2e-3d4b-4c5d-8e9f-0a1b2c3d4e5f")
    with_box = document_match_id(version, 3, (153.0, 84.04, 217.0, 94.0))
    assert with_box == f"ev:{version}#p3:153,84,217,94"
    assert document_match_id(version, 3, None) == f"ev:{version}#p3"
    assert sheet_match_id(version, 0, "C14") == f"{version}!C14"
    assert sheet_match_id(version, 2, "C14") == f"{version}.s2!C14"
    big = document_match_id(version, 5000, (14399.95, 14399.95, 14400.0, 14400.0))
    for found in (with_box, big, sheet_match_id(version, 12, "XFD1048576")):
        assert MATCH_ID.match(found), found


def test_adr166_an_unregistered_kind_is_locator_invalid() -> None:
    step = uuid.uuid4()
    claim = CitationClaim("methodology_step", {"template_version_id": str(step), "step_key": "x"})
    assert source_of(claim) == ("methodology_template_version", step)
    verdict = unverifiable(claim)
    assert (verdict.reason, verdict.verified) == ("locator_invalid", False)
    assert source_of(CitationClaim("request_item", {"request_item_id": "nope"}))[1] == NIL


def test_adr166_a_kind_is_registered_once_and_only_the_ten() -> None:
    with pytest.raises(ValueError, match="ten kinds"):
        register_citable("annotation", verify_document_text, verify_document_text)  # type: ignore[arg-type]  # deliberately not a kind
    with pytest.raises(ValueError, match="already"):
        register_citable("document_text", verify_document_text, verify_document_text)  # type: ignore[arg-type]  # deliberately the wrong display


def test_dec218_a_cited_value_alone_lights_the_word_that_prints_it() -> None:
    found = verify_on_layer(WORDS, TEXT, box=None, quote=None, value=Decimal("16812400.00"))
    assert (found.reason, found.box, found.sha256, found.value_text) == (
        None,
        (123.0, 184.0, 187.0, 194.0),
        None,
        "16,812,400.00",
    )
