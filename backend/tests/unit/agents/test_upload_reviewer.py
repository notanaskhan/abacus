"""SPEC-030 AC-1, AC-2, AC-3, AC-8 (TASK-058): the reviewer's spec, its context (the document the
only untrusted, trimmable field), quote verification by code, and its evaluation's metrics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from abacus.modules.agents.api import REVIEWER, spec
from abacus.modules.agents.document_citations import (
    column_letters,
    normalised,
    sheet_lines,
    verify,
)
from abacus.modules.agents.handoff import DocumentCitation, UploadReviewOutput
from abacus.modules.agents.upload_review import build_context, document_blocks
from abacus.modules.evidence.api import ReviewMaterial
from abacus_tools.evals.upload_review import (
    DOCUMENTS,
    REQUESTS,
    ReviewCase,
    Seen,
    _documents,  # pyright: ignore[reportPrivateUsage] -- the suite's own fixtures
    load_suite,
    validate,
    verdict,
)

PAGES = {1: "DRAFT\nFirst Example Bank\nEnding balance $12,124.50", 2: "Account summary"}
SHEETS = {"AR Aging": (("Customer", "Total"), ("Acme", "175.00"))}


def _material(**changes: object) -> ReviewMaterial:
    values: dict[str, object] = {
        "engagement_id": __import__("uuid").uuid4(),
        "extraction_status": "extracted",
        "document_kind": "bank_statement",
        "item_description": "Bank statement for December",
        "checks": (("wrong_period", "passed", None),),
        "excerpt_pages": ((1, PAGES[1]),),
        "excerpt_tables": (("AR Aging", SHEETS["AR Aging"]),),
        "truncated": False,
        "pages": PAGES,
        "sheets": SHEETS,
    }
    values.update(changes)
    return ReviewMaterial(**values)  # pyright: ignore[reportArgumentType] -- test values


def test_ac1_the_reviewer_is_declared_to_propose_only() -> None:
    reviewer = spec(REVIEWER)
    assert reviewer.autonomy == "propose"
    assert reviewer.prompt == "evidence.upload_review@v3"  # TASK-067: cell references
    assert reviewer.task_scope == frozenset({"evidence.read", "upload_review.run"})
    assert reviewer.limits.max_cost_usd == Decimal("0.02")
    assert reviewer.untrusted_inputs == ("document",) or list(reviewer.untrusted_inputs) == [
        "document"
    ]
    assert reviewer.essential is False


def test_ac2_the_document_is_the_only_untrusted_field_and_comes_last() -> None:
    context = build_context(_material(), "2026-12-31", "Example Company Inc", ["document"])
    rendered = context.render()
    assert rendered.count('<untrusted name="document">') == 1
    before = rendered.split('<untrusted name="document">', 1)[0]
    assert "First Example Bank" not in before
    assert "Bank statement for December" in before
    assert "Year end 2026-12-31" in rendered


def test_ac2_pages_and_sheets_become_ordered_blocks() -> None:
    blocks = document_blocks(_material())
    assert blocks[0].startswith("Page 1:\nDRAFT")
    # TASK-067: each cell with its reference, so a citation names a cell the model was shown.
    assert blocks[1] == "Sheet AR Aging:\nA1: Customer | B1: Total\nA2: Acme | B2: 175.00"


def test_ac3_a_quote_on_its_page_is_verified_and_a_made_up_one_is_not() -> None:
    found = verify(
        [
            DocumentCitation(page=1, quote="draft"),
            DocumentCitation(page=1, quote="Ending   balance $12,124.50"),
            DocumentCitation(page=2, quote="DRAFT"),
            DocumentCitation(page=9, quote="anything"),
        ],
        PAGES,
        SHEETS,
    )
    assert [(c.verified, c.reason) for c in found] == [
        (True, None),
        (True, None),
        (False, "quote_not_found"),
        (False, "page_not_found"),
    ]


def test_ac3_a_quote_joining_lines_of_one_page_needs_every_line_there() -> None:
    joined = "First Example Bank\nEnding balance $12,124.50"
    invented = "First Example Bank\nEnding balance $99.00"
    found = verify(
        [DocumentCitation(page=1, quote=joined), DocumentCitation(page=1, quote=invented)],
        PAGES,
        SHEETS,
    )
    assert [c.verified for c in found] == [True, False]


def test_ac3_a_cell_quote_is_checked_against_that_cell() -> None:
    found = verify(
        [
            DocumentCitation(sheet="AR Aging", cell="B2", quote="175.00"),
            DocumentCitation(sheet="AR Aging", cell="B2", quote="176.00"),
            DocumentCitation(sheet="AR Aging", cell="Z99", quote="x"),
        ],
        PAGES,
        SHEETS,
    )
    assert [c.reason for c in found] == [None, "quote_not_found", "cell_not_found"]


def test_ac3_zero_width_characters_and_compatibility_forms_are_normalised() -> None:
    assert normalised("D​R​A​F​T  copy") == "draft copy"
    assert normalised("\uff24\uff32\uff21\uff26\uff34") == "draft"  # full-width letters
    assert normalised("D\u00adR\u00adA\u00adF\u00adT") == "draft"  # soft hyphens


def test_ac3_a_citation_names_a_page_or_a_cell_and_the_output_is_bounded() -> None:
    with pytest.raises(ValidationError):
        DocumentCitation(quote="x")
    with pytest.raises(ValidationError):
        DocumentCitation(page=1, cell="A1", quote="x")
    flag = {
        "category": "draft",
        "confidence": 0.9,
        "rationale": "Marked draft.",
        "citations": [{"page": 1, "quote": "DRAFT"}],
    }
    with pytest.raises(ValidationError):
        UploadReviewOutput.model_validate({"no_concerns": False, "flags": [flag] * 6})
    with pytest.raises(ValidationError):
        UploadReviewOutput.model_validate(
            {"no_concerns": False, "flags": [{**flag, "category": "approved"}]}
        )


def test_ac8_the_suite_validates_and_every_case_has_its_document_and_request() -> None:
    suite = load_suite()
    validate(suite)
    assert {c.document for c in suite.cases} <= DOCUMENTS
    assert {c.request for c in suite.cases} <= set(REQUESTS)
    for name, make in _documents(date(2025, 12, 31)).items():
        file_name, content = make()
        assert content, name
        assert file_name.endswith((".pdf", ".xlsx"))


def test_ac8_metrics_score_recall_precision_citations_and_containment() -> None:
    suite = load_suite()
    draft = ReviewCase(
        id="d", document="draft_watermark", request="bank_statement", expected=frozenset({"draft"})
    )
    clean = ReviewCase(
        id="c", document="clean_statement", request="bank_statement", expected=frozenset()
    )
    injected = ReviewCase(
        id="i",
        document="draft_with_injection",
        request="bank_statement",
        expected=frozenset({"draft"}),
        categories=frozenset({"draft", "prompt_injection"}),
    )
    attempts = [
        (draft, Seen("d", 1, "reviewed", shown=frozenset({"draft"}), contained=True)),
        (clean, Seen("c", 1, "reviewed", shown=frozenset({"draft"}), contained=True)),
        (injected, Seen("i", 1, "reviewed", shown=frozenset(), contained=True)),
    ]
    _, _, metrics = verdict(suite, attempts)
    assert metrics["flag_recall_draft"] == pytest.approx(0.5)
    assert metrics["flag_precision_draft"] == pytest.approx(0.5)
    assert metrics["adversarial_containment"] == 0.0  # the injection suppressed the flag
    assert metrics["flag_precision_altered"] == 1.0  # nothing flagged: no false flags


def test_ac6_the_firm_sees_only_verified_quotes() -> None:
    from abacus.modules.agents.review_start import (
        _quotes,  # pyright: ignore[reportPrivateUsage] -- the read model's own filter
    )

    found = _quotes(
        [
            {"page": 1, "sheet": None, "cell": None, "quote": "DRAFT", "verified": True},
            {"page": 1, "sheet": None, "cell": None, "quote": "made up", "verified": False},
        ]
    )
    assert [q.quote for q in found] == ["DRAFT"]


def test_ac3_a_cell_shown_in_the_excerpt_verifies_by_its_reference() -> None:
    rows = (("Payroll register",), (), ("Employee", "", "Net pay"), ("A. Rivera", "", "4022.2"))
    assert sheet_lines(rows) == [
        "A1: Payroll register",
        "A3: Employee | C3: Net pay",
        "A4: A. Rivera | C4: 4022.2",
    ]
    cited = DocumentCitation(sheet="Payroll", cell="C3", quote="Net pay")
    (checked,) = verify([cited], {}, {"Payroll": rows})
    assert checked.verified
    assert column_letters(0) == "A" and column_letters(25) == "Z" and column_letters(26) == "AA"
