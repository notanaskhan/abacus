"""P-11-T28 (TASK-3315; DEC-2314): the scanned corpus, from the row.

"The generator is deterministic from a seed, every golden value foots to the Brightwater Hale
figures, and test-only faces never ship in a production layout (DEC-78)."
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import yaml

from abacus.kernel.ocr import normalise
from abacus.modules.evidence.form_extraction import Extracted, extract, identify
from abacus.modules.evidence.words import PageWords, Word
from abacus_tools.synthetic.scanned_corpus import FACES, generate, recordings

GOLDEN = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "golden" / "scanned_corpus.yaml").read_text()
)
REPO = Path(__file__).resolve().parents[4]


def _layer(key: str) -> PageWords:
    page = next(p for p in generate() if p.key == key)
    words = normalise(
        json.loads(page.textract)["Blocks"], width_pt=Decimal("612"), height_pt=Decimal("792")
    )
    return PageWords(
        1, 612.0, 792.0, 0,
        tuple(Word(w.text, float(w.bbox[0]), float(w.bbox[1]), float(w.bbox[2]), float(w.bbox[3]),
                   float(w.confidence)) for w in words),
    )  # fmt: skip


def _fields(key: str) -> dict[str, Extracted]:
    layer = _layer(key)
    form = identify([layer])
    assert form is not None
    return {f.field_key: f for f in extract(form, [layer])}


def test_ac_deterministic_from_a_seed() -> None:
    one, two = generate(7), generate(7)
    assert [p.sha256 for p in one] == [p.sha256 for p in two]
    assert [p.textract for p in one] == [p.textract for p in two]
    assert [p.sha256 for p in one] != [p.sha256 for p in generate(8)]


def test_ac_every_face_has_a_recording_key() -> None:
    pages = generate()
    assert len(recordings(pages)) == len(FACES)
    assert {p.key for p in pages} >= {
        "whitley_cp2000", "santos_cp14", "feld_w2", "feld_1095c", "iyer_1099div_corrected",
        "ridgeline_k1", "front_range_statement", "calloway_instrument",
    }  # fmt: skip


def test_ac_the_whitley_golden_foots_and_reads_through_the_map() -> None:
    gold = GOLDEN["whitley_cp2000"]
    assert Decimal(gold["proposed_tax"]) + Decimal(gold["interest"]) == Decimal(gold["amount_due"])
    payers = sum(Decimal(v) for v in gold["payers"].values())
    assert payers == Decimal(gold["changes_reported"]) - Decimal(gold["changes_shown"])
    fields = _fields("whitley_cp2000")
    assert fields["notice.amount_due"].value_text == gold["amount_due"]
    assert fields["notice.respond_by"].value_text == gold["respond_by"]
    assert fields["notice.changes.interest.reported"].value_text == gold["changes_reported"]
    assert fields["notice.payers.front_range_bank.amount"].value_text == "1870.00"


def test_ac_the_santos_golden_and_its_partly_obscured_date() -> None:
    gold = GOLDEN["santos_cp14"]
    charges = sum(Decimal(v) for v in gold["charges"].values())
    assert charges == Decimal(gold["amount_due"])
    fields = _fields("santos_cp14")
    assert fields["notice.respond_by"].low_confidence
    assert fields["notice.charges.tax.amount"].value_text == gold["charges"]["tax"]


def test_ac_the_corpus_never_reaches_production_code() -> None:
    source = REPO / "backend" / "src" / "abacus"
    assert not [p for p in source.rglob("*.py") if "scanned_corpus" in p.read_text()]
