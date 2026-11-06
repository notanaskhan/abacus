"""P-11-T25 (TASK-3310; DEC-2309): OCR's page images and words, from the row and AC7.

"A scanned W-2 at a flagged firm gets OCR words, a masked box a and a page offshore members can
open, with the flag off the page stays not_scannable, and the version's bytes and fingerprint never
change." The pipeline's database half runs in the integration pass; here the pure rules hold.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from abacus.kernel.db import TenantContext
from abacus.kernel.ocr import OcrPage, OcrWord
from abacus.kernel.uow import Ref
from abacus.modules.evidence import ocr_gate
from abacus.modules.evidence.ocr_normalise import rasterise
from abacus.modules.evidence.ocr_step import (
    _page_words,  # pyright: ignore[reportPrivateUsage] -- the module's own helper
    _system,  # pyright: ignore[reportPrivateUsage] -- the module's own helper
)
from abacus.modules.evidence.words import layer_document, parse_layer


def _image(fmt: str, size: tuple[int, int] = (60, 40), **save: object) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt, **save)
    return buffer.getvalue()


def test_ac_an_images_page_is_its_size_in_pixels() -> None:
    [page] = rasterise(_image("PNG"), "image/png", None)
    assert (page.page, page.width_pt, page.height_pt) == (1, 60.0, 40.0)


def test_ac_exif_orientation_is_applied_before_reading() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotated 90 degrees
    [page] = rasterise(_image("JPEG", exif=exif), "image/jpeg", None)
    assert (page.width_pt, page.height_pt) == (40.0, 60.0)


def test_ac_a_multi_page_tiff_is_each_frame() -> None:
    first, second = Image.new("RGB", (10, 10)), Image.new("RGB", (20, 20))
    buffer = io.BytesIO()
    first.save(buffer, format="TIFF", save_all=True, append_images=[second])
    pages = rasterise(buffer.getvalue(), "image/tiff", None)
    assert [(p.page, p.width_pt) for p in pages] == [(1, 10.0), (2, 20.0)]


def test_ac_ocr_words_carry_their_confidence_through_the_sealed_layer() -> None:
    read = OcrPage(
        "a" * 64,
        (
            OcrWord(
                "6081", (Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")), Decimal("0.84")
            ),
        ),
        None,
    )
    layer = _page_words(1, 612.0, 792.0, 0, read)
    assert layer.words[0].confidence == 0.84
    assert parse_layer(layer_document(layer)).words == layer.words


def test_ac_the_step_runs_as_the_system() -> None:
    tenant = _system(uuid.uuid4())
    assert isinstance(tenant, TenantContext)
    assert tenant.actor_kind == "system"


async def test_ac_a_run_records_without_any_text_in_its_audit_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression (DEC-2332): `Ref` refuses text, and this one held the refusal's name, so every
    run raised before the pages were read."""
    recorded: list[Ref] = []

    class _Tx:
        session = SimpleNamespace(scalar=AsyncMock(return_value=uuid.uuid4()))

        def record(self, _action: str, *, target: object, after: Ref) -> None:
            recorded.append(after)

    @asynccontextmanager
    async def fake_uow(_tenant: object) -> AsyncIterator[_Tx]:
        yield _Tx()

    monkeypatch.setattr(ocr_gate, "uow", fake_uow)
    tenant = TenantContext(uuid.uuid4(), "system", "test")
    for refused in (None, "quota_exceeded"):
        await ocr_gate.record_run(
            tenant,
            evidence_version_id=None,
            inbox_file_id=None,
            provider="fake",
            api="detect_text",
            pages=[1],
            refused=refused,  # type: ignore[arg-type]
            synthetic_firm=True,
            request_ids=[],
        )
    assert [r.fields for r in recorded] == [{"pages": 1, "refused": 0}, {"pages": 1, "refused": 1}]


@pytest.mark.parametrize(
    ("used", "pages", "over"), [(4999, 1, False), (5000, 1, True), (0, 5001, True)]
)
async def test_ac_the_daily_cap_counts_what_the_firm_already_read(
    monkeypatch: pytest.MonkeyPatch, used: int, pages: int, over: bool
) -> None:
    @asynccontextmanager
    async def session(_tenant: object) -> AsyncIterator[object]:
        yield SimpleNamespace(scalar=AsyncMock(return_value=used))

    monkeypatch.setattr(ocr_gate, "tenant_session", session)
    tenant = TenantContext(uuid.uuid4(), "system", "test")
    assert await ocr_gate.over_daily_cap(tenant, pages) is over
