"""P-11-T25 (TASK-3384; DEC-2383; AC7.3): a form's key-value positions help label-anchored masking.

A value OCR places where a line reading can't anchor it is masked when a form's key names it;
nothing a line reading found moves; a layer with no hints stays byte for byte.
"""

from __future__ import annotations

from decimal import Decimal

from abacus.kernel.ocr import normalise_key_values
from abacus.modules.evidence import pii
from abacus.modules.evidence.pii import ScanPage, scan_layer
from abacus.modules.evidence.words import KeyHint, PageWords, Word, layer_document, parse_layer

LABEL = [
    Word("Employee's", 50, 50, 100, 60),
    Word("social", 102, 50, 130, 60),
    Word("security", 132, 50, 170, 60),
    Word("number", 172, 50, 210, 60),
]
# Far below and across from its label: no line reading anchors bare digits there.
VALUE = Word("123456789", 400, 400, 460, 410)
HINT = KeyHint("Employee's social security number", 395, 395, 470, 415)


def _page(hints: tuple[KeyHint, ...] = ()) -> ScanPage:
    return ScanPage(1, [*LABEL, VALUE], 0, 612.0, 792.0, False, hints)


def test_ac_the_hint_masks_what_the_line_reading_cannot_anchor() -> None:
    without, _, _ = scan_layer([_page()])
    assert not [f for f in without if f.last4 == "6789" and f.label_anchored]
    found, scanned, _ = scan_layer([_page((HINT,))])
    anchored = [f for f in found if f.last4 == "6789" and f.label_anchored]
    assert len(anchored) == 1
    assert anchored[0].kind == "ssn"
    assert scanned == [1]


def test_ac_a_key_naming_no_label_adds_nothing() -> None:
    other = KeyHint("Employer name", 395, 395, 470, 415)
    assert scan_layer([_page((other,))])[0] == scan_layer([_page()])[0]


def test_ac_a_value_already_found_is_not_found_twice() -> None:
    anchored = [
        Word("SSN:", 50, 100, 80, 110),
        Word("900-12-3456", 85, 100, 150, 110),
    ]
    hint = KeyHint("SSN", 84, 98, 152, 112)
    found, _, _ = scan_layer([ScanPage(1, anchored, 0, 612.0, 792.0, False, (hint,))])
    assert len(found) == 1


def test_ac_a_turned_page_keeps_its_label_reading_and_takes_no_hint() -> None:
    turned = ScanPage(1, [*LABEL, VALUE], 90, 612.0, 792.0, False, (HINT,))
    assert not [f for f in scan_layer([turned])[0] if f.last4 == "6789" and f.label_anchored]


def test_ac_only_a_page_naming_a_tin_asks_for_forms() -> None:
    assert pii.names_a_tin(w.text for w in LABEL)
    assert not pii.names_a_tin(["Invoice", "total", "1,200.00"])


def test_ac_the_layer_keeps_its_hints_and_a_page_with_none_is_unchanged() -> None:
    plain = PageWords(1, 612.0, 792.0, 0, (VALUE,))
    assert b"hints" not in layer_document(plain)
    assert parse_layer(layer_document(plain)).hints == ()
    hinted = PageWords(1, 612.0, 792.0, 0, (VALUE,), hints=(HINT,))
    assert parse_layer(layer_document(hinted)).hints == (HINT,)


def test_ac_textracts_key_value_blocks_read_as_a_key_and_a_value_box() -> None:
    box = {"BoundingBox": {"Left": 0.5, "Top": 0.5, "Width": 0.1, "Height": 0.1}}
    blocks = [
        {"Id": "w1", "BlockType": "WORD", "Text": "SSN", "Geometry": box},
        {
            "Id": "k",
            "BlockType": "KEY_VALUE_SET",
            "EntityTypes": ["KEY"],
            "Confidence": 91,
            "Geometry": box,
            "Relationships": [
                {"Type": "CHILD", "Ids": ["w1"]},
                {"Type": "VALUE", "Ids": ["v"]},
            ],
        },
        {"Id": "v", "BlockType": "KEY_VALUE_SET", "EntityTypes": ["VALUE"], "Geometry": box},
        {"Id": "lone", "BlockType": "KEY_VALUE_SET", "EntityTypes": ["KEY"], "Geometry": box},
    ]
    (found,) = normalise_key_values(blocks, width_pt=Decimal(100), height_pt=Decimal(200))
    assert found.key == "SSN"
    assert found.value_bbox == tuple(Decimal(x) for x in ("50.00", "100.00", "60.00", "120.00"))
    assert found.confidence == Decimal("0.910")
