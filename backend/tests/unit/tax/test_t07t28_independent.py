"""T-07-T28 (TASK-8360; ADR-078): independent tests for N's T-07-T11, T-07-T13 and T-07-T19,
written in AY's session from the row and SPEC-656, not from the implementing sessions' tests.
ac-test-author: ayushkbhatia

- Clause verifier (T11): a fabricated clause is `source_not_found`; a real clause cited under
  another instrument (moved, or forged across instruments) is `locator_invalid`, and the word
  layer is never asked; a quote outside the clause's regions never verifies; a superseding
  instrument moves every clause citation of each old segmentation.
- Instrument reader (T13): without a §7216 consent in force the run is refused before any tool
  or model call; the model's output has no action field; code drops an uncited governed reading
  and a figure that is no named fact's amount; the only write the reader makes is a proposal.
- CCH 1041 (T19): the reconciliation compares only keys both sides hold, plus engine-only 1041
  keys; one `engine_diagnostic` issue per difference, none for agreement; neither module imports
  a network client (the never-ERO suite holds the rest).
"""

from __future__ import annotations

import ast
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from abacus.modules.evidence.api import CitationAnchor, CitationClaim, CitationVerdict
from abacus.modules.tax import export_fiduciary as xf
from abacus.modules.tax import instrument_citations as ic
from abacus.modules.tax import instrument_reader as reader

type _Fake = Any  # Any: test doubles for the unit of work and the agent context

SRC = Path(__file__).resolve().parents[3] / "src" / "abacus" / "modules" / "tax"

# --- the clause verifier ------------------------------------------------------------------------

INSTRUMENT, OTHER_INSTRUMENT = uuid.uuid4(), uuid.uuid4()
SEG, CLAUSE, VERSION = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
ANCHOR = CitationAnchor("instrument_determination", uuid.uuid4(), engagement_id=uuid.uuid4())


class _Row:
    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class _Result:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def first(self) -> object | None:
        return self._row


class _Db:
    """The two reads the verifier makes: the segmentation and the clause."""

    def __init__(self, seg: _Row | None, clause: _Row | None) -> None:
        self.seg, self.clause = seg, clause

    async def execute(self, statement: object, _params: object) -> _Result:
        if "FROM instrument_segmentations s WHERE" in str(statement):
            return _Result(self.seg)
        return _Result(self.clause)


def _tx(seg: _Row | None, clause: _Row | None) -> _Fake:
    return cast(_Fake, type("Tx", (), {"session": _Db(seg, clause)})())


def _seg(instrument: uuid.UUID = INSTRUMENT) -> _Row:
    return _Row(id=SEG, instrument_id=instrument)


def _clause(**over: object) -> _Row:
    base: dict[str, object] = {
        "id": CLAUSE,
        "segmentation_id": SEG,
        "label": "Art. IV(b)",
        "heading": None,
        "page_from": 2,
        "page_to": 2,
        "regions": [{"page": 2, "bbox": [72, 300, 540, 420]}],
        "instrument_id": INSTRUMENT,
        "evidence_version_id": VERSION,
    }
    return _Row(**{**base, **over})


def _claim(clause: uuid.UUID = CLAUSE, instrument: uuid.UUID = INSTRUMENT) -> CitationClaim:
    return CitationClaim(
        ic.KIND,
        {"instrument_id": str(instrument), "segmentation_id": str(SEG), "clause_id": str(clause)},
        quote="income shall be paid to the beneficiaries",
    )


