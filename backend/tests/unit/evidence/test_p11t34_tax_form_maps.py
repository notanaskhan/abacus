"""P-11-T34 (TASK-6209; P-11 F8, AC8.4, AC8.7; DEC-2809): tax form maps part 1.

Row acceptance: "Box values meet the suite thresholds on the corpus, Iyer's corrected 1099-DIV is
flagged corrected with box 1b 3,310.00, and no live-path file changes." Over the synthetic scanned
corpus (P-11-T28) on FakeOcr; the goldens are `tests/golden/scanned_corpus.yaml`.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

import yaml

from abacus.kernel.ocr import normalise
from abacus.modules.evidence import tax_form_rules as rules
from abacus.modules.evidence.form_extraction import Extracted, extract, identify, load_maps
from abacus.modules.evidence.words import PageWords, Word
from abacus_tools.synthetic.scanned_corpus import generate

ROOT: Final = Path(__file__).resolve().parents[4]
GOLDEN = cast(
    dict[str, Any], yaml.safe_load((ROOT / "backend/tests/golden/scanned_corpus.yaml").read_text())
)
FORMS: Final = (
    "w2",
    "w2c",
    "1099_int",
    "1099_div",
    "1099_r",
    "1099_nec",
    "1099_misc",
    "1099_g",
    "1098",
)


def _layer(key: str) -> PageWords:
    page = next(p for p in generate() if p.key == key)
    blocks = json.loads(page.textract).get("Blocks", [])
    words = normalise(blocks, width_pt=Decimal("612"), height_pt=Decimal("792"))
    return PageWords(
        1, 612.0, 792.0, 0,
        tuple(
            Word(w.text, float(w.bbox[0]), float(w.bbox[1]), float(w.bbox[2]), float(w.bbox[3]),
                 float(w.confidence))
            for w in words
        ),
    )  # fmt: skip


def _fields(key: str) -> tuple[str, int, dict[str, Extracted]]:
    layer = _layer(key)
    found = identify([layer])
    assert found is not None, key
    return found.form_type, found.tax_year, {f.field_key: f for f in extract(found, [layer])}


def _money(golden: str) -> str:
    return f"{Decimal(golden.replace(',', '')):.2f}"


def test_every_part_1_form_has_ty2025_ty2026_and_ty2027_maps() -> None:
    have = {(m.form_type, m.tax_year) for m in load_maps() if m.family == "tax_forms"}
    for form in FORMS:
        assert {(form, 2025), (form, 2026), (form, 2027)} <= have, form


def test_ty2026_inherits_ty2025_under_its_own_version() -> None:
    by = {(m.form_type, m.tax_year): m for m in load_maps()}
    assert by[("1099_div", 2026)].fields == by[("1099_div", 2025)].fields
    assert by[("1099_div", 2026)].version == "1099_div-2026-v1"


def test_ac_the_feld_w2_reads_its_boxes() -> None:
    form, year, fields = _fields("feld_w2")
    assert (form, year) == ("w2", 2025)
    assert fields["w2.box1"].value_text == _money(GOLDEN["feld_w2"]["box_1"])
    assert not fields["w2.box1"].low_confidence
    # The SSN and EIN are never fields (P-03 masks them on the page).
    assert not any("ssn" in k or "ein" in k for k in fields)


def test_ac_iyers_corrected_1099_div_is_flagged_with_box_1b() -> None:
    form, _year, fields = _fields("iyer_1099div_corrected")
    assert form == "1099_div"
    assert fields["1099_div.corrected"].value_text == "true"
    assert GOLDEN["iyer_1099div_corrected"]["corrected"] is True
    assert fields["div.box1b"].value_text == _money(GOLDEN["iyer_1099div_corrected"]["box_1b"])
    assert not fields["div.box1b"].low_confidence  # 3,310.00 ≤ 4,120.00: the tie-out holds


def test_a_tie_out_break_flags_both_fields_and_changes_nothing() -> None:
    broken = rules.broken_tie_outs(
        {"div.box1a": "3310.00", "div.box1b": "4120.00"},
        (rules.TieOut("div.box1b", "div.box1a"),),
    )
    assert broken == {"div.box1a", "div.box1b"}


def test_the_printed_caption_alone_is_not_a_correction() -> None:
    assert not rules.corrected(["CORRECTED", "(if", "checked)", "Form", "1099-INT"], "CORRECTED")
    assert rules.corrected(["X", "CORRECTED", "(if", "checked)"], "CORRECTED")
    assert rules.corrected(["CORRECTED", "Form", "1099-DIV", "2025"], "CORRECTED")


def test_the_notice_maps_declare_no_tax_form_keys() -> None:
    for m in load_maps():
        if m.family == "notices":
            assert (m.year_after, m.corrected_anchor, m.tie_outs) == (None, None, ())
