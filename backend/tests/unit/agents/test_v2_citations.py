"""P-03-T10 (DEC-267): the agents' citations as v2 claims, by code: the screener's cells, the
reviewer's and matcher's page and cell quotes, on a version or an inbox file."""

from __future__ import annotations

import uuid
from decimal import Decimal

from abacus.modules.agents.handoff import Citation, DocumentCitation
from abacus.modules.agents.v2_citations import cell_claims, document_claims


def test_the_screeners_cells_carry_their_quote_and_value() -> None:
    version = uuid.uuid4()
    [claim] = cell_claims(version, [Citation(cell="C9", quote="Total", value=Decimal("16500000"))])
    assert claim.kind == "sheet_cell"
    assert dict(claim.locator) == {"evidence_version_id": str(version), "cell": "C9"}
    assert (claim.quote, claim.value) == ("Total", "16500000")


def test_pages_are_document_text_and_cells_sheet_cell() -> None:
    version = uuid.uuid4()
    page, cell = document_claims(
        [
            DocumentCitation(page=3, quote="Net assets"),
            DocumentCitation(sheet="TB", cell="B2", quote="1,650.00"),
        ],
        evidence_version_id=version,
    )
    assert (page.kind, dict(page.locator)) == (
        "document_text",
        {"evidence_version_id": str(version), "page": 3},
    )
    assert (cell.kind, dict(cell.locator)) == (
        "sheet_cell",
        {"evidence_version_id": str(version), "cell": "B2", "sheet": "TB"},
    )


def test_the_matcher_cites_the_inbox_file() -> None:
    inbox = uuid.uuid4()
    [claim] = document_claims([DocumentCitation(page=1, quote="x")], inbox_file_id=inbox)
    assert dict(claim.locator) == {"inbox_file_id": str(inbox), "page": 1}
