"""T-07-T11 (TASK-8038; ADR-343; SPEC-656 AC-1.4, AC-6.2): the `instrument_clause` citable.

Acceptance (the task row): "A fabricated clause id, a changed quote or a superseded instrument is
refused or marked moved, and a verified clause citation displays 'Art. III(a)' with its passage
regions." The word layer's own verifier (`document_text`) is replaced by a recorder here, so the
clause logic is tested alone; the database path runs in the end pass's integration suite.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from abacus.modules.evidence.api import CitationAnchor, CitationClaim, CitationVerdict
from abacus.modules.evidence.citations.registry import KINDS, SOURCES
from abacus.modules.tax import instrument_citations as ic

type _Fake = Any  # Any: test doubles for the session, unit of work and actor
type _Regions = list[dict[str, Any]]  # Any: stored jsonb regions

INSTRUMENT, SEGMENTATION, CLAUSE, VERSION = (uuid.uuid4() for _ in range(4))
ANCHOR = CitationAnchor("instrument_determination", uuid.uuid4(), engagement_id=uuid.uuid4())
REGIONS = [{"page": 3, "bbox": [72, 400, 540, 720]}, {"page": 4, "bbox": [72, 72, 540, 210]}]


@dataclass
class _Row:
    id: uuid.UUID = CLAUSE
    segmentation_id: uuid.UUID = SEGMENTATION
    instrument_id: uuid.UUID = INSTRUMENT
    label: str = "Art. III(a)"
    heading: str | None = None
    page_from: int = 3
    page_to: int = 4
    regions: _Regions = field(default_factory=lambda: list(REGIONS))
    evidence_version_id: uuid.UUID = VERSION


class _Result:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def first(self) -> object | None:
        return self._row


class _Session:
    def __init__(self, clause: _Row | None, segmentation: _Row | None) -> None:
        self.clause, self.segmentation = clause, segmentation

    async def execute(self, statement: Any, params: dict[str, Any]) -> _Result:  # noqa: ANN401
        sql = str(statement)
        if "FROM instrument_segmentations s WHERE" in sql:
            return _Result(self.segmentation)
        return _Result(self.clause)


class _Tx:
    def __init__(self, session: _Session) -> None:
        self.session = session


def _claim(quote: str | None = "distribute the net income", **locator: object) -> CitationClaim:
    base: dict[str, object] = {
        "instrument_id": str(INSTRUMENT),
        "segmentation_id": str(SEGMENTATION),
        "clause_id": str(CLAUSE),
    }
    return CitationClaim(ic.KIND, {**base, **locator}, quote=quote)


@pytest.fixture
def pages(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    """The word layer: the quote is on page 4 inside the clause's second region."""
    seen: list[tuple[int, str]] = []

    async def verify(
        tx: object, actor: object, claim: CitationClaim, anchor: object
    ) -> CitationVerdict:
        page = cast(int, claim.locator["page"])
        seen.append((page, str(claim.locator["evidence_version_id"])))
        if claim.quote == "distribute the net income" and page == 4:
            return CitationVerdict(None, "evidence_version", VERSION, quote_sha256=b"h" * 32)
        if claim.quote == "elsewhere on the page":
            return CitationVerdict("bbox_mismatch", "evidence_version", VERSION)
        return CitationVerdict("quote_not_found", "evidence_version", VERSION)

    monkeypatch.setattr(ic, "verify_document_citation", verify)
    return seen


async def _verify(
    claim: CitationClaim, clause: _Row | None = None, seg: _Row | None = None
) -> CitationVerdict:
    session = _Session(
        clause if clause is not None else _Row(), seg if seg is not None else _Row()
    )
    return await ic.verify_instrument_clause(
        cast(_Fake, _Tx(session)),
        cast(_Fake, None),
        claim,
        ANCHOR,
    )


def test_adr343_the_eleventh_kind_is_registered_with_its_source() -> None:
    assert "instrument_clause" in KINDS and len(KINDS) == 11
    assert SOURCES["instrument_clause"] == ("instrument_segmentation", "segmentation_id")


async def test_a_quote_inside_the_clause_regions_verifies_with_its_match_id(
    pages: list[tuple[int, str]],
) -> None:
    verdict = await _verify(_claim())
    assert verdict.verified
    assert verdict.match_id == f"ic:{SEGMENTATION}#{CLAUSE}"
    assert verdict.quote_sha256 == b"h" * 32
    assert [p for p, _ in pages] == [3, 4]  # every region in order, on the instrument's version
    assert {v for _, v in pages} == {str(VERSION)}
    assert "quote" not in verdict.locator  # the quote is never stored


async def test_a_fabricated_clause_id_is_source_not_found(pages: list[tuple[int, str]]) -> None:
    session = _Session(None, _Row())
    verdict = await ic.verify_instrument_clause(
        cast(_Fake, _Tx(session)),
        cast(_Fake, None),
        _claim(),
        ANCHOR,
    )
    assert verdict.reason == "source_not_found" and pages == []


async def test_a_clause_of_another_segmentation_is_locator_invalid(
    pages: list[tuple[int, str]],
) -> None:
    other = _Row(segmentation_id=uuid.uuid4())
    assert (await _verify(_claim(), clause=other)).reason == "locator_invalid"
    stranger = _Row(instrument_id=uuid.uuid4())
    assert (await _verify(_claim(), seg=stranger)).reason == "locator_invalid"


async def test_a_changed_quote_is_refused(pages: list[tuple[int, str]]) -> None:
    assert (await _verify(_claim("distribute all of the income"))).reason == "quote_not_found"
    assert (await _verify(_claim("elsewhere on the page"))).reason == "bbox_mismatch"
    assert (await _verify(_claim(None))).reason == "locator_invalid"


async def test_a_malformed_locator_or_regions_never_verify(pages: list[tuple[int, str]]) -> None:
    bad = CitationClaim(ic.KIND, {"clause_id": "not-a-uuid"}, quote="x")
    assert (await _verify(bad)).reason == "locator_invalid"
    assert (
        await _verify(_claim(), clause=_Row(regions=[{"page": "3"}]))
    ).reason == "locator_invalid"


async def test_display_reads_art_iii_a_and_its_pages() -> None:
    session = _Session(_Row(), _Row())
    label = await ic.display_instrument_clause(
        cast(_Fake, session), _claim().locator, uuid.uuid4()
    )
    assert (label.title, label.loc) == ("Art. III(a)", "Trust agreement · pages 3–4")  # noqa: RUF001
    withheld = await ic.display_instrument_clause(cast(_Fake, session), _claim().locator, None)
    assert withheld.title == "Trust agreement" and withheld.loc == ""
