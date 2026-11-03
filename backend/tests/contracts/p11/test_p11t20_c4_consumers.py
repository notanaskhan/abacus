"""C4 v1.1 consumer contract tests (P-11-T20): the shapes notices, tax and closes read from the
OCR and box-extraction reads (P-11-T19, `evidence/ocr_contract.py`).

Each consumer's payload is validated through the provider's models, so a renamed key, a looser
confidence, a whole TIN or a new refusal reason fails here. Figures are the plan's: a close's
receipt lines foot 686.40 + 66.61 = 753.01, and a corrected 1099-R box 1b reads 3,310.00 where
the original read 3,840.00.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import get_args

import pytest
from pydantic import ValidationError

from abacus.kernel.classification import tri_paths
from abacus.modules.evidence import ocr_contract as c4
from abacus.modules.evidence.events import OcrRefusal

BOX = {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.04}
MASK = "tin_tok_8841"  # a mask token, not a secret


def _field(key: str, value: str | None, confidence: float, **over: object) -> dict[str, object]:
    return {
        "field_key": key,
        "label": key,
        "value_type": "money",
        "value_text": value,
        "page": 1,
        "bbox": BOX,
        "confidence": confidence,
        "low_confidence": confidence < c4.LOW_CONFIDENCE,
        "extractor_kind": "ocr_map",
        "match_id": f"m-{key}",
        **over,
    }


def test_refusal_reasons_are_the_eight_the_consumers_handle() -> None:
    assert set(get_args(OcrRefusal)) == {
        "kill_switch",
        "flag_off",
        "provider_terms",
        "boundary_basis",
        "consent_7216",
        "daily_page_cap",
        "size_limit",
        "provider_error",
    }


def test_low_confidence_threshold_is_090() -> None:
    assert c4.LOW_CONFIDENCE == 0.90


@pytest.mark.parametrize("key", ["box_1", "w2.box_1", "1099r.box_1b"])
def test_field_keys_the_consumers_use_are_valid(key: str) -> None:
    c4.ExtractedFieldOut.model_validate(_field(key, "1.00", 0.99))


@pytest.mark.parametrize("key", ["Box1", "box 1", "-box", ""])
def test_a_drifted_field_key_is_refused(key: str) -> None:
    with pytest.raises(ValidationError):
        c4.ExtractedFieldOut.model_validate(_field(key, "1.00", 0.99))


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_confidence_stays_within_0_and_1(confidence: float) -> None:
    with pytest.raises(ValidationError):
        c4.ExtractedFieldOut.model_validate(_field("box_1", "1.00", confidence))


def test_tin_boxes_carry_only_the_mask_token() -> None:
    tin = c4.ExtractedFieldOut.model_validate(
        _field("payer_tin", None, 0.97, value_type="tin", mask_token=MASK)
    )
    assert tin.value_text is None
    assert tin.mask_token == MASK


def test_extracted_values_are_tax_return_information() -> None:
    assert "value_text" in tri_paths(c4.ExtractedFieldOut)
    assert any(p.startswith("items") for p in tri_paths(c4.ExtractedFieldsOut))


def test_tax_a_corrected_1099r_box_1b() -> None:
    original = c4.ExtractedFieldsOut.model_validate(
        {
            "form_type": "1099-R",
            "tax_year": 2025,
            "items": [_field("box_1b", "3840.00", 0.98)],
        }
    )
    corrected = c4.ExtractedFieldsOut.model_validate(
        {
            "form_type": "1099-R",
            "tax_year": 2025,
            "corrected": True,
            "items": [_field("box_1b", "3310.00", 0.98)],
        }
    )
    assert original.corrected is False
    assert corrected.corrected is True
    assert Decimal(corrected.items[0].value_text or "0") == Decimal("3310.00")
    assert Decimal(original.items[0].value_text or "0") == Decimal("3840.00")


def test_closes_receipt_lines_foot() -> None:
    fields = c4.ExtractedFieldsOut.model_validate(
        {
            "form_type": None,
            "items": [
                _field("subtotal", "686.40", 0.96),
                _field("tax", "66.61", 0.93),
                _field("total", "753.01", 0.97),
            ],
        }
    )
    by_key = {f.field_key: Decimal(f.value_text or "0") for f in fields.items}
    assert by_key["subtotal"] + by_key["tax"] == by_key["total"] == Decimal("753.01")


def test_notices_low_confidence_fields_are_flagged_not_dropped() -> None:
    fields = c4.ExtractedFieldsOut.model_validate(
        {
            "form_type": "CP2000",
            "items": [_field("proposed_tax", "1836.00", 0.82), _field("notice_date", None, 0.95)],
        }
    )
    low = [f.field_key for f in fields.items if f.low_confidence]
    assert low == ["proposed_tax"]


def test_tables_keep_their_shape() -> None:
    table = c4.ExtractedTableOut.model_validate(
        {
            "table_id": str(uuid.uuid4()),
            "page": 2,
            "bbox": BOX,
            "rows": [[{"text": "Item", "bbox": BOX, "confidence": 0.99}]],
        }
    )
    assert table.rows[0][0].text == "Item"


def test_a_retry_refusal_names_its_reason() -> None:
    out = c4.TextRetryOut.model_validate({"status": "refused", "reason": "daily_page_cap"})
    assert out.reason == "daily_page_cap"
    with pytest.raises(ValidationError):
        c4.TextRetryOut.model_validate({"status": "refused", "reason": "quota"})