@pytest.fixture
def words(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """The word layer: the quote is found only at its true place (page 2, the region)."""
    asked: list[object] = []

    async def verify(
        _tx: object, _a: object, claim: CitationClaim, _an: object
    ) -> CitationVerdict:
        asked.append(claim.locator)
        if claim.locator.get("page") == 2 and claim.locator.get("bbox") == [72, 300, 540, 420]:
            return CitationVerdict(None, "evidence_version", VERSION, quote_sha256=b"q" * 32)
        return CitationVerdict("bbox_mismatch", "evidence_version", VERSION)

    monkeypatch.setattr(ic, "verify_document_citation", verify)
    return asked


async def test_a_fabricated_clause_is_source_not_found(words: list[object]) -> None:
    verdict = await ic.verify_instrument_clause(
        _tx(_seg(), None), cast(_Fake, None), _claim(clause=uuid.uuid4()), ANCHOR
    )
    assert (verdict.verified, verdict.reason) == (False, "source_not_found")
    assert words == []  # nothing is read for a clause that does not exist


async def test_a_clause_cited_under_another_instrument_never_verifies(words: list[object]) -> None:
    moved = await ic.verify_instrument_clause(
        _tx(_seg(), _clause()), cast(_Fake, None), _claim(instrument=OTHER_INSTRUMENT), ANCHOR
    )
    assert (moved.verified, moved.reason) == (False, "locator_invalid")
    forged = await ic.verify_instrument_clause(
        _tx(_seg(), _clause(segmentation_id=uuid.uuid4())), cast(_Fake, None), _claim(), ANCHOR
    )
    assert (forged.verified, forged.reason) == (False, "locator_invalid")
    assert words == []


async def test_a_quote_outside_the_clause_regions_never_verifies(words: list[object]) -> None:
    elsewhere = _clause(regions=[{"page": 5, "bbox": [72, 72, 540, 200]}])
    verdict = await ic.verify_instrument_clause(
        _tx(_seg(), elsewhere), cast(_Fake, None), _claim(), ANCHOR
    )
    assert (verdict.verified, verdict.reason) == (False, "bbox_mismatch")
    verified = await ic.verify_instrument_clause(
        _tx(_seg(), _clause()), cast(_Fake, None), _claim(), ANCHOR
    )
    assert verified.verified and verified.match_id == ic.match_id(SEG, CLAUSE)


async def test_a_superseding_instrument_moves_every_old_segmentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_segs = [uuid.uuid4(), uuid.uuid4()]
    moved: list[tuple[str, str]] = []

    async def supersede(_tx: object, **kw: object) -> int:
        moved.append((str(kw["old"]), str(kw["new"])))
        return 2

    class _Scalars:
        async def scalars(self, _s: object, _p: object) -> list[uuid.UUID]:
            return old_segs

    monkeypatch.setattr(ic, "mark_sources_superseded", supersede)
    new = uuid.uuid4()
    tx = cast(_Fake, type("Tx", (), {"session": _Scalars()})())
    assert await ic.move_clause_citations(tx, INSTRUMENT, new) == 4
    assert moved == [(str(s), f"instrument:{new}") for s in old_segs]


# --- the instrument reader ----------------------------------------------------------------------


async def test_the_reader_refuses_without_consent_before_any_tool_or_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    async def no_consent(*_: object) -> bool:
        return False

    async def tool(*a: object) -> object:
        called.append(f"tool:{a[2]}")
        return {}

    async def judge(*_: object) -> None:
        called.append("model")

    monkeypatch.setattr(reader, "_consents", no_consent)
    monkeypatch.setattr(reader, "_tool", tool)
    monkeypatch.setattr(reader, "_judge", judge)
    result = await reader.read_instrument(cast(_Fake, object()), uuid.uuid4(), 2025)
    assert (result.outcome, result.code, result.proposal_id) == (
        "refused",
        "consent_required",
        None,
    )
    assert called == []


def test_the_models_output_can_only_become_a_proposal() -> None:
    assert set(reader.ReadInstrumentOutput.model_fields) == {"determinations"}
    assert set(reader.DeterminationAnswer.model_fields) == {
        "key",
        "value_code",
        "value_text",
        "clause_id",
        "quote",
        "fact_ids",
    }


def test_code_drops_an_uncited_governed_reading_and_an_invented_figure() -> None:
    given = reader.ReadInstrumentInput(
        clauses=[
            reader.InstrumentClause(
                id="c1", label="Art. IV", text="The trustee shall pay all income."
            )
        ],
        facts=[reader.TrustFact(id="f1", label="Distributions", amount="12,000.00")],
    )
    answer = reader.ReadInstrumentOutput(
        determinations=[
            # cites a quote the clause does not hold
            reader.DeterminationAnswer(
                key="trust_type", value_code="simple", value_text="Simple trust",
                clause_id="c1", quote="income may be accumulated",
            ),
            # a figure no named fact holds
            reader.DeterminationAnswer(
                key="note", value_code="x", value_text="Paid $13,500.00", fact_ids=["f1"]
            ),
            reader.DeterminationAnswer(
                key="trust_type", value_code="simple", value_text="Simple trust",
                clause_id="c1", quote="shall pay all income",
            ),
        ]
    )  # fmt: skip
    settled = reader.settle(answer, given)
    assert [d.key for d in settled.kept] == ["trust_type"]
    assert (settled.dropped_uncited, settled.dropped_numbers) == (1, 1)


async def test_the_readers_only_write_is_a_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    names: list[str] = []

    async def yes(*_: object) -> bool:
        return True

    async def tool(_a: object, _s: int, name: str, _args: object) -> object:
        names.append(name)
        if name == reader.READ_CLAUSES:
            return {"clauses": [{"id": "c1", "label": "Art. IV", "text": "pay all income"}]}
        if name == reader.READ_FACTS:
            return {"distributions": [], "expenses": []}
        return {"proposal_id": str(uuid.uuid4())}

    async def judge(*_: object) -> reader.ReadInstrumentOutput:
        return reader.ReadInstrumentOutput(
            determinations=[
                reader.DeterminationAnswer(
                    key="trust_type", value_code="simple", value_text="Simple trust",
                    clause_id="c1", quote="pay all income",
                )
            ]
        )  # fmt: skip

    monkeypatch.setattr(reader, "_consents", yes)
    monkeypatch.setattr(reader, "_tool", tool)
    monkeypatch.setattr(reader, "_judge", judge)
    result = await reader.read_instrument(cast(_Fake, object()), uuid.uuid4(), 2025)
    assert result.outcome == "proposed"
    assert names == [reader.READ_CLAUSES, reader.READ_FACTS, reader.PROPOSE]


# --- the CCH 1041 reconciliation ----------------------------------------------------------------

SECTION = xf.FiduciarySection(
    fields=(
        xf.FieldRow("f1041.line_1", "Interest income", "4200.00"),
        xf.FieldRow("f1041.line_18", "Income distribution deduction", "12000.00"),
    ),
    k1=(xf.K1Row("b1", "Nora", "1", Decimal("2100.00")),),
)


def test_reconciliation_flags_only_real_differences() -> None:
    engine: dict[str, dict[str, object]] = {
        "f1041.line_1": {"v": "4200.00"},  # agrees
        "f1041.line_18": {"v": "11800.00"},  # differs
        "k1_1041.b1.box_1": {"v": "2100"},  # agrees (scale differs only)
        "sch_b.line_9": {"v": "300"},  # the engine's only: a difference
        "other.key": {"v": "1"},  # not a 1041 key: never compared
    }
    rows = {r.key: r for r in xf.compare(SECTION, engine)}
    assert {k for k, r in rows.items() if r.differs} == {"f1041.line_18", "sch_b.line_9"}
    assert "other.key" not in rows


def test_reconciliation_ignores_a_key_the_engine_does_not_hold() -> None:
    rows = xf.compare(SECTION, {})
    assert rows == []


async def test_one_engine_issue_per_difference(monkeypatch: pytest.MonkeyPatch) -> None:
    raised: list[str] = []

    async def recon(_t: object, _r: object) -> list[xf.ReconRow]:
        return [
            xf.ReconRow(
                "f1041.line_18", "Income distribution deduction", Decimal(12000), Decimal(11800)
            ),
            xf.ReconRow("f1041.line_1", "Interest income", Decimal(4200), Decimal(4200)),
        ]

    async def issue(_ctx: object, **kw: object) -> None:
        raised.append(str(kw["source_ref"]))

    monkeypatch.setattr(xf, "reconcile", recon)
    monkeypatch.setattr(xf, "record_engine_issue", issue)
    ctx = cast(_Fake, type("Ctx", (), {"tenant": object()})())
    assert await xf.raise_differences(ctx, uuid.uuid4()) == 1
    assert raised == ["recon:f1041.line_18"]


@pytest.mark.parametrize("module", ["export_fiduciary.py", "engine_import.py"])
def test_the_1041_bridge_imports_no_network_client(module: str) -> None:
    banned = {"httpx", "requests", "aiohttp", "urllib.request", "socket", "smtplib", "ftplib"}
    tree = ast.parse((SRC / module).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not {m for m in imported if m in banned or m.split(".")[0] in banned}
