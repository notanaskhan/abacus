"""P-11-T35 (TASK-6308; P-11 F8, AC8.4, AC8.7; DEC-3008): tax form maps part 2.

Row acceptance: "Meera Shah's Ridgeline K-1 yields Box 2 468,008, Box 5 6,992, Box 18A 2,356 and
Box 19A 228,000, each cited to its bbox, and the Feld 1095-C is identified as TY2025."

Meera's K-1 is laid out here as words with boxes (a page as P-11's OCR leaves it); the Feld
1095-C is the synthetic scanned corpus's page (P-11-T28) on FakeOcr.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from decimal import Decimal
from typing import Final

from abacus.kernel.ocr import normalise
from abacus.modules.evidence.form_extraction import Extracted, extract, identify, load_maps
from abacus.modules.evidence.words import PageWords, Word
from abacus_tools.synthetic.scanned_corpus import generate

NEW: Final = ("k1_1065", "k1_1120s", "k1_1041", "f1095a", "f1095c", "ssa_1099")


def _page(lines: Sequence[Sequence[str]], page: int = 1) -> PageWords:
    """Each line's words left to right at 14 pt spacing, lines 18 pt apart."""
    words: list[Word] = []
    for row, line in enumerate(lines):
        x = 36.0
        top = 40.0 + row * 18
        for text in line:
            width = 6.0 * len(text)
            words.append(Word(text, x, top, x + width, top + 10, 0.99))
            x += width + 6
    return PageWords(page, 612.0, 792.0, 0, tuple(words))


MEERA_K1 = _page(
    [
        ("Schedule", "K-1", "(Form", "1065)", "2025"),
        ("Partner", "Meera", "Shah"),
        ("Partnership", "Ridgeline", "Property", "Partners,", "LP"),
        ("2", "Net", "rental", "real", "estate", "income", "(loss)", "468,008"),
        ("5", "Interest", "income", "6,992"),
        ("18A", "Tax-exempt", "interest", "income", "2,356"),
        ("19", "A", "Cash", "distributions", "228,000"),
    ]
)
STATE_PAGE = _page(
    [("State", "Information", "Ridgeline", "Property", "Partners,", "LP"), ("2", "Net", "rental",
      "real", "estate", "income", "(loss)", "155,000")],
    page=2,
)  # fmt: skip


def _fields(pages: Sequence[PageWords]) -> dict[str, Extracted]:
    found = identify(pages)
    assert found is not None
    return {f.field_key: f for f in extract(found, pages)}


def test_every_part_2_form_has_ty2025_ty2026_and_ty2027_maps() -> None:
    have = {(m.form_type, m.tax_year) for m in load_maps() if m.family == "tax_forms"}
    for form in NEW:
        assert {(form, 2025), (form, 2026), (form, 2027)} <= have, form


def test_ac_meera_shahs_ridgeline_k1_reads_its_boxes_with_their_bboxes() -> None:
    found = identify([MEERA_K1])
    assert found is not None and (found.form_type, found.tax_year) == ("k1_1065", 2025)
    fields = _fields([MEERA_K1])
    expected = {
        "k1_1065.box2": "468008.00",
        "k1_1065.box5": "6992.00",
        "k1_1065.box18a": "2356.00",
        "k1_1065.box19a": "228000.00",
    }
    for key, value in expected.items():
        assert fields[key].value_text == value, key
        assert fields[key].page == 1
        x0, top, x1, bottom = fields[key].bbox
        assert x1 > x0 and bottom > top
        assert not fields[key].low_confidence


def test_a_caption_inside_a_code_line_is_not_taken_for_its_box() -> None:
    no_box5 = _page([line for i, line in enumerate(_lines(MEERA_K1)) if i != 4])
    fields = _fields([no_box5])
    assert "k1_1065.box5" not in fields  # "18A Tax-exempt interest income" is box 18, not box 5
    assert fields["k1_1065.box18a"].value_text == "2356.00"


def _lines(page: PageWords) -> list[list[str]]:
    rows: dict[float, list[str]] = {}
    for w in page.words:
        rows.setdefault(w.top, []).append(w.text)
    return [rows[k] for k in sorted(rows)]


def test_ac_a_state_attachment_is_flagged_for_review_and_never_read() -> None:
    fields = _fields([MEERA_K1, STATE_PAGE])
    flag = fields["k1_1065.state_attachment"]
    assert (flag.value_text, flag.low_confidence, flag.page) == ("true", True, 2)
    assert fields["k1_1065.box2"].value_text == "468008.00"  # the federal box, not 155,000
    assert all(f.page == 1 for k, f in fields.items() if k != "k1_1065.state_attachment")


def test_the_1120s_and_1041_k1s_are_told_apart() -> None:
    s_corp = _page(
        [("Schedule", "K-1", "(Form", "1120-S)", "2025"), ("4", "Interest", "income", "310")]
    )
    trust = _page(
        [("Schedule", "K-1", "(Form", "1041)", "2027"), ("1", "Interest", "income", "88")]
    )
    a, b = identify([s_corp]), identify([trust])
    assert a is not None and (a.form_type, a.tax_year) == ("k1_1120s", 2025)
    assert b is not None and (b.form_type, b.tax_year) == ("k1_1041", 2027)
    assert _fields([s_corp])["k1_1120s.box4"].value_text == "310.00"


def _corpus(key: str) -> PageWords:
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


def test_ac_the_feld_1095c_is_identified_as_ty2025() -> None:
    found = identify([_corpus("feld_1095c")])
    assert found is not None and (found.form_type, found.tax_year) == ("f1095c", 2025)
    fields = {f.field_key: f for f in extract(found, [_corpus("feld_1095c")])}
    assert fields["f1095c.line14"].value_text == "1E"


def test_ssa_1099_reads_its_boxes_and_ties_out() -> None:
    page = _page(
        [
            ("FORM", "SSA-1099", "-", "SOCIAL", "SECURITY", "BENEFIT", "STATEMENT", "2025"),
            ("Box", "3.", "Benefits", "Paid", "in", "2025", "24,000.00"),
            ("Box", "4.", "Benefits", "Repaid", "to", "SSA", "in", "2025", "1,200.00"),
            ("Box", "5.", "Net", "Benefits", "for", "2025", "22,800.00"),
        ]
    )
    found = identify([page])
    assert found is not None and (found.form_type, found.tax_year) == ("ssa_1099", 2025)
    fields = _fields([page])
    assert fields["ssa_1099.box5"].value_text == "22800.00"
    assert not fields["ssa_1099.box5"].low_confidence  # 22,800 <= 24,000: never summed, ordered


def test_ty2026_k1_inherits_ty2025_under_its_own_version() -> None:
    by = {(m.form_type, m.tax_year): m for m in load_maps()}
    assert by[("k1_1065", 2026)].fields == by[("k1_1065", 2025)].fields
    assert by[("k1_1065", 2026)].code_boxes == by[("k1_1065", 2025)].code_boxes
    assert by[("k1_1065", 2026)].version == "k1_1065-2026-v1"
