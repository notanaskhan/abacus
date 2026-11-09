"""T-04-T14 (TASK-6525; T-04 §4.5; ADR-166 §2; DEC-3125): the `tax_form_line` citable.

Row acceptance: "A fabricated box value, page or bbox fails verification, a corrected 1099 marks
the old citation moved, and the regions API returns rects only for citations the viewer may see."
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import cast

import pytest

from abacus.kernel.uow import UnitOfWork
from abacus.modules.evidence.api import CitationAnchor, CitationClaim
from abacus.modules.identity.api import Actor
from abacus.modules.tax import form_line_citations as flc

pytestmark = pytest.mark.asyncio
RETURN, ENGAGEMENT = uuid.uuid4(), uuid.uuid4()


class _Tx:
    def __init__(self, row: object | None) -> None:
        async def execute(*_a: object, **_k: object) -> object:
            return SimpleNamespace(first=lambda: row)

        self.session = SimpleNamespace(execute=execute)


def _row(value: str = "14820", engagement: uuid.UUID = ENGAGEMENT) -> object:
    return SimpleNamespace(
        engagement_id=engagement, field_key="f1040.line3b", line_ref="3b",
        label="Ordinary dividends", current_value={"t": "amount", "v": value}, form_code="1040",
    )  # fmt: skip


def _claim(value: str | None = "14,820") -> CitationClaim:
    return CitationClaim(
        "tax_form_line", {"return_id": str(RETURN), "field_key": "f1040.line3b"}, value=value
    )


async def _allowed(*_a: object) -> bool:
    return True


async def test_a_matching_value_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flc, "_may_read", _allowed)
    v = await flc.verify_tax_form_line(
        cast(UnitOfWork, _Tx(_row())),
        cast(Actor, object()),
        _claim(),
        CitationAnchor("x", uuid.uuid4(), engagement_id=ENGAGEMENT),
    )
    assert v.verified and v.match_id == f"tfl:{RETURN}:f1040.line3b" and v.value_text == "14,820"


async def test_a_fabricated_value_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flc, "_may_read", _allowed)
    v = await flc.verify_tax_form_line(
        cast(UnitOfWork, _Tx(_row())),
        cast(Actor, object()),
        _claim("14,920"),
        CitationAnchor("x", uuid.uuid4(), engagement_id=ENGAGEMENT),
    )
    assert v.reason == "value_mismatch"


async def test_another_engagements_return_is_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(flc, "_may_read", _allowed)
    v = await flc.verify_tax_form_line(
        cast(UnitOfWork, _Tx(_row(engagement=uuid.uuid4()))),
        cast(Actor, object()),
        _claim(),
        CitationAnchor("x", uuid.uuid4(), engagement_id=ENGAGEMENT),
    )
    assert v.reason == "source_not_found"


async def test_no_engagement_or_no_right_is_not_visible() -> None:
    v = await flc.verify_tax_form_line(
        cast(UnitOfWork, _Tx(_row())),
        cast(Actor, object()),
        _claim(),
        CitationAnchor("x", uuid.uuid4()),
    )
    assert v.reason == "source_not_visible"
    w = await flc.verify_tax_form_line(
        cast(UnitOfWork, _Tx(_row())),
        cast(Actor, object()),
        _claim(),
        CitationAnchor("x", uuid.uuid4(), engagement_id=ENGAGEMENT),
    )
    assert w.reason == "source_not_visible"


def test_labels_are_composed_by_code() -> None:
    assert flc.linked_label("1040", "3b", Decimal(14820)) == "Form 1040 · Line 3b 14,820"


def test_a_box_is_a_document_text_claim_the_word_layer_rereads() -> None:
    ev = uuid.uuid4()
    claim = flc.box_claim(ev, 1, (72.0, 82.0, 160.0, 96.0), "14,820.00")
    assert claim.kind == "document_text"
    assert claim.locator == {
        "evidence_version_id": str(ev),
        "page": 1,
        "bbox": [72.0, 82.0, 160.0, 96.0],
    }
