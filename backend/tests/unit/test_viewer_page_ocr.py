"""P-11-T31: a manifest page says where its words came from, and OCR's facts or its refusal."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from abacus.modules.evidence import viewer
from abacus.modules.evidence.viewer import (
    ViewerPageOcr,
    _page_ocr,  # pyright: ignore[reportPrivateUsage] -- the rule under test
    _text_source,  # pyright: ignore[reportPrivateUsage] -- the rule under test
)


def _page(**kw: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "text_source": None,
        "has_text_layer": False,
        "mean_confidence": None,
        "low_conf_words": None,
    }
    return SimpleNamespace(**(base | kw))


def test_a_page_from_before_0666_reads_its_layer_flag() -> None:
    assert _text_source(_page(has_text_layer=True)) == "text_layer"  # type: ignore[arg-type]  # a stand-in row
    assert _text_source(_page()) == "none"  # type: ignore[arg-type]  # a stand-in row
    assert _text_source(_page(text_source="ocr")) == "ocr"  # type: ignore[arg-type]  # a stand-in row


def test_a_page_ocr_read_carries_its_confidence() -> None:
    page = _page(
        text_source="ocr", has_text_layer=True, mean_confidence=Decimal("0.94"), low_conf_words=3
    )
    assert _page_ocr(page, "provider_error") == ViewerPageOcr(0.94, 3)  # type: ignore[arg-type]  # a stand-in row


def test_a_refusal_shows_only_on_a_page_left_without_words() -> None:
    assert _page_ocr(_page(), "consent_7216") == ViewerPageOcr(refused_reason="consent_7216")  # type: ignore[arg-type]  # a stand-in row
    assert _page_ocr(_page(has_text_layer=True, text_source="text_layer"), "consent_7216") is None  # type: ignore[arg-type]  # a stand-in row
    assert _page_ocr(_page(), None) is None  # type: ignore[arg-type]  # a stand-in row


def test_a_client_gets_neither_how_a_page_was_read_nor_the_refusal() -> None:
    source = Path(viewer.__file__).read_text()
    assert "refusal = None if client else" in source
    assert "ocr=None if client else _page_ocr(page, refusal)" in source
