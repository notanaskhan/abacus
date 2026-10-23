"""F-04-T25 (F-04.26; ADR-066, ADR-050): the E0 scenario documents have fixed citation regions,
their figures are blueprint §9.4's and foot, and the recorded fake-model responses cite only those
regions and verify by code, except the one planted unsupported value, which is "Uncited"."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest
from pydantic import BaseModel

from abacus.ai_gateway import FakeModel, ModelRequest
from abacus.modules.agents.citations import verify as verify_cells
from abacus.modules.agents.document_citations import normalised
from abacus.modules.agents.document_citations import verify as verify_pages
from abacus.modules.agents.handoff import (
    Citation,
    DocumentCitation,
    MatchOutput,
    ScreeningOutput,
    UploadReviewOutput,
)
from abacus_tools.quality import seed_contamination
from abacus_tools.synthetic.scenarios.brightwater_hale import documents as docs
from abacus_tools.synthetic.scenarios.brightwater_hale import responses
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import PBC_LISTS

SCHEMAS: dict[str, type[BaseModel]] = {
    "evidence.screen@v0": ScreeningOutput,
    "evidence.upload_review@v3": UploadReviewOutput,
    "evidence.inbox_match@v2": MatchOutput,
}
FILES = sorted(responses.DIRECTORY.glob("*.json"))


def _raw(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def _amount(text: str) -> Decimal:
    return Decimal(text.strip("()").replace(",", "")) * (-1 if text.startswith("(") else 1)


def _document(path: Path) -> docs.ScenarioDocument:
    found = docs.by_sha256(str(_raw(path)["content_sha256"]))
    assert found is not None, f"{path.name}: keyed to no scenario document"
    return found


# --- the documents ------------------------------------------------------------------------------


def test_t25_the_documents_are_deterministic() -> None:
    first = [(d.key, d.sha256) for d in docs.documents()]
    docs.documents.cache_clear()
    assert [(d.key, d.sha256) for d in docs.documents()] == first
    assert len({sha for _, sha in first}) == 3


def test_t25_every_region_reads_back_from_the_bytes() -> None:
    for document in docs.documents():
        for region in document.regions:
            assert docs.region_text(document, region) == region.text, (document.key, region.id)


def test_t25_page_regions_are_fixed_rectangles_that_never_overlap() -> None:
    for document in docs.documents():
        boxes = [r.bbox for r in document.regions if isinstance(r, docs.PageRegion)]
        for i, (x0, top, x1, bottom) in enumerate(boxes):
            assert 0 <= x0 < x1 <= 612 and 0 <= top < bottom <= docs.PAGE_HEIGHT
            for ox0, otop, ox1, obottom in boxes[i + 1 :]:
                assert x1 <= ox0 or ox1 <= x0 or bottom <= otop or obottom <= top


def test_t25_each_document_answers_a_request_on_the_northwind_pbc_list() -> None:
    northwind = next(p for p in PBC_LISTS if p.key == "northwind")
    titles = {r.title for r in northwind.requests}
    for document in docs.documents():
        assert document.engagement == "A1"
        assert document.request is None or document.request in titles


def test_t25_the_net_trust_assets_foot_on_the_trust_basis() -> None:
    d = docs.documents()[0]

    def value(row: str, column: str = "first") -> Decimal:
        return _amount(d.region(f"{row}.{column}").text)

    for column in ("first", "second"):
        funds = ("krs-500", "krs-2035", "krs-2045", "krs-bond", "krs-intl", "stable-value")
        assert sum(value(f, column) for f in funds) == value("mutual-funds", column)
        assert value("mutual-funds", column) + value("brokerage", column) == value(
            "investments", column
        )
        assert value("investments", column) + value("loans", column) == value("net-assets", column)
    # Blueprint §9.4: unadjusted 16,812,400 (planning excludes the 48,600 receivable); 14,228,500.
    assert value("net-assets") == Decimal("16812400")
    assert value("net-assets", "second") == Decimal("14228500")


def test_t25_the_loan_rollforward_foots() -> None:
    d = docs.documents()[1]
    rows = ("beginning", "new", "repayments", "offsets")
    assert sum(_amount(d.region(f"{r}.second").text) for r in rows) == Decimal("312400")
    assert _amount(d.region("ending.second").text) == Decimal("312400")
    counts = [int(d.region(f"{r}.first").text) for r in (*rows, "ending")]
    assert counts[0] + counts[1] - counts[2] - counts[3] == counts[4] == 36


def test_t25_the_trial_balance_balances_and_ties_to_the_trust_report() -> None:
    tb, trust = docs.documents()[2], docs.documents()[0]
    amounts = [r for r in tb.regions if r.id.endswith(".amount")]
    debit = sum(
        _amount(r.text) for r in amounts if isinstance(r, docs.CellRegion) and r.cell[0] == "C"
    )
    credit = sum(
        _amount(r.text) for r in amounts if isinstance(r, docs.CellRegion) and r.cell[0] == "D"
    )
    assert debit == credit == _amount(tb.region("total.debit").text) == Decimal("17663450")
    assets = ("1110", "1120", "1130", "1140", "1150", "1160", "1200", "1300")
    assert sum(_amount(tb.region(f"{a}.amount").text) for a in assets) == _amount(
        trust.region("net-assets.first").text
    )


# --- the recorded responses ---------------------------------------------------------------------


def test_t25_every_response_is_keyed_to_a_document_and_parses_as_its_schema() -> None:
    assert len(FILES) == 5
    for path in FILES:
        raw = _raw(path)
        document = _document(path)
        assert raw["document"] == document.key
        SCHEMAS[str(raw["prompt_ref"])].model_validate(raw["response"])
    assert len(responses.load()) == len(FILES)


def _screen_citations(path: Path) -> list[Citation]:
    return ScreeningOutput.model_validate(_raw(path)["response"]).citations


def _page_citations(path: Path) -> list[DocumentCitation]:
    raw = _raw(path)
    if raw["prompt_ref"] == "evidence.inbox_match@v2":
        out = MatchOutput.model_validate(raw["response"])
        return [c for p in out.proposals for c in p.citations]
    review = UploadReviewOutput.model_validate(raw["response"])
    return [c for f in review.flags for c in f.citations]


def test_t25_every_citation_resolves_to_a_fixed_region_and_verifies_by_code() -> None:
    planted_file, planted_index = responses.PLANTED_UNSUPPORTED
    cited = 0
    for path in FILES:
        document = _document(path)
        if document.media_type == docs.XLSX:
            citations = _screen_citations(path)
            checked = verify_cells(document.content, citations)
            for n, (citation, result) in enumerate(zip(citations, checked, strict=True)):
                region = next(
                    r
                    for r in document.regions
                    if isinstance(r, docs.CellRegion) and r.cell == citation.cell
                )
                if (path.name, n) == (planted_file, planted_index):
                    continue
                assert result.verified, (path.name, n, result.reason)
                if citation.value is not None:
                    assert _amount(region.text) == citation.value
                cited += 1
        else:
            citations = _page_citations(path)
            pages = {1: docs.page_text(document, 1)}
            for citation, result in zip(
                citations, verify_pages(citations, pages, {}), strict=True
            ):
                assert result.verified, (path.name, citation.quote, result.reason)
                assert any(
                    isinstance(r, docs.PageRegion)
                    and r.page == citation.page
                    and normalised(citation.quote) in normalised(docs.region_text(document, r))
                    for r in document.regions
                ), (path.name, citation.quote)
                cited += 1
    assert cited >= 7


def test_t25_the_one_planted_value_is_unsupported_so_it_shows_uncited() -> None:
    planted_file, planted_index = responses.PLANTED_UNSUPPORTED
    unverified: list[tuple[str, int, str | None]] = []
    for path in FILES:
        document = _document(path)
        if document.media_type != docs.XLSX:
            continue
        checked = verify_cells(document.content, _screen_citations(path))
        unverified += [(path.name, n, c.reason) for n, c in enumerate(checked) if not c.verified]
    assert unverified == [(planted_file, planted_index, "value_mismatch")]
    planted = _screen_citations(responses.DIRECTORY / planted_file)[planted_index]
    tb = docs.documents()[2]
    assert planted.value == Decimal("1366900.00")  # accrual basis: 1,318,300 + 48,600
    assert all(_amount(r.text) != planted.value for r in tb.regions if r.id.endswith(".amount"))


async def test_t25_the_fake_model_answers_a_request_that_names_the_document() -> None:
    fake = responses.install(FakeModel())
    tb = docs.documents()[2]
    answer = await fake.complete(
        ModelRequest(
            prompt_ref="evidence.screen@v0",
            model="fake",
            system="",
            user=f"## task\n{{}}\nsource sha256 {tb.sha256}",
            max_output_tokens=100,
        )
    )
    assert json.loads(answer.text)["action"] == "ready_for_review"


def test_t25_no_kit_sample_data_in_the_documents_or_responses() -> None:
    for document in docs.documents():
        for region in document.regions:
            assert not list(seed_contamination.findings_in(region.text))
    for path in FILES:
        assert not list(seed_contamination.findings_in(path.read_text()))


@pytest.mark.parametrize("document", docs.documents(), ids=lambda d: d.key)
def test_t25_documents_carry_no_real_identifier(document: docs.ScenarioDocument) -> None:
    text = " ".join(r.text for r in document.regions)
    assert "@" not in text and "SSN" not in text and "EIN" not in text
